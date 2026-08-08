"""
tools/search_tool.py — SearchContextTool for OmniContext agent interface.

Exposes hybrid retrieval as a callable agent tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all OmniContext agent tools."""

    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        ...

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class SearchContextTool(BaseTool):
    """
    Searches the OmniContext vector store using hybrid retrieval.

    Combines semantic similarity (0.7) and keyword scoring (0.3)
    with optional metadata filters.
    """

    name = "search_context"
    description = (
        "Search the OmniContext memory store for relevant information. "
        "Supports filtering by source type, project, and tags. "
        "Returns relevance-ranked chunks with source citations."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "source_type": {
                "type": "string",
                "description": "Filter by source type: code, pdf, web, clipboard, note",
                "enum": ["code", "pdf", "web", "clipboard", "note"],
            },
            "project": {
                "type": "string",
                "description": "Filter by project name",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by tags (all must match)",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def execute(
        self,
        query: str,
        source_type: str | None = None,
        project: str | None = None,
        tags: list[str] | None = None,
        top_k: int = 5,
        **kwargs,
    ) -> dict:
        from memory.vector_store import MemoryStore
        store = MemoryStore()
        results = store.search_memories_hybrid(
            query=query,
            source_type=source_type,
            tags=tags,
            project=project,
            top_k=top_k,
        )
        return {
            "tool": self.name,
            "query": query,
            "total": len(results),
            "results": [
                {
                    "id": r["id"],
                    "preview": r["preview"],
                    "source": r["source"],
                    "source_type": r["source_type"],
                    "relevance": r["final_score"],
                    "project": r.get("project"),
                    "tags": r.get("tags", []),
                }
                for r in results
            ],
        }
