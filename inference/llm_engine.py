"""
inference/llm_engine.py — OmniContext LLM engine with citation-aware, trust-grounded responses.

ask() now returns a structured dict:
  {
    "answer": str,
    "confidence": float,
    "insufficient_context": bool,
    "used_sources": [{"index", "source", "score", "source_type", "project", "tags"}],
    "context_quality": {"is_sufficient", "chunk_count", "avg_score", "quality_level"}
  }

ask_stream() yields tokens, then yields a final JSON summary event.
"""

from __future__ import annotations

import json
from typing import Generator, Optional

import ollama

from core.config import OLLAMA_MODEL
from inference.prompt_builder import build_prompt_messages, parse_citations_from_answer
from inference.reliability import (
    build_grounded_response,
    evaluate_context_quality,
    calculate_confidence,
    extract_source_citations,
)


class BrainEngine:
    def __init__(self):
        self.model_name = OLLAMA_MODEL
        self.conversation_history: list[dict] = []

    def clear_history(self):
        self.conversation_history = []

    # ── Blocking ask ─────────────────────────────────────────────────────────

    def ask(self, query: str, context_results: list[dict] | str) -> dict:
        """
        Ask the LLM a question grounded in retrieved context.

        Parameters
        ----------
        context_results : either the list of hybrid-retrieval dicts
                          OR a plain string (legacy support)

        Returns a structured trust-grounded response dict.
        """
        results = _normalise_results(context_results)
        quality = evaluate_context_quality(results)

        # Short-circuit when there is no usable context
        if not quality["is_sufficient"] and not results:
            return build_grounded_response(
                answer="I don't have sufficient context to answer that question.",
                results=[],
                insufficient_context=True,
            )

        messages, citation_map = build_prompt_messages(
            query=query,
            results=results,
            conversation_history=self.conversation_history,
        )

        try:
            response = ollama.chat(model=self.model_name, messages=messages)
            raw_answer: str = response["message"]["content"]
        except Exception as e:
            return {
                "answer": f"Error connecting to local LLM: {e}\n\nMake sure Ollama is running (`ollama serve`).",
                "confidence": 0.0,
                "insufficient_context": True,
                "used_sources": [],
                "context_quality": quality,
            }

        used_sources = parse_citations_from_answer(raw_answer, citation_map)
        self._save_to_history(query, raw_answer)

        return build_grounded_response(
            answer=raw_answer,
            results=results,
            insufficient_context=not quality["is_sufficient"],
        ) | {"used_sources": used_sources}  # override with parsed citations

    # ── Streaming ask ────────────────────────────────────────────────────────

    def ask_stream(
        self,
        query: str,
        context_results: list[dict] | str,
    ) -> Generator[str, None, None]:
        """
        Stream LLM response tokens. After the final token, yields one JSON
        'meta' event containing confidence, citations, and context quality.

        Consumers should check event['type']:
          "token"  → text fragment
          "meta"   → final structured metadata
        """
        results = _normalise_results(context_results)
        quality = evaluate_context_quality(results)

        messages, citation_map = build_prompt_messages(
            query=query,
            results=results,
            conversation_history=self.conversation_history,
        )

        full_answer = ""
        try:
            for chunk in ollama.chat(
                model=self.model_name, messages=messages, stream=True
            ):
                token: str = chunk["message"]["content"]
                full_answer += token
                yield json.dumps({"type": "token", "token": token})

        except Exception as e:
            yield json.dumps({"type": "token", "token": f"Error: {e}"})
            yield json.dumps({
                "type": "meta",
                "confidence": 0.0,
                "used_sources": [],
                "context_quality": quality,
                "insufficient_context": True,
            })
            return

        # Parse citations from completed answer
        used_sources = parse_citations_from_answer(full_answer, citation_map)
        self._save_to_history(query, full_answer)

        grounded = build_grounded_response(
            answer=full_answer,
            results=results,
            insufficient_context=not quality["is_sufficient"],
        )

        yield json.dumps({
            "type": "meta",
            "confidence": grounded["confidence"],
            "used_sources": used_sources,
            "context_quality": quality,
            "insufficient_context": grounded["insufficient_context"],
        })

    # ── Private helpers ───────────────────────────────────────────────────────

    def _save_to_history(self, query: str, answer: str):
        """Keep last 10 turns in short-term conversation memory."""
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": answer})
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_results(context: list[dict] | str) -> list[dict]:
    """
    Accept either the new list[dict] format from hybrid retrieval
    or the legacy plain-string context (wraps it in a single dict).
    """
    if isinstance(context, list):
        return context
    if isinstance(context, str) and context.strip():
        return [{"content": context, "source": "legacy", "final_score": 0.6, "relevance": 0.6}]
    return []
