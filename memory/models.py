"""
memory/models.py — OmniContext metadata models.

Defines the canonical MemoryMetadata Pydantic model used across all
ingestion, retrieval, and API layers.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator

# ── Source type constants ────────────────────────────────────────────────────

SOURCE_TYPE_MAP: dict[str, str] = {
    "file":      "code",
    "pdf":       "pdf",
    "web":       "web",
    "clipboard": "clipboard",
    "manual":    "note",
    "note":      "note",
}

# Extension → programming language
LANGUAGE_MAP: dict[str, str] = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".java": "java",
    ".go":   "go",
    ".rs":   "rust",
    ".cpp":  "cpp",
    ".c":    "c",
    ".cs":   "csharp",
    ".rb":   "ruby",
    ".php":  "php",
    ".sh":   "shell",
    ".sql":  "sql",
    ".r":    "r",
    ".scala": "scala",
    ".kt":   "kotlin",
    ".swift": "swift",
    ".yaml": "yaml",
    ".yml":  "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md":   "markdown",
    ".html": "html",
    ".css":  "css",
}


class MemoryMetadata(BaseModel):
    """Canonical metadata for every chunk stored in the vector database."""

    source: str
    source_type: str = "unknown"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owner: str = "sathwik"

    # Provenance
    project: Optional[str] = None
    repository: Optional[str] = None
    language: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    path: Optional[str] = None
    checksum: Optional[str] = None

    # Versioning & chunking
    version: int = 1
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    ingested_from: Optional[str] = None

    # Document classification
    document_type: Optional[str] = None   # code | documentation | configuration | data | script
    heading: Optional[str] = None         # top-level heading of the chunk (for markdown)

    @model_validator(mode="after")
    def _auto_detect_source_type(self) -> "MemoryMetadata":
        """Infer source_type from the source prefix if not explicitly set."""
        if self.source_type == "unknown":
            for prefix, stype in SOURCE_TYPE_MAP.items():
                if self.source.startswith(prefix):
                    self.source_type = stype
                    break
        return self

    # ── Class-level helpers ──────────────────────────────────────────────────

    @classmethod
    def detect_language(cls, file_path: str | Path) -> Optional[str]:
        """Return language name from file extension."""
        ext = Path(file_path).suffix.lower()
        return LANGUAGE_MAP.get(ext)

    @classmethod
    def compute_checksum(cls, content: str | bytes) -> str:
        """MD5 checksum of text or binary content."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.md5(content).hexdigest()

    def to_chroma_dict(self) -> dict:
        """Flatten to a ChromaDB-compatible metadata dict (no None values, no lists)."""
        raw = self.model_dump()
        result: dict = {}
        for k, v in raw.items():
            if v is None:
                continue
            if isinstance(v, list):
                # ChromaDB metadata values must be str/int/float/bool
                result[k] = ",".join(str(i) for i in v) if v else ""
            else:
                result[k] = v
        return result

    @classmethod
    def from_chroma_dict(cls, d: dict) -> "MemoryMetadata":
        """Reconstruct from a ChromaDB metadata dict."""
        data = dict(d)
        # Re-hydrate comma-separated tag strings
        if "tags" in data and isinstance(data["tags"], str):
            data["tags"] = [t for t in data["tags"].split(",") if t]
        return cls(**data)
