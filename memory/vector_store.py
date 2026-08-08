"""
memory/vector_store.py — OmniContext vector store with hybrid retrieval.

Wraps ChromaDB with:
  - MemoryMetadata-aware add_memory()
  - Semantic search (cosine similarity via ChromaDB)
  - Hybrid retrieval: 0.7 * semantic + 0.3 * keyword score
  - Related context discovery (nearest-neighbour by embedding)
  - Structured result dicts throughout
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Union

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from core.config import DB_DIR, EMBEDDING_MODEL, COLLECTION_NAME
from memory.models import MemoryMetadata


class MemoryStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(DB_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )

    # ── Write ────────────────────────────────────────────────────────────────

    def add_memory(
        self,
        text: str,
        source: str = "clipboard",
        doc_id: Optional[str] = None,
        metadata: Optional[Union[dict, MemoryMetadata]] = None,
    ) -> bool:
        """
        Add a chunk to the vector store.

        metadata can be a MemoryMetadata instance or a plain dict.
        When omitted, a minimal MemoryMetadata is constructed from `source`.
        """
        if not text or not text.strip():
            return False

        if doc_id is None:
            doc_id = str(uuid.uuid4())

        # Normalise metadata to a ChromaDB-compatible flat dict
        if isinstance(metadata, MemoryMetadata):
            meta_dict = metadata.to_chroma_dict()
        elif isinstance(metadata, dict):
            # Ensure required keys exist
            meta_dict = metadata.copy()
            meta_dict.setdefault("source", source)
            meta_dict.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        else:
            meta = MemoryMetadata(source=source)
            meta_dict = meta.to_chroma_dict()

        self.collection.upsert(
            documents=[text],
            metadatas=[meta_dict],
            ids=[doc_id],
        )
        return True

    # ── Basic search ─────────────────────────────────────────────────────────

    def search_memories(self, query: str, n_results: int = 3) -> str:
        """Returns a formatted string of the top-n semantically similar chunks."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        memories: list[str] = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                ts = meta.get("timestamp", "unknown time")
                src = meta.get("source", "unknown")
                memories.append(f"[{ts}] (Source: {src}):\n{doc}")
        return "\n\n".join(memories)

    def search_memories_detailed(self, query: str, n_results: int = 10) -> list[dict]:
        """Semantic search returning structured result dicts (for the memory browser)."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        memories: list[dict] = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                doc = doc.strip()
                meta = results["metadatas"][0][i]
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                semantic_score = round(max(0.0, 1 - distance), 3)

                # Re-hydrate tags from comma string if present
                tags_raw = meta.get("tags", "")
                tags = [t for t in tags_raw.split(",") if t] if isinstance(tags_raw, str) else []

                memories.append({
                    "id": results["ids"][0][i],
                    "text": doc[:300] + "..." if len(doc) > 300 else doc,
                    "full_text": doc,
                    "source": meta.get("source", "unknown"),
                    "source_type": meta.get("source_type", "unknown"),
                    "timestamp": meta.get("timestamp", "unknown"),
                    "project": meta.get("project"),
                    "tags": tags,
                    "language": meta.get("language"),
                    "document_type": meta.get("document_type"),
                    "relevance": semantic_score,
                })
        return memories

    # ── Hybrid retrieval ─────────────────────────────────────────────────────

    def search_memories_hybrid(
        self,
        query: str,
        source_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Hybrid retrieval combining semantic similarity and keyword scoring.

        final_score = 0.7 * semantic_score + 0.3 * keyword_score

        Optional filters (applied post-retrieval):
          source_type — exact match on stored source_type
          tags        — chunk must contain ALL requested tags
          project     — exact match on stored project
        """
        # Fetch a larger candidate pool before filtering
        fetch_n = min(max(top_k * 4, 20), self.collection.count() or 1)

        results = self.collection.query(
            query_texts=[query],
            n_results=fetch_n,
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        query_terms = _tokenise(query)
        enriched: list[dict] = []

        for i, doc in enumerate(results["documents"][0]):
            doc = doc.strip()
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i] if results.get("distances") else 0.0
            semantic_score = round(max(0.0, 1 - distance), 3)

            # Re-hydrate tags
            tags_raw = meta.get("tags", "")
            chunk_tags = [t for t in tags_raw.split(",") if t] if isinstance(tags_raw, str) else []

            # ── Post-retrieval metadata filters ──
            if source_type and meta.get("source_type") != source_type:
                continue
            if project and meta.get("project") != project:
                continue
            if tags:
                if not all(t in chunk_tags for t in tags):
                    continue

            # ── Keyword score ──
            keyword_score = _keyword_score(query_terms, doc)
            final_score = round(0.7 * semantic_score + 0.3 * keyword_score, 4)

            enriched.append({
                "id": results["ids"][0][i],
                "content": doc,
                "preview": doc[:200] + "..." if len(doc) > 200 else doc,
                "semantic_score": semantic_score,
                "keyword_score": round(keyword_score, 3),
                "final_score": final_score,
                "source": meta.get("source", "unknown"),
                "source_type": meta.get("source_type", "unknown"),
                "timestamp": meta.get("timestamp", "unknown"),
                "project": meta.get("project"),
                "repository": meta.get("repository"),
                "tags": chunk_tags,
                "language": meta.get("language"),
                "document_type": meta.get("document_type"),
                "chunk_index": meta.get("chunk_index"),
                "total_chunks": meta.get("total_chunks"),
                "heading": meta.get("heading"),
                "metadata": meta,
            })

        # Sort by final_score descending
        enriched.sort(key=lambda x: x["final_score"], reverse=True)
        return enriched[:top_k]

    # ── Related context discovery ────────────────────────────────────────────

    def find_related_memories(self, doc_id: str, top_k: int = 5) -> list[dict]:
        """
        Find the nearest neighbours to a stored chunk.

        Fetches the chunk's document text, re-embeds it as a query,
        and returns the top_k most similar chunks (excluding itself).
        """
        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"],
            )
        except Exception:
            return []

        if not result["documents"]:
            return []

        source_text = result["documents"][0]

        fetch_n = min(top_k + 1, self.collection.count() or 1)
        neighbours = self.collection.query(
            query_texts=[source_text],
            n_results=fetch_n,
            include=["documents", "metadatas", "distances"],
        )

        related: list[dict] = []
        if neighbours["documents"] and neighbours["documents"][0]:
            for i, doc in enumerate(neighbours["documents"][0]):
                nid = neighbours["ids"][0][i]
                if nid == doc_id:
                    continue  # exclude self
                meta = neighbours["metadatas"][0][i]
                distance = neighbours["distances"][0][i] if neighbours.get("distances") else 0.0
                similarity = round(max(0.0, 1 - distance), 3)

                tags_raw = meta.get("tags", "")
                chunk_tags = [t for t in tags_raw.split(",") if t] if isinstance(tags_raw, str) else []

                related.append({
                    "id": nid,
                    "preview": doc.strip()[:200] + "..." if len(doc.strip()) > 200 else doc.strip(),
                    "source": meta.get("source", "unknown"),
                    "source_type": meta.get("source_type", "unknown"),
                    "similarity": similarity,
                    "tags": chunk_tags,
                    "project": meta.get("project"),
                    "timestamp": meta.get("timestamp", "unknown"),
                })
                if len(related) >= top_k:
                    break

        return related

    # ── CRUD helpers ─────────────────────────────────────────────────────────

    def get_count(self) -> int:
        return self.collection.count()

    def clear_collection(self):
        self.client.delete_collection(name=COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
        )

    def list_memories(self, limit: int = 50, offset: int = 0) -> list[dict]:
        try:
            results = self.collection.get(
                limit=limit,
                offset=offset,
                include=["documents", "metadatas"],
            )
            memories: list[dict] = []
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"]):
                    doc = (results["documents"][i] if results["documents"] else "").strip()
                    meta = results["metadatas"][i] if results["metadatas"] else {}
                    tags_raw = meta.get("tags", "")
                    tags = [t for t in tags_raw.split(",") if t] if isinstance(tags_raw, str) else []
                    memories.append({
                        "id": doc_id,
                        "text": doc[:300] + "..." if len(doc) > 300 else doc,
                        "full_text": doc,
                        "source": meta.get("source", "unknown"),
                        "source_type": meta.get("source_type", "unknown"),
                        "timestamp": meta.get("timestamp", "unknown"),
                        "project": meta.get("project"),
                        "tags": tags,
                        "language": meta.get("language"),
                        "document_type": meta.get("document_type"),
                    })
            return memories
        except Exception:
            return []

    def delete_memory(self, doc_id: str) -> bool:
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def get_all_metadata(self) -> list[dict]:
        """Return all stored metadata dicts (for explorer endpoints)."""
        try:
            count = self.collection.count()
            if count == 0:
                return []
            results = self.collection.get(
                limit=count,
                include=["metadatas"],
            )
            return results.get("metadatas", []) or []
        except Exception:
            return []


# ── Internal helpers ─────────────────────────────────────────────────────────

def _tokenise(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, min 2 chars."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 2]


def _keyword_score(query_terms: list[str], document: str) -> float:
    """
    Lightweight TF-IDF-inspired keyword score (no external deps).

    Score = (matched unique terms) / (total unique query terms)
    Boosted by in-document term frequency up to a log ceiling.
    """
    if not query_terms:
        return 0.0
    doc_tokens = _tokenise(document)
    doc_freq: dict[str, int] = {}
    for t in doc_tokens:
        doc_freq[t] = doc_freq.get(t, 0) + 1

    matched = 0.0
    for term in query_terms:
        if term in doc_freq:
            tf_boost = min(1.0, math.log1p(doc_freq[term]) / math.log1p(10))
            matched += 0.5 + 0.5 * tf_boost  # partial credit even for single occurrence

    return min(1.0, matched / len(query_terms))
