import time
import pyperclip
import threading
from memory.vector_store import MemoryStore
from rich.console import Console

console = Console()

class ClipboardMonitor:
    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store
        self.last_copied = ""
        self.is_running = False
        self.thread = None

    def _monitor_loop(self):
        console.print("[cyan]Clipboard monitor started. Listening for copies...[/cyan]")
        while self.is_running:
            try:
                current_text = pyperclip.paste()
                # If text changed and isn't empty, save it
                if current_text != self.last_copied and current_text.strip():
                    self.last_copied = current_text
                    # Simple heuristic: don't save very small snippets unless they look like code/commands
                    if len(current_text) > 10: 
                        self.memory_store.add_memory(current_text, source="clipboard")
                        console.print(f"[dim green]Saved to memory: {current_text[:50]}...[/dim green]")
            except pyperclip.PyperclipException:
                pass # Ignore errors reading clipboard (sometimes locked)
            
            time.sleep(1.0) # Check every second

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            console.print("[yellow]Clipboard monitor stopped.[/yellow]")
