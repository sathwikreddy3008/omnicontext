"""
ingestion/metadata_extractor.py — Automatic metadata enrichment for OmniContext.

Extracts:
  - project name from file path heuristics
  - repository root via .git detection
  - technology tags from content keywords
  - top-level headings from Markdown
  - document type (code | documentation | configuration | data | script)
  - programming language from file extension
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from memory.models import MemoryMetadata, LANGUAGE_MAP


# ── Technology keyword → tag mapping ─────────────────────────────────────────

TECH_KEYWORDS: dict[str, list[str]] = {
    "fastapi":      ["FastAPI", "fastapi", "APIRouter", "@app.get", "@app.post"],
    "kafka":        ["kafka", "KafkaProducer", "KafkaConsumer", "confluent_kafka", "aiokafka"],
    "pyspark":      ["pyspark", "SparkSession", "SparkContext", "RDD", "DataFrame.rdd"],
    "docker":       ["Dockerfile", "docker-compose", "docker run", "FROM ", "ENTRYPOINT"],
    "sql":          ["SELECT ", "INSERT INTO", "CREATE TABLE", "ALTER TABLE", "JOIN ", "WHERE "],
    "rag":          ["RAG", "retrieval augmented", "vector store", "ChromaDB", "chroma", "embedding"],
    "llm":          ["ollama", "openai", "anthropic", "llm", "LLM", "language model", "prompt"],
    "redis":        ["redis", "Redis", "RedisClient", "aioredis"],
    "clickhouse":   ["clickhouse", "ClickHouse", "clickhouse_driver"],
    "airflow":      ["airflow", "DAG", "PythonOperator", "BashOperator"],
    "pytorch":      ["torch", "nn.Module", "DataLoader", "optim."],
    "tensorflow":   ["tensorflow", "tf.keras", "tf.data"],
    "pandas":       ["import pandas", "pd.DataFrame", "pd.read_csv"],
    "react":        ["import React", "useState", "useEffect", "jsx"],
    "kubernetes":   ["apiVersion:", "kubectl", "kubernetes", "k8s"],
    "chromadb":     ["chromadb", "ChromaDB", "chroma_client", "get_or_create_collection"],
    "python":       ["import ", "def ", "class ", "if __name__"],
}

# Configuration file names / patterns
CONFIG_PATTERNS = {
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    "Dockerfile", "docker-compose",
}

# Script file names / patterns
SCRIPT_PATTERNS = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"}

# Documentation file extensions
DOC_PATTERNS = {".md", ".rst", ".txt", ".adoc"}

# Data file extensions
DATA_PATTERNS = {".json", ".csv", ".tsv", ".parquet", ".xml", ".ndjson"}


def extract_metadata(
    path: Optional[str | Path] = None,
    text: str = "",
) -> dict:
    """
    Analyse a file path and its textual content to produce enriched metadata.

    Returns a dict compatible with MemoryMetadata field names.
    """
    result: dict = {}

    # ── Language & document type from path ───────────────────────────────────
    if path:
        p = Path(path)
        ext = p.suffix.lower()
        stem = p.stem.lower()
        name = p.name

        lang = LANGUAGE_MAP.get(ext)
        if lang:
            result["language"] = lang

        result["document_type"] = _classify_document(name, ext, stem)
        result["path"] = str(p)

        # ── Project name heuristic ───────────────────────────────────────────
        project = _infer_project(p)
        if project:
            result["project"] = project

        # ── Repository root detection ────────────────────────────────────────
        repo = _find_repository_name(p)
        if repo:
            result["repository"] = repo

    # ── Technology tags from content ─────────────────────────────────────────
    tags = _extract_tags(text, result.get("language"))
    if tags:
        result["tags"] = tags

    # ── Top-level heading from Markdown ─────────────────────────────────────
    if path and Path(path).suffix.lower() == ".md":
        heading = _extract_first_heading(text)
        if heading:
            result["heading"] = heading

    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _classify_document(name: str, ext: str, stem: str) -> str:
    """Infer document type from file extension and name."""
    if ext in DOC_PATTERNS:
        return "documentation"
    if ext in DATA_PATTERNS:
        return "data"
    if ext in SCRIPT_PATTERNS or stem in {"makefile", "rakefile", "justfile"}:
        return "script"
    if ext in CONFIG_PATTERNS or any(p in name.lower() for p in CONFIG_PATTERNS):
        return "configuration"
    # Code: any programming language extension
    if ext in LANGUAGE_MAP:
        return "code"
    return "unknown"


def _infer_project(path: Path) -> Optional[str]:
    """
    Walk up the directory tree to find a plausible project name.

    Strategy:
    1. If a pyproject.toml / setup.py / package.json exists nearby → use parent dir
    2. Otherwise use the first meaningful ancestor directory (not common names)
    """
    SKIP = {"src", "lib", "app", "core", "main", "test", "tests", "docs", "scripts"}

    # Check for project root markers
    current = path.parent
    for _ in range(6):  # search up to 6 levels
        markers = {"pyproject.toml", "setup.py", "package.json", "Cargo.toml", "go.mod"}
        if any((current / m).exists() for m in markers):
            return _slug(current.name)
        if (current / ".git").exists():
            return _slug(current.name)
        current = current.parent
        if current == current.parent:
            break

    # Fallback: pick first ancestor not in SKIP
    for part in reversed(path.parts[:-1]):
        if part.lower() not in SKIP and not part.startswith(".") and len(part) > 2:
            return _slug(part)
    return None


def _find_repository_name(path: Path) -> Optional[str]:
    """Locate the nearest .git directory and return the parent folder name."""
    current = path.parent
    for _ in range(8):
        if (current / ".git").exists():
            return _slug(current.name)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _extract_tags(text: str, language: Optional[str] = None) -> list[str]:
    """Return detected technology tags present in `text`."""
    tags: set[str] = set()
    if language:
        tags.add(language)
    for tag, keywords in TECH_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                tags.add(tag)
                break
    return sorted(tags)


def _extract_first_heading(text: str) -> Optional[str]:
    """Return the first H1 or H2 heading from a Markdown document."""
    m = re.search(r"^#{1,2}\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _slug(name: str) -> str:
    """Convert a directory name to a lowercase slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
