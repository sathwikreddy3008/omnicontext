"""
inference/reliability.py — OmniContext Trust & Reliability Layer.

Provides:
  - evaluate_context_quality()  — assess retrieved chunk set
  - calculate_confidence()      — weighted confidence score
  - extract_source_citations()  — deduplicated sources with scores
  - build_grounded_response()   — structured response with fallback
"""

from __future__ import annotations

from typing import Any, Optional

# ── Thresholds ────────────────────────────────────────────────────────────────

MIN_RELEVANCE: float = 0.55       # minimum acceptable chunk relevance
MIN_CONTEXT_CHUNKS: int = 2       # minimum chunks needed for a confident answer
HIGH_CONFIDENCE_THRESHOLD: float = 0.75
LOW_CONFIDENCE_THRESHOLD: float = 0.45

FALLBACK_RESPONSE = (
    "I found some context but I'm not confident it directly answers your question. "
    "The retrieved information may be tangentially related. "
    "Please consider refining your query or ingesting more relevant content."
)


# ── Core functions ────────────────────────────────────────────────────────────

def evaluate_context_quality(results: list[dict]) -> dict:
    """
    Assess the quality of a set of retrieved chunks.

    Parameters
    ----------
    results : list of hybrid-retrieval result dicts (must have 'final_score')

    Returns
    -------
    dict with keys: is_sufficient, chunk_count, avg_score, max_score, quality_level
    """
    if not results:
        return {
            "is_sufficient": False,
            "chunk_count": 0,
            "avg_score": 0.0,
            "max_score": 0.0,
            "quality_level": "none",
        }

    scores = [r.get("final_score", r.get("relevance", 0.0)) for r in results]
    # Only consider chunks above the minimum relevance threshold
    relevant = [s for s in scores if s >= MIN_RELEVANCE]

    avg_score = sum(relevant) / len(relevant) if relevant else 0.0
    max_score = max(scores) if scores else 0.0
    is_sufficient = len(relevant) >= MIN_CONTEXT_CHUNKS and avg_score >= MIN_RELEVANCE

    if avg_score >= 0.80:
        quality_level = "excellent"
    elif avg_score >= 0.65:
        quality_level = "good"
    elif avg_score >= MIN_RELEVANCE:
        quality_level = "fair"
    else:
        quality_level = "poor"

    return {
        "is_sufficient": is_sufficient,
        "chunk_count": len(relevant),
        "avg_score": round(avg_score, 3),
        "max_score": round(max_score, 3),
        "quality_level": quality_level,
    }


def calculate_confidence(context_quality: dict, answer_length: int = 0) -> float:
    """
    Compute an overall confidence score for an LLM answer.

    Factors:
      - avg_score of the retrieved context   (weight 0.6)
      - whether context is sufficient        (weight 0.2)
      - answer length heuristic              (weight 0.2)
    """
    avg = context_quality.get("avg_score", 0.0)
    is_suf = 1.0 if context_quality.get("is_sufficient", False) else 0.0

    # Normalise answer length: 50–500 chars → 0→1 (sigmoid-like)
    length_score = min(1.0, max(0.0, (answer_length - 20) / 480))

    confidence = 0.6 * avg + 0.2 * is_suf + 0.2 * length_score
    return round(min(1.0, max(0.0, confidence)), 3)


def extract_source_citations(results: list[dict]) -> list[dict]:
    """
    Build a deduplicated, numbered citation list from retrieval results.

    Returns list of:
      { index, source, score, source_type, project, tags }
    """
    seen: set[str] = set()
    citations: list[dict] = []

    for r in sorted(results, key=lambda x: x.get("final_score", 0.0), reverse=True):
        src = r.get("source", "unknown")
        if src in seen:
            continue
        seen.add(src)
        citations.append({
            "index": len(citations) + 1,
            "source": src,
            "score": round(r.get("final_score", r.get("relevance", 0.0)), 3),
            "source_type": r.get("source_type", "unknown"),
            "project": r.get("project"),
            "tags": r.get("tags", []),
        })

    return citations


def build_grounded_response(
    answer: str,
    results: list[dict],
    insufficient_context: bool = False,
) -> dict:
    """
    Wrap an LLM answer into a structured, trust-aware response.

    If `insufficient_context` is True, replaces the answer with a safe fallback.
    """
    quality = evaluate_context_quality(results)
    confidence = calculate_confidence(quality, answer_length=len(answer))
    citations = extract_source_citations(results)

    if insufficient_context or not quality["is_sufficient"]:
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            answer = FALLBACK_RESPONSE
            insufficient_context = True

    return {
        "answer": answer,
        "confidence": confidence,
        "insufficient_context": insufficient_context,
        "context_quality": quality,
        "used_sources": citations,
    }
