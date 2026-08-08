"""tools/note_tool.py — NoteTool for OmniContext agent interface."""
from __future__ import annotations
from tools.search_tool import BaseTool


class NoteTool(BaseTool):
    """Saves a manual note or thought into the OmniContext memory store."""

    name = "save_note"
    description = (
        "Save a manual note, observation, or thought into OmniContext. "
        "The note is embedded and stored as a searchable memory."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The note text to save",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags to attach to the note",
            },
            "project": {
                "type": "string",
                "description": "Optional project to associate the note with",
            },
        },
        "required": ["text"],
    }

    async def execute(
        self,
        text: str,
        tags: list[str] | None = None,
        project: str | None = None,
        **kwargs,
    ) -> dict:
        from memory.vector_store import MemoryStore
        from memory.models import MemoryMetadata
        store = MemoryStore()
        meta = MemoryMetadata(
            source="manual_note",
            source_type="note",
            tags=tags or [],
            project=project,
            ingested_from="note_tool",
        )
        success = store.add_memory(text=text, source="manual_note", metadata=meta)
        return {
            "tool": self.name,
            "success": success,
            "total_chunks": store.get_count(),
        }
