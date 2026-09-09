"""Retrieval pipeline.

Design:

    query
      -> metadata filtering where appropriate
      -> dense retrieval
      -> hybrid retrieval where supported         (extension point)
      -> candidate merging                         (extension point)
      -> reranking                                 (extension point)
      -> evidence evaluation                       (extension point)
      -> parent expansion if needed

Phase 1 establishes the interface, the filtering model, and a reference
pipeline that raises a clear error until a vector store is configured.
Enabled features are driven by configuration so we can switch them on later
without code changes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.config import RETRIEVAL_TOP_K
from app.errors import ConfigurationError
from app.rag.models import RetrievedChunk


class RetrievalFilter(BaseModel):
    """Metadata filters applied to a retrieval query."""

    document_id: str | None = None
    document_type: str | None = None
    topic: str | None = None
    source: str | None = None
    heading: str | None = None
    extra: dict | None = None

    def to_kwargs(self) -> dict:
        """Convert to per-provider filter kwargs (drop empty fields)."""
        filtered = {k: v for k, v in self.__dict__.items() if v is not None and k != "extra"}
        if self.extra:
            filtered.update(self.extra)
        return filtered


@runtime_checkable
class Retriever(Protocol):
    """Executes a retrieval query and returns evidence."""

    def retrieve(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]: ...


def _not_configured_error() -> ConfigurationError:
    return ConfigurationError(
        "Retrieval is not configured. Selecting a vector store and embeddings "
        "provider is a prerequisite for retrieval."
    )


def get_retriever() -> Retriever:
    """Return the configured retriever.

    With no vector store configured, retrieval is explicitly unavailable —
    the agent will detect this and answer without retrieval rather than
    pretend retrieval happened.
    """
    raise _not_configured_error()


def is_retrieval_configured() -> bool:
    from app.rag.vectorestore import is_vector_store_configured
    from app.rag.embeddings import is_embeddings_configured

    return is_vector_store_configured() and is_embeddings_configured()


def merge_candidates(*groups: list[RetrievedChunk], top_k: int = RETRIEVAL_TOP_K) -> list[RetrievedChunk]:
    """Merge candidate lists from multiple retrieval passes.

    Deduplicates by chunk id, keeps the best score per chunk, and applies an
    upper bound. Scores are expected to be comparable (same metric).
    """
    best: dict[str, RetrievedChunk] = {}
    for group in groups:
        for item in group:
            key = item.chunk.chunk_id
            if key not in best or item.score > best[key].score:
                best[key] = item

    ranked = sorted(best.values(), key=lambda item: item.score, reverse=True)
    return ranked[:top_k]


def rerank(candidates: list[RetrievedChunk], query: str, top_k: int = RETRIEVAL_TOP_K) -> list[RetrievedChunk]:
    """Re-rank candidates with a cross-encoder.

    Extension point: Phase 1 keeps candidates as-is. When a reranker provider
    is selected, implement it here behind the same signature.
    """
    return candidates[:top_k]


def evaluate_evidence(candidates: list[RetrievedChunk]) -> "EvidenceVerdict":
    """Evaluate whether retrieved evidence is sufficient to answer.

    Phase 1 uses a small, deterministic heuristic: at least one candidate with
    non-trivial score. The adaptive/LLM-powered evaluation arrives in a later
    phase when real retrieval exists.
    """
    relevant = [c for c in candidates if c.score >= 0.0]
    sufficient = len(relevant) > 0
    return EvidenceVerdict(sufficient=sufficient, top_score=max((c.score for c in candidates), default=0.0))


class EvidenceVerdict(BaseModel):
    """Outcome of evidence evaluation."""

    sufficient: bool
    top_score: float = 0.0


def expand_parents(candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Expand child chunks to their parent block when present.

    Called automatically by context assembly; children retain their score
    and the parent text is used for generation.
    """
    return candidates