"""Embedding abstraction.

Any embedding backend satisfies the ``Embedder`` protocol. Until an embedding
provider/model is explicitly selected, ``get_embedder()`` raises a
``ConfigurationError`` rather than silently using a placeholder.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.config import VECTOR_STORE_PROVIDER
from app.errors import ConfigurationError


@runtime_checkable
class Embedder(Protocol):
    """Produces vector embeddings for the knowledge base."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...

    @property
    def dimensions(self) -> int: ...


def get_embedder() -> Embedder:
    """Return the configured embedding provider.

    The embedding provider is chosen together with the vector store when the
    project selects one — hard-coding one now would be premature.
    """
    raise ConfigurationError(
        "No embeddings provider is configured. Select an embedding provider "
        "and vector store first."
    )


def is_embeddings_configured() -> bool:
    return VECTOR_STORE_PROVIDER is not None