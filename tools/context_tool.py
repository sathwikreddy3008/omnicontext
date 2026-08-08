"""tools/context_tool.py — ContextTool for OmniContext agent interface."""
from __future__ import annotations
from tools.search_tool import BaseTool


class ContextTool(BaseTool):
    """Returns aggregated statistics and metadata about the OmniContext store."""

    name = "get_context_stats"
    description = (
        "Retrieve aggregated statistics about the OmniContext memory store: "
        "source types, top projects, top languages, top tags, and total chunks."
    )
    input_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, **kwargs) -> dict:
        from memory.vector_store import MemoryStore
        from collections import Counter
        store = MemoryStore()
        all_meta = store.get_all_metadata()
        type_counts: Counter = Counter()
        lang_counts: Counter = Counter()
        proj_counts: Counter = Counter()
        tag_counts: Counter = Counter()

        for m in all_meta:
            type_counts[m.get("source_type", "unknown")] += 1
            if m.get("language"):
                lang_counts[m["language"]] += 1
            if m.get("project"):
                proj_counts[m["project"]] += 1
            for t in (m.get("tags") or "").split(","):
                if t:
                    tag_counts[t] += 1

        return {
            "tool": self.name,
            "total_chunks": len(all_meta),
            "source_types": dict(type_counts.most_common()),
            "top_languages": dict(lang_counts.most_common(5)),
            "top_projects": dict(proj_counts.most_common(5)),
            "top_tags": dict(tag_counts.most_common(10)),
        }
