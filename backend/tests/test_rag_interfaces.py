"""RAG interface tests.

These assert the abstraction boundaries, not any specific provider:
  - vector store / embedder must not be silently "implemented" with a fake
  - retrieval must refuse to run until a provider is configured
  - evidence assembly is deterministic and de-duplicates
"""
import pytest

from app.errors import ConfigurationError
from app.rag.context import assemble_evidence
from app.rag.embeddings import get_embedder
from app.rag.models import (
    ChildChunk,
    DocumentMetadata,
    ParentChunk,
    RetrievedChunk,
)
from app.rag.retriever import (
    merge_candidates,
    evaluate_evidence,
)
from app.rag.vectorestore import get_vector_store


def test_no_hardcoded_vector_store(monkeypatch):
    """No fake/in-memory vector store may be silently used as 'production'."""
    from app.rag.vectorestore import reset_vector_store

    reset_vector_store()
    monkeypatch.setattr(
        "app.rag.vectorestore.is_vector_store_configured", lambda: False
    )
    with pytest.raises(ConfigurationError):
        get_vector_store()


def test_embeddings_require_explicit_selection(monkeypatch):
    from app.rag.embeddings import reset_embedder

    reset_embedder()
    monkeypatch.setattr(
        "app.rag.embeddings.is_embeddings_configured", lambda: False
    )
    with pytest.raises(ConfigurationError):
        get_embedder()


def _child(id_, parent, score):
    chunk = ChildChunk(
        chunk_id=id_,
        parent_id=parent,
        document_id="doc1",
        content=f"child {id_}",
        position=0,
        metadata=DocumentMetadata(document_id="doc1", source="menu.md"),
    )
    return RetrievedChunk(chunk=chunk, score=score, source="menu.md")


def test_merge_candidates_deduplicates_and_bounds():
    a = _child("c1", "p1", 0.9)
    a2 = _child("c1", "p1", 0.95)  # same id, better score
    b = _child("c2", "p2", 0.8)
    merged = merge_candidates([a, b], [a2], top_k=5)
    ids = [m.chunk.chunk_id for m in merged]
    assert ids == ["c1", "c2"]
    assert next(m for m in merged if m.chunk.chunk_id == "c1").score == pytest.approx(0.95)


def test_evaluate_evidence_sufficient_when_candidates_exist():
    verdict = evaluate_evidence([_child("c1", "p1", 0.7)])
    assert verdict.sufficient is True
    assert verdict.top_score == pytest.approx(0.7)


def test_evaluate_evidence_insufficient_when_empty():
    verdict = evaluate_evidence([])
    assert verdict.sufficient is False
    assert verdict.top_score == 0.0


def test_assemble_evidence_formats_context_with_sources():
    child = ChildChunk(
        chunk_id="c1",
        parent_id="p1",
        document_id="doc1",
        content="Cause in child chunk",
        position=0,
        metadata=DocumentMetadata(document_id="doc1", source="menu.md", title="Menu"),
    )
    parent = ParentChunk(
        chunk_id="p1",
        parent_id=None,
        document_id="doc1",
        content="Full parent context block",
        position=0,
        metadata=DocumentMetadata(document_id="doc1", source="menu.md", title="Menu"),
    )
    candidate = RetrievedChunk(chunk=child, score=0.9, source="Menu", parent=parent)

    evidence = assemble_evidence([candidate])
    assert "Full parent context block" in evidence.context
    assert "Menu" in evidence.citations
    assert evidence.retrieval_count == 1


def test_assemble_evidence_empty():
    evidence = assemble_evidence([])
    assert evidence.context == ""
    assert evidence.citations == []
    assert evidence.retrieval_count == 0