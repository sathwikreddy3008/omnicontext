import argparse
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core.config import DATA_DIR
from memory.vector_store import MemoryStore
from ingestion.clipboard_monitor import ClipboardMonitor
from inference.llm_engine import BrainEngine
from ingestion.file_indexer import FileIndexer
from ingestion.directory_watcher import LiveWatcher
from desktop_app import launch_desktop_app
import uvicorn
import threading

console = Console()

def print_banner():
    banner = """
    🧠 [bold blue]Second Brain[/bold blue] 
    [dim]Your Private, Local-First AI Memory Engine[/dim]
    """
    console.print(Panel(banner, border_style="blue", expand=False))

def start_daemon():
    print_banner()
    console.print(f"[dim]Data directory: {DATA_DIR}[/dim]")
    
    try:
        store = MemoryStore()
        monitor = ClipboardMonitor(store)
        monitor.start()
        
        console.print("[bold green]Clipboard Daemon is running.[/bold green]")
        console.print("Press Ctrl+C to stop.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down daemon...[/yellow]")
        if 'monitor' in locals():
            monitor.stop()
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Error starting daemon:[/bold red] {e}")
        sys.exit(1)

def run_server():
    print_banner()
    console.print("[bold cyan]Starting Second Brain Web Server...[/bold cyan]")
    console.print("🌐 UI available at: [bold green]http://localhost:8000[/bold green]")
    
    # Start live directory watcher in background
    watcher = LiveWatcher(".")
    watcher.start()
    
    try:
        # Run FastAPI
        uvicorn.run("core.server:app", host="0.0.0.0", port=8000, log_level="warning")
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()

def query_brain(query_text: str):
    console.print(f"🤔 [bold]Searching memory for:[/bold] '{query_text}'...")
    
    store = MemoryStore()
    context = store.search_memories(query_text)
    
    if not context:
        console.print("[yellow]No relevant memories found in your local vector database.[/yellow]")
        return

    console.print(Panel(context, title="Retrieved Context", border_style="dim", expand=False))
    
    console.print("🤖 [bold]Asking local LLM...[/bold]")
    engine = BrainEngine()
    answer = engine.ask(query_text, context)
    
    console.print(Panel(Markdown(answer), title="Second Brain Output", border_style="green", expand=False))

def ingest_path(path: str):
    store = MemoryStore()
    indexer = FileIndexer(store)
    indexer.ingest_directory(path)

def print_stats():
    store = MemoryStore()
    count = store.get_count()
    console.print(f"\n🧠 [bold blue]Brain Statistics[/bold blue]")
    console.print(f"Total memories (chunks) stored: [bold green]{count}[/bold green]\n")

def clear_brain():
    console.print("[bold red]Warning:[/bold red] This will permanently delete all memories.")
    confirm = console.input("Are you sure? (y/N): ")
    if confirm.lower() == 'y':
        store = MemoryStore()
        store.clear_collection()
        console.print("[bold green]Brain cleared successfully.[/bold green]")
    else:
        console.print("Aborted.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OmniContext Second Brain CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Command: listen
    listen_parser = subparsers.add_parser("listen", help="Start the clipboard daemon")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Start the Web UI and Live Directory Watcher")

    # Command: desktop
    desktop_parser = subparsers.add_parser("desktop", help="Start the Native Desktop App")

    # Command: ask
    ask_parser = subparsers.add_parser("ask", help="Query your second brain")
    ask_parser.add_argument("query", type=str, help="The question you want to ask")

    # Command: ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a directory of files into the brain")
    ingest_parser.add_argument("path", type=str, help="Path to the directory")

    # Command: stats
    subparsers.add_parser("stats", help="View brain statistics")

    # Command: clear
    subparsers.add_parser("clear", help="Wipe all memories from the brain")

    args = parser.parse_args()

    if args.command == "listen":
        start_daemon()
    elif args.command == "serve":
        run_server()
    elif args.command == "desktop":
        launch_desktop_app()
    elif args.command == "ask":
        query_brain(args.query)
    elif args.command == "ingest":
        ingest_path(args.path)
    elif args.command == "stats":
        print_stats()
    elif args.command == "clear":
        clear_brain()
    else:
        parser.print_help()
