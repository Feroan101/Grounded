"""Document ingestion pipeline.

Phase 1 establishes the ingestion contract and wiring between chunking,
embedding, and the vector store. It does not run against a real store until a
provider is selected.
"""
from __future__ import annotations

import hashlib

from app.rag.embeddings import get_embedder
from app.rag.models import (
    ChildChunk,
    Document,
    IngestionResult,
    ParentChunk,
)
from app.rag.vectorestore import get_vector_store
from app.rag.chunking import chunk_document


def _chunk_id(document_id: str, position: int, level: str) -> str:
    raw = f"{document_id}:{level}:{position}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def ingest_document(document: Document) -> IngestionResult:
    """Ingest one document into the knowledge base.

    Steps:
      1. Hierarchically chunk the document (parent/child).
      2. Embed each chunk.
      3. Upsert into the external vector store.
    """
    hierarchy = chunk_document(document, assign_ids=_chunk_id)

    embedder = get_embedder()
    vector_store = get_vector_store()

    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []
    vector_chunks: list[ParentChunk | ChildChunk] = []

    for parent in hierarchy.parents:
        parents.append(parent)
        vector_chunks.append(parent)

    for child in hierarchy.children:
        children.append(child)
        vector_chunks.append(child)

    # Emphasize content when embedding so retrieval matches semantics, not ids.
    vectors = embedder.embed_documents(
        [f"{c.metadata.heading_path} {c.content}".strip() for c in vector_chunks]
    )

    vector_store.upsert_chunks(vector_chunks, vectors)

    return IngestionResult(
        document_id=document.document_id,
        parent_count=len(parents),
        child_count=len(children),
        vector_count=len(vector_chunks),
        status="ok",
    )


def delete_document(document_id: str) -> None:
    """Remove an ingested document from the knowledge base."""
    get_vector_store().delete_document(document_id)