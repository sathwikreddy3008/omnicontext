import os
from pathlib import Path
from rich.console import Console
from memory.vector_store import MemoryStore

console = Console()

# Files we want to ignore
IGNORE_DIRS = {".git", ".venv", "node_modules", "__pycache__", "data", "chromadb"}
VALID_EXTENSIONS = {".py", ".md", ".txt", ".js", ".html", ".css", ".json"}

class FileIndexer:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 200):
        """Splits text into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
        return chunks

    def ingest_directory(self, target_path: str):
        path = Path(target_path)
        if not path.exists() or not path.is_dir():
            console.print(f"[bold red]Error:[/bold red] '{target_path}' is not a valid directory.")
            return

        console.print(f"[cyan]Scanning directory: {path.absolute()}[/cyan]")
        files_indexed = 0
        chunks_added = 0

        for root, dirs, files in os.walk(path):
            # Mutate dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in VALID_EXTENSIONS:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            
                        # Chunk the file
                        chunks = self._chunk_text(content)
                        for i, chunk in enumerate(chunks):
                            # Create a deterministic ID so we can update it later
                            chunk_id = f"{file_path.absolute()}_chunk_{i}"
                            self.memory_store.add_memory(
                                text=chunk, 
                                source=f"file: {file_path.relative_to(path)}", 
                                doc_id=chunk_id
                            )
                            chunks_added += 1
                        
                        files_indexed += 1
                        console.print(f"[dim green]Indexed:[/dim green] {file_path.relative_to(path)} ({len(chunks)} chunks)")
                    except Exception as e:
                        console.print(f"[dim yellow]Skipping {file_path.name}: {str(e)}[/dim yellow]")

        console.print(f"\n[bold green]Ingestion Complete![/bold green]")
        console.print(f"Indexed {files_indexed} files into {chunks_added} vector chunks.")
