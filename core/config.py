import os
from pathlib import Path

import sys

# Base directories
# For the DB, we want a persistent location, not the temp PyInstaller folder.
PERSISTENT_DIR = Path.home() / ".second_brain"
DATA_DIR = PERSISTENT_DIR / "data"
DB_DIR = DATA_DIR / "chromadb"

# Ensure data directory exists
os.makedirs(DB_DIR, exist_ok=True)

# Model Settings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
OLLAMA_MODEL = "phi3" # Fast model for CPU. Change to llama3 if you have a GPU.

# App Settings
COLLECTION_NAME = "second_brain_memory"
