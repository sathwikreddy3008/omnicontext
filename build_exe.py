import PyInstaller.__main__
from pathlib import Path
import os

print("Starting OmniContext executable build process...")

base_dir = Path(__file__).parent.absolute()
ui_dir = base_dir / "ui"

if not ui_dir.exists():
    print(f"Error: UI directory not found at {ui_dir}")
    exit(1)

# PyInstaller Arguments
args = [
    'desktop_app.py',            # Entry point script
    '--name=OmniContext',        # Name of the executable
    '--onedir',                  # Create a one-folder bundle (faster startup than onefile)
    '--noconsole',               # Hide the terminal window
    '--noconfirm',               # Overwrite existing build
    '--clean',                   # Clean cache
    f'--add-data={ui_dir};ui',   # Bundle the UI folder (semicolon for Windows)
    
    # Uvicorn & FastAPI dynamic imports that Pyinstaller often misses
    '--hidden-import=uvicorn.logging',
    '--hidden-import=uvicorn.loops',
    '--hidden-import=uvicorn.loops.auto',
    '--hidden-import=uvicorn.protocols',
    '--hidden-import=uvicorn.protocols.http',
    '--hidden-import=uvicorn.protocols.http.auto',
    '--hidden-import=uvicorn.protocols.websockets',
    '--hidden-import=uvicorn.protocols.websockets.auto',
    '--hidden-import=uvicorn.lifespan',
    '--hidden-import=uvicorn.lifespan.on',
    
    # ChromaDB hidden imports
    '--hidden-import=chromadb',
    '--hidden-import=chromadb.api.segment',
]

print(f"Running PyInstaller with arguments: {args}")

PyInstaller.__main__.run(args)

print("\n✅ Build complete! You can find your executable in the 'dist/OmniContext/' folder.")
