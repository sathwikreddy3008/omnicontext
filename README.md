# 🧠 Second Brain (OmniContext)

**Second Brain** is a personal, local-first Retrieval-Augmented Generation (RAG) application that acts as your digital memory engine. It seamlessly captures your clipboard history, local files, and web snippets, stores them in a local vector database, and allows you to query your digital footprint using local Large Language Models (LLMs) with complete privacy.

---

## 🌟 Key Features

- **100% Local & Private:** Your data never leaves your machine. Uses `ChromaDB` for local vector storage and `Ollama` for local LLM inference.
- **Continuous Ingestion:** Background daemon automatically captures and indexes clipboard copies longer than 10 characters.
- **Live Directory Watching:** Automatically tracks and indexes changes in your local file directories.
- **Multiple User Interfaces:** 
  - **Terminal CLI:** Fast and aesthetic CLI built with `rich`.
  - **Web UI:** Interactive web interface powered by FastAPI.
  - **Native Desktop App:** A discrete system-tray app with global hotkeys (`Ctrl+Alt+Space`) to access your second brain from anywhere.
- **Intelligent Contextual Queries:** Ask questions about things you saw, copied, or worked on days ago, and your Second Brain will fetch the context and generate an answer.

---

## 🏗 Architecture

1. **Memory & Vector Store (`memory/`)**
   - **Database:** ChromaDB (`~/.second_brain/data/chromadb`)
   - **Embeddings:** `all-MiniLM-L6-v2` via `SentenceTransformers`
2. **LLM Inference Engine (`inference/`)**
   - **Model:** `phi3` (default) via local Ollama.
   - **Memory:** Retains the last 10 messages for conversation context.
3. **Data Ingestion (`ingestion/`)**
   - Clipboard Monitor (`pyperclip`)
   - Directory Watcher 
   - PDF Parser, Web Scraper, and File Indexer.
4. **Interfaces (`core/` & Root scripts)**
   - API Server using FastAPI
   - Native wrappers using `pywebview` and `pystray`.

---

## 🚀 Installation & Setup

### Prerequisites

1. **Python 3.8+**
2. **Ollama:** You must have [Ollama](https://ollama.com/) installed and running locally.
   - Pull the default model: 
     ```bash
     ollama run phi3
     ```

### Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sathwikreddy3008/-Second-Brain.git
   cd -Second-Brain
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(We recommend using a virtual environment like `.venv`)*

---

## 💻 Usage

The application provides a comprehensive Command Line Interface (CLI).

```bash
# Start the clipboard daemon (runs in background, saves copied text)
python cli.py listen

# Start the Web UI and Live Directory Watcher
python cli.py serve

# Start the Native Desktop App (System Tray + Global Hotkey Ctrl+Alt+Space)
python cli.py desktop

# Query your second brain directly from the terminal
python cli.py ask "What did I copy about the machine learning model?"

# Ingest a specific directory of files into your brain
python cli.py ingest /path/to/your/notes

# View statistics about your stored memories
python cli.py stats

# Clear all memories (Warning: Irreversible)
python cli.py clear
```

---

## ⚙️ Configuration

You can tweak the default configurations in `core/config.py`:
- **Models:** Switch the LLM to `llama3` if you have a powerful GPU.
- **Data Persistence:** Default directory is `~/.second_brain`.

---

## 🛡 Privacy Commitment

Second Brain is built on the philosophy that your thoughts and digital context belong to you. By utilizing completely local embeddings and local inference, there is absolutely zero telemetry or cloud transmission of your personal data.
