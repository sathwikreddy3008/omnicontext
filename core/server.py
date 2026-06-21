from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pathlib import Path
import json
import tempfile
import os

from memory.vector_store import MemoryStore
from inference.llm_engine import BrainEngine
from ingestion.file_indexer import FileIndexer
from ingestion.web_scraper import WebScraper
from ingestion.pdf_parser import PdfParser

import sys

app = FastAPI(title="Second Brain API")

# PyInstaller compatibility for finding the UI directory
if hasattr(sys, '_MEIPASS'):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.parent

UI_DIR = BASE_DIR / "ui"
UI_DIR.mkdir(exist_ok=True)

# Create a single global instance so it remembers conversation history
global_engine = BrainEngine()

# API Models
class AskRequest(BaseModel):
    query: str

class IngestRequest(BaseModel):
    path: str

# Endpoints
@app.get("/api/stats")
def get_stats():
    store = MemoryStore()
    return {"count": store.get_count()}

@app.post("/api/ask")
def ask_brain(req: AskRequest):
    store = MemoryStore()
    context = store.search_memories(req.query)
    
    if not context:
        return {"answer": "I don't have any relevant memories for that query.", "context": ""}
        
    answer = global_engine.ask(req.query, context)
    return {"answer": answer, "context": context}

@app.post("/api/ask_stream")
def ask_brain_stream(req: AskRequest):
    """Streams the LLM response token-by-token using Server-Sent Events."""
    store = MemoryStore()
    context = store.search_memories(req.query)
    
    if not context:
        def no_context():
            yield f"data: {json.dumps({'token': 'I do not have any relevant memories for that query.', 'done': False})}\n\n"
            yield f"data: {json.dumps({'token': '', 'done': True, 'context': ''})}\n\n"
        return StreamingResponse(no_context(), media_type="text/event-stream")
    
    def generate():
        # First, send the context so the UI can display it immediately
        yield f"data: {json.dumps({'token': '', 'done': False, 'context': context})}\n\n"
        
        # Stream tokens from the LLM
        for token in global_engine.ask_stream(req.query, context):
            yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
        
        # Signal completion
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/clear_chat")
def clear_chat():
    global_engine.clear_history()
    return {"status": "success", "message": "Short-term chat history cleared."}

@app.post("/api/ingest")
def ingest_directory(req: IngestRequest):
    store = MemoryStore()
    indexer = FileIndexer(store)
    try:
        indexer.ingest_directory(req.path)
        return {"status": "success", "message": f"Successfully ingested directory {req.path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UrlRequest(BaseModel):
    url: str

@app.post("/api/ingest_url")
def ingest_url(req: UrlRequest):
    store = MemoryStore()
    scraper = WebScraper(store)
    try:
        scraper.ingest_url(req.url)
        return {"status": "success", "message": f"Successfully scraped and memorized {req.url}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ingest_pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
        
    store = MemoryStore()
    parser = PdfParser(store)
    
    # Save the uploaded file to a temporary location
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
            
        # Parse it
        pages = parser.ingest_pdf(tmp_path)
        
        # Clean up the temp file
        os.unlink(tmp_path)
        
        return {"status": "success", "message": f"Successfully memorized {pages} pages from {file.filename}"}
    except Exception as e:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear")
def clear_brain():
    store = MemoryStore()
    store.clear_collection()
    return {"status": "success", "message": "Brain memories cleared."}

# --- Memory Browser Endpoints ---

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
    success = store.delete_memory(doc_id)
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Memory not found")

# --- Manual Notes ---

class NoteRequest(BaseModel):
    text: str

@app.post("/api/add_note")
def add_note(req: NoteRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")
    store = MemoryStore()
    store.add_memory(text=req.text.strip(), source="manual_note")
    return {"status": "success", "message": "Note saved to memory."}

# Mount static files (UI)
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

@app.get("/")
def serve_ui():
    return FileResponse(str(UI_DIR / "index.html"))
