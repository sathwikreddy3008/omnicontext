import os
from pathlib import Path

# ── Persistent storage ────────────────────────────────────────────────────────
# Uses ~/.omnicontext/ so data survives reinstalls and Docker volume mounts.
PERSISTENT_DIR = Path(os.environ.get("OMNICONTEXT_DATA_DIR", Path.home() / ".omnicontext"))
DATA_DIR = PERSISTENT_DIR / "data"
DB_DIR = DATA_DIR / "chromadb"

os.makedirs(DB_DIR, exist_ok=True)

# ── Model settings ────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
OLLAMA_MODEL = os.environ.get("OMNICONTEXT_MODEL", "phi3")  # Override via env var

# ── ChromaDB collection ───────────────────────────────────────────────────────
COLLECTION_NAME = "omnicontext_memory"
