"""Vector store abstraction.

The vector store is external (never Render's ephemeral filesystem). Provider
selection is explicit and configured, not hard-coded. Until a provider is
selected, ``get_vector_store()`` raises ``ConfigurationError``.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.config import VECTOR_STORE_PROVIDER
from app.errors import ConfigurationError
from app.rag.models import Chunk, RetrievedChunk

METADATA_FILTER_FIELDS = {
    "document_id",
    "source",
    "title",
    "heading",
    "heading_path",
    "document_type",
    "topic",
}


@runtime_checkable
class VectorStore(Protocol):
    """External vector store for dense retrieval over chunks.

    Embeddings are computed by the embeddings provider and passed explicitly so
    the store never needs to know about a specific model. Search accepts a query
    vector produced the same way.
    """

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...
    def delete_document(self, document_id: str) -> None: ...
    def search(
        self,
        query_vector: list[float],
        top_k: int = 4,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]: ...
    def get_chunk_by_id(self, chunk_id: str) -> Chunk | None: ...
    def get_children_for_parent(self, parent_id: str) -> list[Chunk]: ...


def get_vector_store() -> VectorStore:
    """Return the configured external vector store.

    The provider is selected via ``VECTOR_STORE_PROVIDER``. No provider is
    hard-coded in Phase 1; plug a real one in when the deployment is decided.
    """
    if not VECTOR_STORE_PROVIDER:
        raise ConfigurationError(
            "No vector store provider is configured. Set VECTOR_STORE_PROVIDER "
            "when the knowledge-base deployment is decided."
        )
    raise ConfigurationError(
        f"Vector store provider {VECTOR_STORE_PROVIDER!r} is not implemented "
        "yet. Provider selection is pending."
    )


def is_vector_store_configured() -> bool:
    return VECTOR_STORE_PROVIDER is not None