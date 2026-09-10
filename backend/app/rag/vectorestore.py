"""Vector store abstraction.

The vector store is external (never Render's ephemeral filesystem). Provider
selection is explicit and configured, not hard-coded. The concrete provider in
use is Qdrant Cloud, selected via ``VECTOR_STORE_PROVIDER=qdrant_cloud``.
Until a provider and its credentials are configured, ``get_vector_store()``
raises ``ConfigurationError``.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from app.config import (
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_URL,
    VECTOR_STORE_PROVIDER,
)
from app.errors import ConfigurationError, ProviderError
from app.rag.models import Chunk, DocumentMetadata, RetrievedChunk

logger = logging.getLogger(__name__)

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

    def ensure_collection(self, vector_size: int) -> str: ...
    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> int: ...
    def delete_document(self, document_id: str) -> None: ...
    def search(
        self,
        query_vector: list[float],
        top_k: int = 4,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]: ...
    def get_chunk_by_id(self, chunk_id: str) -> Chunk | None: ...
    def get_children_for_parent(self, parent_id: str) -> list[Chunk]: ...


def _payload_size(info) -> int | None:
    """Extract the vector size from a Qdrant collection info object."""
    try:
        vectors = info.config.params.vectors
    except AttributeError:
        return None
    if isinstance(vectors, dict):
        first = next(iter(vectors.values()), None)
        return getattr(first, "size", None)
    return getattr(vectors, "size", None)


def _build_query_filter(filters: dict):
    """Translate a flat metadata ``filters`` dict into a Qdrant filter."""
    from qdrant_client import models

    conditions = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, bool):
            conditions.append(
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
            )
        elif isinstance(value, (int, float)):
            conditions.append(
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
            )
        elif isinstance(value, (list, tuple, set)):
            values = [str(v) for v in value]
            if values:
                conditions.append(
                    models.FieldCondition(
                        key=key, match=models.MatchAny(any=values)
                    )
                )
        elif isinstance(value, str):
            conditions.append(
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
            )
    if not conditions:
        return None
    return models.Filter(must=conditions)


class QdrantVectorStore:
    """Qdrant Cloud-backed ``VectorStore``.

    Each indexed menu item is stored as one point whose payload carries the
    canonical Firestore ``menu_id`` plus the deterministic text used for
    embedding. The store never receives credentials in payloads or logs.
    """

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        collection: str,
        client=None,
    ):
        self._url = url
        self._api_key = api_key
        self._collection = collection
        if client is not None:
            self._client = client
            return

        try:
            from qdrant_client import QdrantClient
        except ImportError:
            raise ConfigurationError(
                "qdrant-client is not installed. "
                "Run: pip install -r requirements.txt"
            )
        if not url or not api_key:
            raise ConfigurationError(
                "Qdrant URL and API key are required. Set QDRANT_URL and "
                "QDRANT_API_KEY in backend/.env or your environment."
            )
        self._client = QdrantClient(url=url, api_key=api_key)

    @property
    def collection(self) -> str:
        return self._collection

    def _collection_exists(self) -> bool:
        if hasattr(self._client, "collection_exists"):
            try:
                return bool(self._client.collection_exists(self._collection))
            except Exception:
                # Unreachable or forbidden: treat as absent and let the create
                # path surface the real failure as a controlled ProviderError.
                return False
        try:
            self._client.get_collection(self._collection)
            return True
        except Exception:
            return False

    def ensure_collection(self, vector_size: int) -> str:
        """Create the collection if missing; validate it if present.

        Returns "created" or "exists". A size mismatch means the collection and
        the embedding model disagree — reindexing risks garbage results, so this
        is surfaced as a controlled error.
        """
        if self._collection_exists():
            try:
                info = self._client.get_collection(self._collection)
            except Exception as exc:
                raise ProviderError(
                    "Failed to read the Qdrant collection configuration."
                ) from exc
            existing_size = _payload_size(info)
            if existing_size is not None and existing_size != vector_size:
                raise ProviderError(
                    f"Qdrant collection '{self._collection}' has dimension "
                    f"{existing_size}, but the embedding model produced "
                    f"{vector_size}. Recreate the collection or change the "
                    "embedding model configuration."
                )
            return "exists"

        from qdrant_client import models

        try:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
            )
        except Exception as exc:
            raise ProviderError("Failed to create the Qdrant collection.") from exc
        return "created"

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")

        from qdrant_client import models

        points = []
        for chunk, vector in zip(chunks, vectors):
            extra = chunk.metadata.extra or {}
            menu_id = extra.get("menu_id") or chunk.document_id
            points.append(
                models.PointStruct(
                    id=chunk.chunk_id,
                    vector=list(vector),
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "menu_id": menu_id,
                        "title": chunk.metadata.title,
                        "text": chunk.content,
                    },
                )
            )

        if points:
            try:
                self._client.upsert(
                    collection_name=self._collection,
                    points=points,
                )
            except Exception as exc:
                raise ProviderError("Failed to upsert vectors into Qdrant.") from exc
        return len(points)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 4,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        kwargs = {
            "collection_name": self._collection,
            "query": list(query_vector),
            "limit": max(1, top_k),
            "with_payload": True,
            "with_vectors": False,
        }
        if filters:
            query_filter = _build_query_filter(filters)
            if query_filter is not None:
                kwargs["query_filter"] = query_filter

        try:
            response = self._client.query_points(**kwargs)
        except Exception as exc:
            raise ProviderError("Semantic search on Qdrant failed.") from exc

        points = response.points if hasattr(response, "points") else response
        results = []
        for point in points:
            payload = dict(point.payload or {})
            menu_id = payload.get("menu_id") or payload.get("document_id")
            if not menu_id:
                continue
            chunk = Chunk(
                chunk_id=str(point.id),
                document_id=menu_id,
                content=payload.get("text", ""),
                position=0,
                metadata=DocumentMetadata(
                    document_id=menu_id,
                    source="firestore:menu",
                    title=payload.get("title", ""),
                    document_type="menu_item",
                    extra={"menu_id": menu_id},
                ),
                level="parent",
            )
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=float(point.score),
                    source="firestore:menu",
                )
            )
        return results

    def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        try:
            points = self._client.retrieve(
                collection_name=self._collection,
                ids=[str(chunk_id)],
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise ProviderError("Failed to read from Qdrant.") from exc

        if not points:
            return None
        point = points[0]
        payload = dict(point.payload or {})
        menu_id = payload.get("menu_id") or payload.get("document_id")
        if not menu_id:
            return None
        return Chunk(
            chunk_id=str(point.id),
            document_id=menu_id,
            content=payload.get("text", ""),
            position=0,
            metadata=DocumentMetadata(
                document_id=menu_id,
                source="firestore:menu",
                title=payload.get("title", ""),
                document_type="menu_item",
                extra={"menu_id": menu_id},
            ),
            level="parent",
        )

    def get_children_for_parent(self, parent_id: str) -> list[Chunk]:
        # Menu items are stored as flat single-chunk points (no children).
        return []

    def delete_document(self, document_id: str) -> None:
        from qdrant_client import models

        try:
            self._client.delete(
                collection_name=self._collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
            )
        except Exception as exc:
            raise ProviderError("Failed to delete from Qdrant.") from exc


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the configured external vector store (Qdrant Cloud).

    The provider is selected via ``VECTOR_STORE_PROVIDER=qdrant_cloud`` and
    connected using ``QDRANT_URL`` and ``QDRANT_API_KEY``. Nothing is hard-coded.
    """
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    if not is_vector_store_configured():
        raise ConfigurationError(
            "No vector store provider is configured. Set "
            "VECTOR_STORE_PROVIDER=qdrant_cloud plus QDRANT_URL and "
            "QDRANT_API_KEY when the knowledge-base deployment is ready."
        )

    _vector_store = QdrantVectorStore(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        collection=QDRANT_COLLECTION,
    )
    return _vector_store


def reset_vector_store() -> None:
    """Drop the cached vector store (mainly for tests)."""
    global _vector_store
    _vector_store = None


def is_vector_store_configured() -> bool:
    return (
        VECTOR_STORE_PROVIDER in {"qdrant", "qdrant_cloud"}
        and bool(QDRANT_URL)
        and bool(QDRANT_API_KEY)
    )