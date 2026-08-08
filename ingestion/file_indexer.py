"""
ingestion/file_indexer.py — OmniContext file ingestion with semantic chunking.

Uses:
  - chunk_text_semantically() for context-preserving splits
  - extract_metadata() for automatic project/tag/language enrichment
  - MemoryMetadata for structured, typed metadata storage
"""

from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console

from memory.vector_store import MemoryStore
from memory.models import MemoryMetadata
from ingestion.chunking import chunk_text_semantically
from ingestion.metadata_extractor import extract_metadata

console = Console()

IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "data", "chromadb", "dist", "build", ".agents"}
VALID_EXTENSIONS = {".py", ".md", ".txt", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".sh", ".sql"}


class FileIndexer:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def ingest_directory(self, target_path: str):
        path = Path(target_path)
        if not path.exists() or not path.is_dir():
            console.print(f"[bold red]Error:[/bold red] '{target_path}' is not a valid directory.")
            return

        console.print(f"[cyan]Scanning directory: {path.absolute()}[/cyan]")
        files_indexed = 0
        chunks_added = 0

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() not in VALID_EXTENSIONS:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    console.print(f"[dim yellow]Skipping {file_path.name}: {e}[/dim yellow]")
                    continue

                # ── Automatic metadata enrichment ────────────────────────────
                extracted = extract_metadata(path=file_path, text=content)
                checksum = MemoryMetadata.compute_checksum(content)
                rel_path = str(file_path.relative_to(path))
                source_str = f"file:{rel_path}"

                # ── Semantic chunking ────────────────────────────────────────
                chunks = chunk_text_semantically(
                    text=content,
                    source=source_str,
                )

                for chunk in chunks:
                    chunk_id = f"{file_path.absolute()}_chunk_{chunk.chunk_index}"

                    meta = MemoryMetadata(
                        source=source_str,
                        source_type="code" if extracted.get("document_type") == "code" else extracted.get("document_type", "code"),
                        path=str(file_path.absolute()),
                        checksum=checksum,
                        language=extracted.get("language"),
                        project=extracted.get("project"),
                        repository=extracted.get("repository"),
                        tags=extracted.get("tags", []),
                        document_type=extracted.get("document_type"),
                        heading=chunk.heading,
                        chunk_index=chunk.chunk_index,
                        total_chunks=chunk.total_chunks,
                        ingested_from="file_indexer",
                    )

                    self.memory_store.add_memory(
                        text=chunk.text,
                        source=source_str,
                        doc_id=chunk_id,
                        metadata=meta,
                    )
                    chunks_added += 1

                files_indexed += 1
                console.print(
                    f"[dim green]Indexed:[/dim green] {rel_path} "
                    f"({len(chunks)} chunks"
                    + (f", {extracted.get('language', '')}" if extracted.get("language") else "")
                    + ")"
                )

        console.print(f"\n[bold green]Ingestion Complete![/bold green]")
        console.print(f"Indexed {files_indexed} files into {chunks_added} vector chunks.")
