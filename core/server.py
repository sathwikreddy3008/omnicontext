"""
core/server.py — OmniContext FastAPI server.

Routes:
  /api/stats          — chunk count
  /api/ask            — blocking RAG query (returns structured response)
  /api/ask_stream     — SSE streaming RAG with meta event
  /api/clear_chat     — clear conversation history
  /api/ingest         — ingest a local directory
  /api/ingest_url     — scrape and ingest a URL
  /api/ingest_pdf     — upload and ingest a PDF
  /api/clear          — wipe all memories
  /api/memories       — list stored memories
  /api/memories/search — semantic search (memory browser)
  /api/memories/{id}  — delete a memory
  /api/add_note       — save a manual note
  /api/context/*      — Context Explorer (via context_api router)
  /api/telemetry/metrics — observability metrics
  /                   — serve the Web UI
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from memory.vector_store import MemoryStore
from inference.llm_engine import BrainEngine
from ingestion.file_indexer import FileIndexer
from ingestion.web_scraper import WebScraper
from ingestion.pdf_parser import PdfParser
from core.context_api import context_router
from core.telemetry import telemetry

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OmniContext API",
    description="Local-first, privacy-preserving AI context engine for retrieval-grounded answers.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Context Explorer router
app.include_router(context_router)

# PyInstaller compatibility
if hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.parent

UI_DIR = BASE_DIR / "ui"
UI_DIR.mkdir(exist_ok=True)

# Single global engine (preserves conversation history across requests)
global_engine = BrainEngine()

# ── Request/Response models ───────────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str

class IngestRequest(BaseModel):
    path: str

class UrlRequest(BaseModel):
    url: str

class NoteRequest(BaseModel):
    text: str

# ── Root / Health ─────────────────────────────────────────────────────────────

@app.get("/")
def serve_ui():
    return FileResponse(str(UI_DIR / "index.html"))

@app.get("/api")
def root():
    return {
        "name": "OmniContext",
        "tagline": (
            "A local-first, privacy-preserving AI context engine that continuously ingests files, "
            "PDFs, web content, and clipboard activity, enriches them with metadata, stores them "
            "in a semantic vector database, and provides retrieval-grounded answers through a local LLM."
        ),
        "version": "2.0.0",
        "docs": "/docs",
    }

# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    store = MemoryStore()
    return {"count": store.get_count()}

# ── Ask (blocking) ────────────────────────────────────────────────────────────

@app.post("/api/ask")
def ask_brain(req: AskRequest):
    store = MemoryStore()

    with telemetry.track_retrieval(query=req.query) as _:
        results = store.search_memories_hybrid(req.query, top_k=5)

    if not results:
        return {
            "answer": "I don't have any relevant context for that query.",
            "confidence": 0.0,
            "insufficient_context": True,
            "used_sources": [],
            "context_quality": {"is_sufficient": False, "chunk_count": 0},
        }

    with telemetry.track_llm(model=global_engine.model_name) as _:
        result = global_engine.ask(req.query, results)

    return result

# ── Ask (streaming SSE) ───────────────────────────────────────────────────────

@app.post("/api/ask_stream")
def ask_brain_stream(req: AskRequest):
    """
    Streams the LLM response via Server-Sent Events.

    Event types:
      {"token": "...", "done": false}           — text fragment
      {"token": "", "done": false, "context": ...} — initial context payload
      {"token": "", "done": true, "meta": {...}}   — completion + trust metadata
    """
    store = MemoryStore()
    results = store.search_memories_hybrid(req.query, top_k=5)

    if not results:
        def no_context():
            yield f"data: {json.dumps({'token': 'I do not have any relevant context for that query.', 'done': False})}\n\n"
            yield f"data: {json.dumps({'token': '', 'done': True, 'context': '', 'meta': {'confidence': 0.0, 'used_sources': []}})}\n\n"
        return StreamingResponse(no_context(), media_type="text/event-stream")

    # Build context string for the UI context panel
    context_str = "\n\n".join(
        f"[Source: {r['source']}]\n{r['content'][:400]}" for r in results[:3]
    )

    def generate():
        # Send context immediately so the UI can display it
        yield f"data: {json.dumps({'token': '', 'done': False, 'context': context_str})}\n\n"

        meta_payload: dict = {}
        for raw_event in global_engine.ask_stream(req.query, results):
            try:
                event = json.loads(raw_event)
            except Exception:
                continue

            if event.get("type") == "token":
                yield f"data: {json.dumps({'token': event['token'], 'done': False})}\n\n"
            elif event.get("type") == "meta":
                meta_payload = event

        yield f"data: {json.dumps({'token': '', 'done': True, 'meta': meta_payload})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ── Clear chat ────────────────────────────────────────────────────────────────

@app.post("/api/clear_chat")
def clear_chat():
    global_engine.clear_history()
    return {"status": "success", "message": "Chat history cleared."}

# ── Ingest directory ──────────────────────────────────────────────────────────

@app.post("/api/ingest")
def ingest_directory(req: IngestRequest):
    store = MemoryStore()
    indexer = FileIndexer(store)
    try:
        with telemetry.track_ingestion(source=req.path):
            indexer.ingest_directory(req.path)
        return {"status": "success", "message": f"Successfully ingested directory: {req.path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Ingest URL ────────────────────────────────────────────────────────────────

@app.post("/api/ingest_url")
def ingest_url(req: UrlRequest):
    store = MemoryStore()
    scraper = WebScraper(store)
    try:
        with telemetry.track_ingestion(source=req.url):
            scraper.ingest_url(req.url)
        return {"status": "success", "message": f"Successfully scraped and memorized: {req.url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Ingest PDF ────────────────────────────────────────────────────────────────

@app.post("/api/ingest_pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    store = MemoryStore()
    parser = PdfParser(store)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        with telemetry.track_ingestion(source=file.filename):
            chunks = parser.ingest_pdf(tmp_path)

        return {"status": "success", "message": f"Memorized {chunks} chunks from {file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ── Clear all memories ────────────────────────────────────────────────────────

@app.post("/api/clear")
def clear_brain():
    store = MemoryStore()
    store.clear_collection()
    return {"status": "success", "message": "All OmniContext memories cleared."}

# ── Memory Browser ────────────────────────────────────────────────────────────

@app.get("/api/memories")
def list_memories(limit: int = 50, offset: int = 0):
    store = MemoryStore()
    memories = store.list_memories(limit=limit, offset=offset)
    return {"memories": memories, "total": store.get_count()}

@app.get("/api/memories/search")
def search_memories_browse(q: str):
    store = MemoryStore()
    memories = store.search_memories_detailed(q)
    return {"memories": memories}

@app.delete("/api/memories/{doc_id:path}")
def delete_memory(doc_id: str):
    store = MemoryStore()
    if store.delete_memory(doc_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Memory not found")

# ── Manual notes ──────────────────────────────────────────────────────────────

@app.post("/api/add_note")
def add_note(req: NoteRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")
    store = MemoryStore()
    from memory.models import MemoryMetadata
    meta = MemoryMetadata(source="manual_note", source_type="note", ingested_from="web_ui")
    store.add_memory(text=req.text.strip(), source="manual_note", metadata=meta)
    return {"status": "success", "message": "Note saved to memory."}

# ── Telemetry ─────────────────────────────────────────────────────────────────

@app.get("/api/telemetry/metrics")
def get_metrics():
    return telemetry.get_metrics()

# ── Static files / UI ─────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")
