import threading
import time
import uvicorn
import webview
import os
from rich.console import Console
from ingestion.directory_watcher import LiveWatcher
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from pynput import keyboard

console = Console()

app_window = None
is_hidden = False
tray_icon = None
watcher = None

def run_api_server():
    """Run FastAPI in a background thread."""
    uvicorn.run("core.server:app", host="127.0.0.1", port=8000, log_level="error")

def create_tray_image():
    # Create a generic brain-like icon (pink circle on dark background)
    image = Image.new('RGB', (64, 64), color=(15, 23, 42))
    dc = ImageDraw.Draw(image)
    dc.ellipse((12, 12, 52, 52), fill=(236, 72, 153))
    return image

def show_window(icon, item):
    global is_hidden
    if app_window:
        app_window.show()
        is_hidden = False

def quit_app(icon, item):
    console.print("\n[yellow]Shutting down Second Brain...[/yellow]")
    if tray_icon:
        tray_icon.stop()
    if watcher:
        watcher.stop()
    if app_window:
        app_window.destroy()
    os._exit(0)  # Hard exit to kill FastAPI and hotkey threads

def toggle_window():
    global is_hidden
    if not app_window:
        return
    if is_hidden:
        app_window.show()
        is_hidden = False
    else:
        app_window.hide()
        is_hidden = True

def setup_tray():
    global tray_icon
    menu = pystray.Menu(
        item('Open Second Brain', show_window, default=True),
        item('Quit', quit_app)
    )
    tray_icon = pystray.Icon("second_brain", create_tray_image(), "Second Brain", menu)
    tray_icon.run()

def setup_hotkeys():
    # Global hotkey to toggle window visibility
    hotkey = keyboard.GlobalHotKeys({
        '<ctrl>+<alt>+<space>': toggle_window
    })
    hotkey.start()

def on_closing():
    global is_hidden
    app_window.hide()
    is_hidden = True
    return False # Cancel the actual close event so the app stays alive

def launch_desktop_app():
    global app_window, watcher

    # Start the Live Directory Watcher
    watcher = LiveWatcher(".")
    watcher.start()

    # Start the FastAPI server in a background thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()

    # Start Tray Icon in a background thread
    threading.Thread(target=setup_tray, daemon=True).start()

    # Start Global Hotkeys
    setup_hotkeys()

    # Wait a moment for the server to spin up
    time.sleep(1.5)

    console.print("\n[bold cyan]Starting Second Brain...[/bold cyan]")
    console.print("[green]System Tray mode active! Minimize to hide, or use Ctrl+Alt+Space to toggle.[/green]")
    
    # Create the native window
    app_window = webview.create_window(
        title="Second Brain",
        url="http://127.0.0.1:8000",
        width=1200,
        height=800,
        min_size=(900, 600),
        background_color="#0f172a"
    )
    
    # Override the close button behavior
    app_window.events.closing += on_closing
    
    # This blocks until the window is destroyed
    webview.start()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    launch_desktop_app()
