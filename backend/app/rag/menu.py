"""Menu semantic retrieval and indexing.

This module ties the menu to the embedding + vector-store abstraction:

    query -> Gemini embedding -> Qdrant search -> candidate menu IDs

and provides the deterministic, re-indexable representation of each canonical
Firestore menu item. Firestore remains the source of truth: the vector store
only identifies relevant ``menu_id`` values, and final facts always come from
Firestore documents.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from app.config import MENU_SEMANTIC_TOP_K
from app.errors import GroundedError
from app.rag.embeddings import Embedder, get_embedder
from app.rag.models import Chunk, DocumentMetadata
from app.rag.vectorestore import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


class MenuIndexingError(GroundedError):
    """Raised when the menu cannot be indexed."""

    message = "Menu indexing failed."


@dataclass(frozen=True)
class MenuIndexingResult:
    """Outcome of indexing the menu into the vector store."""

    document_count: int
    vector_count: int
    vector_size: int
    status: str = "ok"


def menu_item_to_text(item: dict) -> str:
    """Build a deterministic semantic representation of a menu item.

    Includes the fields that carry meaning for retrieval: name, category,
    description, ingredients, flavors, tags, sweetness, caffeine, temperature,
    and dietary information. Prices and availability are deliberately excluded:
    those facts always come from Firestore, never from vectors.
    """
    name = item.get("name", "")
    category = item.get("category", "")
    description = item.get("description", "") or ""
    ingredients = ", ".join(item.get("ingredients") or [])
    flavors = ", ".join(item.get("flavor_profile") or [])
    tags = ", ".join(item.get("tags") or [])
    sweetness = item.get("sweetness", "")
    caffeine = item.get("caffeine", "")
    temperature = item.get("temperature", "")
    dietary = ", ".join(item.get("dietary") or [])
    return "\n".join(
        [
            f"Name: {name}",
            f"Category: {category}",
            f"Description: {description}",
            f"Ingredients: {ingredients}",
            f"Flavors: {flavors}",
            f"Tags: {tags}",
            f"Sweetness: {sweetness}",
            f"Caffeine: {caffeine}",
            f"Temperature: {temperature}",
            f"Dietary: {dietary}",
        ]
    )


def menu_chunk_id(menu_id: str) -> str:
    """Deterministic point id for a menu item.

    Deterministic ids make indexing idempotent: re-running the indexing
    operation overwrites the same points rather than creating duplicates.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"grounded-menu/{menu_id}"))


class MenuIndexer:
    """Explicit indexing operation. Never invoked during a chat request."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.embedder = embedder or get_embedder()
        self.vector_store = vector_store or get_vector_store()

    def chunk_for(self, item: dict) -> Chunk:
        menu_id = item.get("id") or item.get("document_id")
        if not menu_id:
            raise MenuIndexingError("Menu item is missing its canonical 'id'.")
        return Chunk(
            chunk_id=menu_chunk_id(menu_id),
            document_id=menu_id,
            content=menu_item_to_text(item),
            position=0,
            metadata=DocumentMetadata(
                document_id=menu_id,
                source="firestore:menu",
                title=item.get("name", ""),
                document_type="menu_item",
                extra={"menu_id": menu_id},
            ),
            level="parent",
        )

    def index(self, items: list[dict]) -> MenuIndexingResult:
        if not items:
            raise MenuIndexingError("No menu items provided to index.")

        chunks = [self.chunk_for(item) for item in items]
        vectors = self.embedder.embed_documents([chunk.content for chunk in chunks])
        if not vectors:
            raise MenuIndexingError("No embedding vectors were produced.")

        vector_size = len(vectors[0])
        self.vector_store.ensure_collection(vector_size)
        self.vector_store.upsert_chunks(chunks, vectors)
        logger.info(
            "Indexed %d menu items into vector store '%s'",
            len(items),
            getattr(self.vector_store, "collection", "?"),
        )
        return MenuIndexingResult(
            document_count=len(items),
            vector_count=len(vectors),
            vector_size=vector_size,
        )

    def index_from_firestore(self) -> MenuIndexingResult:
        """Index the canonical Firestore menu (the source of truth)."""
        from app.repositories.menu import list_menu_items

        items = list_menu_items()
        if not items:
            raise MenuIndexingError("The Firestore menu collection is empty.")
        return self.index(items)


def index_menu(items: list[dict]) -> MenuIndexingResult:
    """Convenience wrapper: index menu items using the configured providers."""
    return MenuIndexer().index(items)


def search_semantic_menu_ids(
    query: str,
    top_k: int = MENU_SEMANTIC_TOP_K,
) -> list[str]:
    """Return candidate canonical menu IDs for a natural-language query.

    Raises the underlying ``ProviderError``/``ConfigurationError`` on failure so
    callers decide whether to fall back to structured search.
    """
    embedder = get_embedder()
    vector_store = get_vector_store()

    query_vector = embedder.embed_query(query)
    results = vector_store.search(query_vector, top_k=max(1, top_k))

    ids: list[str] = []
    seen: set[str] = set()
    for item in results:
        menu_id = item.chunk.metadata.extra.get("menu_id") or item.chunk.document_id
        if menu_id and menu_id not in seen:
            seen.add(menu_id)
            ids.append(menu_id)
    return ids