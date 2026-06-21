import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rich.console import Console

from memory.vector_store import MemoryStore
from ingestion.file_indexer import FileIndexer, IGNORE_DIRS, VALID_EXTENSIONS

console = Console()

class CodeWatcher(FileSystemEventHandler):
    def __init__(self, target_path: str):
        self.target_path = Path(target_path).absolute()
        self.store = MemoryStore()
        self.indexer = FileIndexer(self.store)
        
        # Debounce timer mapping: filepath -> timer
        self.timers = {}

    def is_valid_file(self, event) -> bool:
        if event.is_directory:
            return False
        
        path = Path(event.src_path)
        
        # Check extensions
        if path.suffix.lower() not in VALID_EXTENSIONS:
            return False
            
        # Check ignored dirs
        for part in path.parts:
            if part in IGNORE_DIRS:
                return False
                
        return True

    def process_file(self, filepath: str):
        try:
            path = Path(filepath)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            chunks = self.indexer._chunk_text(content)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{path.absolute()}_chunk_{i}"
                self.store.add_memory(
                    text=chunk,
                    source=f"file: {path.relative_to(self.target_path)}",
                    doc_id=chunk_id
                )
            console.print(f"[dim cyan]Live updated:[/dim cyan] {path.name} ({len(chunks)} chunks)")
        except Exception as e:
            console.print(f"[dim yellow]Live update failed for {Path(filepath).name}: {e}[/dim yellow]")

    def on_modified(self, event):
        if not self.is_valid_file(event):
            return
            
        filepath = event.src_path
        
        # Debounce logic: wait 1 second after last edit before indexing
        if filepath in self.timers:
            self.timers[filepath].cancel()
            
        timer = threading.Timer(1.0, self.process_file, args=[filepath])
        self.timers[filepath] = timer
        timer.start()

class LiveWatcher:
    def __init__(self, target_path: str = "."):
        self.target_path = target_path
        self.observer = Observer()
        self.is_running = False
        
    def start(self):
        if self.is_running: return
        
        event_handler = CodeWatcher(self.target_path)
        self.observer.schedule(event_handler, self.target_path, recursive=True)
        self.observer.start()
        self.is_running = True
        console.print(f"[green]Live Watcher active on {self.target_path}[/green]")
        
    def stop(self):
        if self.is_running:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            console.print("[yellow]Live Watcher stopped.[/yellow]")
