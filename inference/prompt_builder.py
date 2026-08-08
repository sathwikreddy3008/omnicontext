"""
inference/prompt_builder.py — OmniContext citation-aware prompt builder.

Formats retrieved context chunks as numbered, source-labelled snippets
so the LLM can ground its answer and cite specific sources.
"""

from __future__ import annotations

from typing import Optional


SYSTEM_PROMPT_TEMPLATE = """\
You are OmniContext, a local AI context assistant that answers questions \
based ONLY on the provided numbered context snippets.

Rules:
1. Answer using ONLY information present in the numbered context below.
2. After your answer, list which numbered sources you used, e.g. Sources used: [1], [3].
3. If the context does not contain enough information, say exactly:
   "I don't have sufficient context to answer that question."
4. Never fabricate or infer information beyond what is explicitly stated.
5. Keep your answer concise and accurate.

{context_block}
"""

USER_PROMPT_TEMPLATE = """\
Question:
{query}

Answer:
"""


def build_prompt_messages(
    query: str,
    results: list[dict],
    conversation_history: Optional[list[dict]] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Build the full message list for the Ollama chat API.

    Parameters
    ----------
    query                : the user's question
    results              : list of hybrid-retrieval result dicts
                           (must have 'content' and 'source' keys)
    conversation_history : prior turns to include for multi-turn context

    Returns
    -------
    (messages, citation_map)
      messages     : ready for ollama.chat(messages=...)
      citation_map : list of {index, source, score, source_type, ...}
    """
    context_block, citation_map = _build_context_block(results)

    system_content = SYSTEM_PROMPT_TEMPLATE.format(context_block=context_block)

    messages: list[dict] = [{"role": "system", "content": system_content}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": USER_PROMPT_TEMPLATE.format(query=query)})

    return messages, citation_map


def parse_citations_from_answer(answer: str, citation_map: list[dict]) -> list[dict]:
    """
    Extract which numbered citations the model claimed to use.

    Looks for patterns like [1], [2], [1], [3] at the end of the answer.
    Returns citation dicts for each referenced index.
    """
    import re
    referenced_indices: set[int] = set()
    for m in re.finditer(r"\[(\d+)\]", answer):
        referenced_indices.add(int(m.group(1)))

    used: list[dict] = []
    for c in citation_map:
        if c["index"] in referenced_indices:
            used.append(c)

    # If the model didn't cite anything but gave a real answer, include top sources
    if not used and citation_map and len(answer) > 50:
        used = citation_map[:2]

    return used


def _build_context_block(results: list[dict]) -> tuple[str, list[dict]]:
    """
    Format results as numbered context snippets.

    Returns (formatted_block, citation_map).
    """
    if not results:
        return "No context available.", []

    lines: list[str] = []
    citation_map: list[dict] = []

    for idx, r in enumerate(results, start=1):
        source = r.get("source", "unknown")
        content = r.get("content", r.get("full_text", r.get("text", "")))
        score = round(r.get("final_score", r.get("relevance", 0.0)), 3)
        source_type = r.get("source_type", "unknown")
        project = r.get("project")
        tags = r.get("tags", [])

        header = f"[{idx}] Source: {source}"
        if project:
            header += f" (project: {project})"
        lines.append(f"{header}\n{content.strip()}\n")

        citation_map.append({
            "index": idx,
            "source": source,
            "score": score,
            "source_type": source_type,
            "project": project,
            "tags": tags,
        })

    return "\n".join(lines), citation_map
