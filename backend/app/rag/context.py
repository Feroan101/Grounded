"""Context assembly for generation.

Turns retrieved chunks into a compact, de-duplicated evidence string with
source citations. Children are expanded to parents where the vector store
provides them.
"""
from __future__ import annotations

from app.config import RETRIEVAL_TOP_K
from app.rag.models import Evidence, RetrievedChunk
from app.rag.retriever import expand_parents


def assemble_evidence(
    candidates: list[RetrievedChunk],
    top_k: int = RETRIEVAL_TOP_K,
) -> Evidence:
    """Build the final evidence object fed to the generator.

    Steps:
      1. Expand children to parent context where available.
      2. Deduplicate (a parent may appear via multiple children).
      3. Format with source citations.
    """
    expanded = expand_parents(candidates)

    seen: dict[str, RetrievedChunk] = {}
    for item in expanded:
        key = item.parent.chunk_id if item.parent is not None else item.chunk.chunk_id
        if key not in seen or item.score > seen[key].score:
            seen[key] = item

    ordered = sorted(seen.values(), key=lambda item: item.score, reverse=True)[:top_k]

    blocks: list[str] = []
    citations: list[str] = []
    for idx, item in enumerate(ordered, start=1):
        source = item.source or item.chunk.metadata.source or "unknown"
        text = item.text
        blocks.append(f"[{idx}] ({source})\n{text}")
        citations.append(source)

    return Evidence(
        context="\n\n".join(blocks),
        citations=citations,
        retrieval_count=len(candidates),
    )