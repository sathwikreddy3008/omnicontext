"""
ingestion/pdf_parser.py — OmniContext PDF ingestion with semantic chunking.

Reads each page, concatenates them into a full-document text, then applies
chunk_text_semantically() so context boundaries are preserved across pages.
"""

from __future__ import annotations

import os
from pathlib import Path

from pypdf import PdfReader

from memory.models import MemoryMetadata
from ingestion.chunking import chunk_text_semantically


class PdfParser:
    def __init__(self, vector_store):
        self.store = vector_store

    def ingest_pdf(self, file_path: str) -> int:
        """
        Parse a PDF and store semantically chunked text in the vector database.

        Returns the number of chunks successfully stored.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        if not file_path.lower().endswith(".pdf"):
            raise ValueError("File must be a PDF document.")

        try:
            reader = PdfReader(file_path)
            file_name = os.path.basename(file_path)
            source_str = f"pdf:{file_name}"

            # Concatenate all pages into one document for better semantic splitting
            full_text_parts: list[str] = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    full_text_parts.append(f"--- Page {i + 1} ---\n{text.strip()}")

            if not full_text_parts:
                raise ValueError("No extractable text found in the PDF. It may be an image-based scan.")

            full_text = "\n\n".join(full_text_parts)
            checksum = MemoryMetadata.compute_checksum(full_text)

            # Semantic chunking across the whole document
            chunks = chunk_text_semantically(
                text=full_text,
                source=source_str,
                max_chars=1800,
                overlap=200,
            )

            chunks_stored = 0
            for chunk in chunks:
                meta = MemoryMetadata(
                    source=source_str,
                    source_type="pdf",
                    path=file_path,
                    checksum=checksum,
                    heading=chunk.heading,
                    chunk_index=chunk.chunk_index,
                    total_chunks=chunk.total_chunks,
                    ingested_from="pdf_parser",
                    document_type="documentation",
                )

                chunk_id = f"{Path(file_path).stem}_chunk_{chunk.chunk_index}"
                self.store.add_memory(
                    text=chunk.text,
                    source=source_str,
                    doc_id=chunk_id,
                    metadata=meta,
                )
                chunks_stored += 1

            return chunks_stored

        except Exception as e:
            raise Exception(f"Failed to parse PDF: {e}") from e
