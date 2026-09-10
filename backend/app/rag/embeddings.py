"""Embedding abstraction.

Any embedding backend satisfies the ``Embedder`` protocol. The concrete
provider in use is Google's Gemini Embedding API (via the existing
``langchain-google-genai`` integration) configured through environment
variables. ``get_embedder()`` returns a lazily-built singleton and raises a
clear ``ConfigurationError`` while the provider is not fully configured.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.config import (
    GEMINI_API_KEY,
    GEMINI_EMBEDDING_MODEL,
    VECTOR_STORE_PROVIDER,
)
from app.errors import ConfigurationError, ProviderError

logger = logging.getLogger(__name__)


@runtime_checkable
class Embedder(Protocol):
    """Produces vector embeddings for the knowledge base."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...

    @property
    def dimensions(self) -> int: ...


class GeminiEmbedder:
    """Gemini Embedding API wrapper implementing the ``Embedder`` protocol.

    Backed by ``GoogleGenerativeAIEmbeddings`` from the already-installed
    ``langchain-google-genai`` package. The key, model, and provider are read
    from configuration — never hard-coded. Provider failures are converted into
    controlled ``ProviderError`` exceptions; requests and keys are never logged.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        backend=None,
    ):
        if backend is not None:
            self._backend = backend
        else:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
            except ImportError:
                raise ConfigurationError(
                    "langchain-google-genai is not installed. "
                    "Run: pip install -r requirements.txt"
                )

            if not api_key:
                raise ConfigurationError(
                    "Gemini API key is not configured. Set GEMINI_API_KEY "
                    "(or GOOGLE_API_KEY) in backend/.env or your environment."
                )
            if not model_name:
                raise ConfigurationError("GEMINI_EMBEDDING_MODEL is not configured.")

            try:
                self._backend = GoogleGenerativeAIEmbeddings(
                    model=model_name,
                    google_api_key=api_key,
                )
            except (ValueError, TypeError) as exc:
                raise ConfigurationError(
                    f"Failed to initialize Gemini embeddings: {exc}"
                ) from exc

        self._dimensions: int | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self._backend.embed_documents(list(texts))
        except Exception as exc:
            logger.warning("Gemini document embedding failed")
            raise ProviderError(
                "Embedding generation is currently unavailable."
            ) from exc
        if vectors:
            self._dimensions = len(vectors[0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        try:
            vector = self._backend.embed_query(text)
        except Exception as exc:
            logger.warning("Gemini query embedding failed")
            raise ProviderError(
                "Embedding generation is currently unavailable."
            ) from exc
        if vector:
            self._dimensions = len(vector)
        return vector

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            raise ConfigurationError(
                "Embedding dimensions are unknown until the first embedding is "
                "generated."
            )
        return self._dimensions


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Return the configured embedding provider (Gemini Embedding API).

    Built lazily so provider credential issues surface at first use rather than
    at import time (which would break the health endpoint).
    """
    global _embedder
    if _embedder is not None:
        return _embedder

    if not is_embeddings_configured():
        raise ConfigurationError(
            "No embeddings provider is configured. Set VECTOR_STORE_PROVIDER "
            "and GEMINI_API_KEY (with GEMINI_EMBEDDING_MODEL) first."
        )

    _embedder = GeminiEmbedder(
        model_name=GEMINI_EMBEDDING_MODEL,
        api_key=GEMINI_API_KEY,
    )
    return _embedder


def reset_embedder() -> None:
    """Drop the cached embedder (mainly for tests)."""
    global _embedder
    _embedder = None


def is_embeddings_configured() -> bool:
    return bool(VECTOR_STORE_PROVIDER and GEMINI_API_KEY)