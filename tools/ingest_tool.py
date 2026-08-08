"""tools/ingest_tool.py — IngestTool for OmniContext agent interface."""
from __future__ import annotations
from tools.search_tool import BaseTool


class IngestTool(BaseTool):
    """Ingests a local directory of files into the OmniContext memory store."""

    name = "ingest_directory"
    description = (
        "Ingest all supported files from a local directory into OmniContext. "
        "Automatically extracts metadata, chunks content, and stores embeddings."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the directory to ingest",
            },
        },
        "required": ["path"],
    }

    async def execute(self, path: str, **kwargs) -> dict:
        from memory.vector_store import MemoryStore
        from ingestion.file_indexer import FileIndexer
        store = MemoryStore()
        indexer = FileIndexer(store)
        before = store.get_count()
        indexer.ingest_directory(path)
        after = store.get_count()
        return {
            "tool": self.name,
            "path": path,
            "chunks_added": after - before,
            "total_chunks": after,
        }
