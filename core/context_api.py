"""
core/context_api.py — OmniContext Context Explorer API router.

Endpoints:
  GET /api/context/explore        — hybrid search with optional filters
  GET /api/context/sources        — list distinct sources
  GET /api/context/projects       — list distinct projects
  GET /api/context/tags           — list distinct tags with counts
  GET /api/context/stats          — aggregated metadata statistics
  GET /api/context/related/{doc_id} — nearest-neighbour context discovery
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from fastapi import APIRouter, Query

from memory.vector_store import MemoryStore

context_router = APIRouter(prefix="/api/context", tags=["Context Explorer"])


def _store() -> MemoryStore:
    return MemoryStore()


# ── Explore ───────────────────────────────────────────────────────────────────

@context_router.get("/explore")
def explore(
    q: str = Query(..., description="Search query"),
    source_type: Optional[str] = Query(None, description="Filter by source type (code/pdf/web/clipboard/note)"),
    project: Optional[str] = Query(None, description="Filter by project name"),
    tags: Optional[str] = Query(None, description="Comma-separated tag filters"),
    top_k: int = Query(5, ge=1, le=50, description="Number of results"),
):
    """
    Hybrid semantic + keyword search with optional metadata filtering.

    Returns relevance-ranked results with source provenance.
    """
    store = _store()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    results = store.search_memories_hybrid(
        query=q,
        source_type=source_type,
        tags=tag_list,
        project=project,
        top_k=top_k,
    )

    return {
        "query": q,
        "filters": {
            "source_type": source_type,
            "project": project,
            "tags": tag_list,
        },
        "total": len(results),
        "results": [
            {
                "id": r["id"],
                "preview": r["preview"],
                "source": r["source"],
                "source_type": r["source_type"],
                "project": r.get("project"),
                "tags": r.get("tags", []),
                "relevance": r["final_score"],
                "semantic_score": r["semantic_score"],
                "keyword_score": r["keyword_score"],
                "timestamp": r["timestamp"],
                "language": r.get("language"),
                "document_type": r.get("document_type"),
                "heading": r.get("heading"),
                "chunk_index": r.get("chunk_index"),
                "total_chunks": r.get("total_chunks"),
            }
            for r in results
        ],
    }


# ── Sources ───────────────────────────────────────────────────────────────────

@context_router.get("/sources")
def list_sources():
    """Return all distinct source strings with counts and type breakdown."""
    store = _store()
    all_meta = store.get_all_metadata()

    source_counts: Counter = Counter()
    type_counts: Counter = Counter()

    for m in all_meta:
        src = m.get("source", "unknown")
        stype = m.get("source_type", "unknown")
        source_counts[src] += 1
        type_counts[stype] += 1

    return {
        "total_chunks": len(all_meta),
        "source_type_breakdown": dict(type_counts.most_common()),
        "sources": [
            {"source": src, "count": cnt}
            for src, cnt in source_counts.most_common(100)
        ],
    }


# ── Projects ─────────────────────────────────────────────────────────────────

@context_router.get("/projects")
def list_projects():
    """Return all distinct project names with chunk counts."""
    store = _store()
    all_meta = store.get_all_metadata()

    project_counts: Counter = Counter()
    for m in all_meta:
        proj = m.get("project")
        if proj:
            project_counts[proj] += 1

    return {
        "total": len(project_counts),
        "projects": [
            {"project": p, "chunks": cnt}
            for p, cnt in project_counts.most_common()
        ],
    }


# ── Tags ──────────────────────────────────────────────────────────────────────

@context_router.get("/tags")
def list_tags():
    """Return all distinct tags with occurrence counts."""
    store = _store()
    all_meta = store.get_all_metadata()

    tag_counts: Counter = Counter()
    for m in all_meta:
        tags_raw = m.get("tags", "")
        tags = [t for t in tags_raw.split(",") if t] if isinstance(tags_raw, str) else []
        for tag in tags:
            tag_counts[tag] += 1

    return {
        "total_unique_tags": len(tag_counts),
        "tags": [
            {"tag": t, "count": cnt}
            for t, cnt in tag_counts.most_common(50)
        ],
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

@context_router.get("/stats")
def context_stats():
    """Return rich aggregated statistics about the context store."""
    store = _store()
    all_meta = store.get_all_metadata()
    total = len(all_meta)

    if total == 0:
        return {"total_chunks": 0, "message": "No memories indexed yet."}

    type_counts: Counter = Counter()
    language_counts: Counter = Counter()
    project_counts: Counter = Counter()
    tag_counts: Counter = Counter()

    for m in all_meta:
        stype = m.get("source_type", "unknown")
        lang = m.get("language")
        proj = m.get("project")
        tags_raw = m.get("tags", "")
        tags = [t for t in tags_raw.split(",") if t] if isinstance(tags_raw, str) else []

        type_counts[stype] += 1
        if lang:
            language_counts[lang] += 1
        if proj:
            project_counts[proj] += 1
        for tag in tags:
            tag_counts[tag] += 1

    return {
        "total_chunks": total,
        "source_types": dict(type_counts.most_common()),
        "top_languages": dict(language_counts.most_common(10)),
        "top_projects": dict(project_counts.most_common(10)),
        "top_tags": dict(tag_counts.most_common(20)),
    }


# ── Related context ───────────────────────────────────────────────────────────

@context_router.get("/related/{doc_id:path}")
def related_context(doc_id: str, top_k: int = Query(5, ge=1, le=20)):
    """
    Find the nearest-neighbour chunks to a given memory ID.

    Enables knowledge-graph-like exploration of the context store.
    """
    store = _store()
    related = store.find_related_memories(doc_id=doc_id, top_k=top_k)

    return {
        "doc_id": doc_id,
        "total": len(related),
        "related": related,
    }
