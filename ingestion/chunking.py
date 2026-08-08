"""
ingestion/chunking.py — Semantic text chunker for OmniContext.

Splitting strategy (in priority order):
  1. Markdown headings  — split on ## / ### level headings
  2. Paragraph breaks   — blank-line-separated blocks
  3. Code-block aware   — never splits inside a fenced ``` block
  4. Sliding window     — fallback for long paragraphs / prose

Returns a list of TextChunk dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TextChunk:
    text: str
    heading: Optional[str] = None   # nearest markdown heading, if any
    chunk_index: int = 0
    total_chunks: int = 1
    source: str = ""


def chunk_text_semantically(
    text: str,
    source: str = "",
    max_chars: int = 1800,
    overlap: int = 200,
) -> list[TextChunk]:
    """
    Split `text` into semantically coherent chunks.

    Parameters
    ----------
    text       : raw input text
    source     : origin label (used only to populate TextChunk.source)
    max_chars  : soft upper bound on chunk size in characters
    overlap    : character overlap between adjacent sliding-window chunks
    """
    if not text or not text.strip():
        return []

    # ── Step 1: Try markdown heading split ───────────────────────────────────
    heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    heading_positions = [(m.start(), m.group(0), m.group(2)) for m in heading_pattern.finditer(text)]

    if heading_positions:
        sections = _split_by_headings(text, heading_positions, max_chars, overlap)
    else:
        sections = _split_by_paragraphs(text, max_chars, overlap)

    # Label chunks
    total = len(sections)
    chunks: list[TextChunk] = []
    for idx, (chunk_text, heading) in enumerate(sections):
        if chunk_text.strip():
            chunks.append(TextChunk(
                text=chunk_text.strip(),
                heading=heading,
                chunk_index=idx,
                total_chunks=total,
                source=source,
            ))

    # Renumber total after filtering empty
    total = len(chunks)
    for i, c in enumerate(chunks):
        c.chunk_index = i
        c.total_chunks = total

    return chunks


# ── Internal splitting helpers ────────────────────────────────────────────────

def _split_by_headings(
    text: str,
    heading_positions: list[tuple[int, str, str]],
    max_chars: int,
    overlap: int,
) -> list[tuple[str, Optional[str]]]:
    """
    Produce (section_text, heading_label) pairs split at heading boundaries.
    Sections that exceed max_chars are further split by paragraphs.
    """
    sections: list[tuple[str, Optional[str]]] = []

    # Build boundary list: (start_pos, heading_text)
    boundaries = [(pos, h) for pos, _, h in heading_positions]
    boundaries.append((len(text), None))  # sentinel

    current_heading: Optional[str] = None
    prev_pos = 0

    for start_pos, heading_text in boundaries:
        section = text[prev_pos:start_pos]
        if section.strip():
            if len(section) <= max_chars:
                sections.append((section, current_heading))
            else:
                # Further split large sections
                sub = _split_by_paragraphs(section, max_chars, overlap)
                for chunk_text, _ in sub:
                    sections.append((chunk_text, current_heading))
        prev_pos = start_pos
        current_heading = heading_text

    return sections


def _split_by_paragraphs(
    text: str,
    max_chars: int,
    overlap: int,
) -> list[tuple[str, Optional[str]]]:
    """
    Split text on double-newline paragraph breaks.
    Consecutive short paragraphs are merged until max_chars is approached.
    Code blocks (``` fences) are kept intact.
    """
    # Protect code blocks from splitting
    protected, placeholders = _protect_code_blocks(text)

    paragraphs = re.split(r"\n{2,}", protected)
    sections: list[tuple[str, Optional[str]]] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_len = len(para)

        if current_len + para_len > max_chars and current_parts:
            chunk = "\n\n".join(current_parts)
            sections.append((_restore_code_blocks(chunk, placeholders), None))
            # Overlap: keep tail of previous chunk
            overlap_text = chunk[-overlap:] if len(chunk) > overlap else chunk
            current_parts = [overlap_text, para]
            current_len = len(overlap_text) + para_len
        else:
            current_parts.append(para)
            current_len += para_len

    if current_parts:
        chunk = "\n\n".join(current_parts)
        sections.append((_restore_code_blocks(chunk, placeholders), None))

    # If even a single paragraph exceeds max_chars, do a final sliding-window pass
    final: list[tuple[str, Optional[str]]] = []
    for chunk_text, heading in sections:
        if len(chunk_text) > max_chars * 1.5:
            for sub in _sliding_window(chunk_text, max_chars, overlap):
                final.append((sub, heading))
        else:
            final.append((chunk_text, heading))

    return final


def _protect_code_blocks(text: str) -> tuple[str, dict[str, str]]:
    """Replace fenced code blocks with placeholder tokens."""
    placeholders: dict[str, str] = {}
    counter = 0

    def replacer(m: re.Match) -> str:
        nonlocal counter
        key = f"__CODEBLOCK_{counter}__"
        placeholders[key] = m.group(0)
        counter += 1
        return key

    protected = re.sub(r"```[\s\S]*?```", replacer, text)
    return protected, placeholders


def _restore_code_blocks(text: str, placeholders: dict[str, str]) -> str:
    for key, value in placeholders.items():
        text = text.replace(key, value)
    return text


def _sliding_window(text: str, max_chars: int, overlap: int) -> list[str]:
    """Hard sliding-window fallback for very long paragraphs."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start += max_chars - overlap
    return chunks
