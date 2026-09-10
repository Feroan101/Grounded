"""Focused tests for Grounded's semantic menu retrieval.

Covers the Gemini embedding service, Qdrant configuration and store behavior,
the deterministic menu representation, indexing (idempotent), hybrid
``MenuService`` search with hard structured constraints, and the structured
fallback path. All external providers (Gemini, Qdrant) are mocked — no network
or credentials are used. Integration tests are gated behind
``RUN_INTEGRATION_TESTS=1``.
"""
from __future__ import annotations

import importlib
import os
from types import SimpleNamespace

import pytest

import app.services.menu_service as menu_service_module
from app.errors import ConfigurationError, ProviderError
from app.rag.embeddings import GeminiEmbedder
from app.rag.menu import (
    MenuIndexer,
    menu_chunk_id,
    menu_item_to_text,
    search_semantic_menu_ids,
)
from app.rag.models import Chunk, DocumentMetadata, RetrievedChunk
from app.rag.vectorestore import QdrantVectorStore

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_config_after_each_test():
    yield
    importlib.reload(importlib.import_module("app.config"))


def _no_dotenv(monkeypatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)


def _safety_item(
    item_id: str = "mocha",
    *,
    name: str = "Mocha",
    category: str = "Hot Coffee",
    description: str = "Rich chocolate espresso drink.",
    ingredients=(),
    price=260,
    dietary=(),
    caffeine="medium",
    temperature="hot",
    sweetness="medium",
    flavor_profile=(),
    tags=(),
    available=True,
) -> dict:
    return {
        "id": item_id,
        "name": name,
        "category": category,
        "description": description,
        "ingredients": list(ingredients),
        "size": "240 ml",
        "price": price,
        "dietary": list(dietary),
        "caffeine": caffeine,
        "temperature": temperature,
        "sweetness": sweetness,
        "flavor_profile": list(flavor_profile),
        "tags": list(tags),
        "available": available,
    }


class _FakeEmbeddingBackend:
    """Stand-in for GoogleGenerativeAIEmbeddings."""

    def __init__(self, *, dimension: int = 4, error: Exception | None = None):
        self.dimension = dimension
        self.error = error
        self.doc_texts: list[str] = []
        self.query_texts: list[str] = []

    def embed_query(self, text):
        self.query_texts.append(text)
        if self.error:
            raise self.error
        return [0.1] * self.dimension

    def embed_documents(self, texts):
        self.doc_texts.extend(texts)
        if self.error:
            raise self.error
        return [[0.1] * self.dimension for _ in texts]


class _FakeVectorStore:
    """Menu-level VectorStore stand-in (no network)."""

    def __init__(self, results: list[RetrievedChunk] | None = None):
        self.results = results or []
        self.ensure_calls: list[int] = []
        self.upsert_chunks_calls: list[tuple] = []
        self.search_calls: list[tuple] = []

    @property
    def collection(self) -> str:
        return "grounded-menu"

    def ensure_collection(self, vector_size: int) -> str:
        self.ensure_calls.append(vector_size)
        return "exists"

    def upsert_chunks(self, chunks, vectors):
        self.upsert_chunks_calls.append((chunks, vectors))
        return len(chunks)

    def search(self, query_vector, top_k=4, filters=None):
        self.search_calls.append((query_vector, top_k, filters))
        return self.results


def _chunk_for_menu(menu_id: str, text: str = "") -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=menu_chunk_id(menu_id),
        document_id=menu_id,
        content=text,
        position=0,
        metadata=DocumentMetadata(
            document_id=menu_id,
            source="firestore:menu",
            title=menu_id,
            document_type="menu_item",
            extra={"menu_id": menu_id},
        ),
        level="parent",
    )
    return RetrievedChunk(chunk=chunk, score=0.9, source="firestore:menu")


def _point(menu_id: str, id_: str | None = None, payload=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_ or menu_chunk_id(menu_id),
        score=0.9,
        payload=payload or {"menu_id": menu_id, "document_id": menu_id},
    )


class _FakeQdrantClient:
    """Stand-in for qdrant_client.QdrantClient."""

    def __init__(self, *, exists: bool = False, size: int | None = None, points=None):
        self._exists = exists
        self._size = size
        self.points = points or []
        self.created: list[tuple] = []
        self.upserts: list[list] = []
        self.searches: list[dict] = []
        self.deleted: list[str] = []

    def collection_exists(self, name):
        return self._exists

    def get_collection(self, name):
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=self._size))
            )
        )

    def create_collection(self, collection_name, vectors_config):
        self.created.append((collection_name, vectors_config))

    def upsert(self, collection_name, points):
        self.upserts.append(points)

    def query_points(self, **kwargs):
        self.searches.append(kwargs)
        return SimpleNamespace(points=self.points)

    def retrieve(self, collection_name, ids, with_payload=True, with_vectors=False):
        return [p for p in self.points if str(p.id) in {str(i) for i in ids}]

    def delete(self, collection_name, points_selector=None):
        self.deleted.append(collection_name)


def _menu_items() -> list[dict]:
    return [
        _safety_item(
            "mocha",
            name="Mocha",
            category="Hot Coffee",
            price=260,
            ingredients=["espresso", "chocolate"],
            dietary=["vegetarian"],
            flavor_profile=["chocolate", "creamy"],
            tags=["milk-based"],
        ),
        _safety_item(
            "vanilla-cold-brew",
            name="Vanilla Cold Brew",
            category="Cold Coffee",
            price=240,
            ingredients=["coffee"],
            dietary=["vegan"],
            caffeine="high",
            temperature="cold",
            sweetness="low",
            flavor_profile=["smooth", "vanilla"],
            tags=["cold-brew"],
        ),
        _safety_item(
            "affogato",
            name="Affogato",
            category="Cold Coffee",
            price=320,
            ingredients=["espresso", "ice-cream"],
            dietary=["vegetarian"],
            caffeine="medium",
            temperature="cold",
            sweetness="high",
            flavor_profile=["creamy", "sweet"],
            tags=["dessert"],
        ),
    ]


# ---------------------------------------------------------------------------
# 1. Gemini embedding service
# ---------------------------------------------------------------------------


def test_gemini_embedder_embeds_a_query():
    backend = _FakeEmbeddingBackend(dimension=6)
    embedder = GeminiEmbedder(model_name="gemini-embedding-001", api_key="k", backend=backend)

    vector = embedder.embed_query("something comforting")

    assert vector == [0.1] * 6
    assert backend.query_texts == ["something comforting"]
    assert embedder.dimensions == 6


def test_gemini_embedder_embeds_documents():
    backend = _FakeEmbeddingBackend(dimension=3)
    embedder = GeminiEmbedder(model_name="gemini-embedding-001", api_key="k", backend=backend)

    vectors = embedder.embed_documents(["alpha", "beta"])

    assert len(vectors) == 2
    assert all(len(v) == 3 for v in vectors)
    assert backend.doc_texts == ["alpha", "beta"]


def test_gemini_embedder_handles_empty_documents_without_calling_provider():
    backend = _FakeEmbeddingBackend()
    embedder = GeminiEmbedder(model_name="m", api_key="k", backend=backend)

    assert embedder.embed_documents([]) == []
    assert backend.doc_texts == []


def test_gemini_embedder_requires_an_api_key_when_no_backend_injected():
    with pytest.raises(ConfigurationError, match="Gemini API key"):
        GeminiEmbedder(model_name="gemini-embedding-001", api_key="")


# ---------------------------------------------------------------------------
# 2. Embedding model configuration
# ---------------------------------------------------------------------------


def test_gemini_embedding_model_default_is_stable_model(monkeypatch):
    _no_dotenv(monkeypatch)
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)
    config = importlib.reload(importlib.import_module("app.config"))

    assert config.GEMINI_EMBEDDING_MODEL == "gemini-embedding-001"


def test_gemini_embedding_model_reads_from_environment(monkeypatch):
    _no_dotenv(monkeypatch)
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    config = importlib.reload(importlib.import_module("app.config"))

    assert config.GEMINI_EMBEDDING_MODEL == "gemini-embedding-2"


# ---------------------------------------------------------------------------
# 3. Qdrant configuration
# ---------------------------------------------------------------------------


def test_qdrant_config_defaults(monkeypatch):
    _no_dotenv(monkeypatch)
    for key in ("QDRANT_URL", "QDRANT_API_KEY", "QDRANT_COLLECTION"):
        monkeypatch.delenv(key, raising=False)
    config = importlib.reload(importlib.import_module("app.config"))

    assert config.QDRANT_URL == ""
    assert config.QDRANT_API_KEY == ""
    assert config.QDRANT_COLLECTION == "grounded-menu"
    assert config.is_semantic_menu_configured() is False


def test_qdrant_config_reads_from_environment(monkeypatch):
    _no_dotenv(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant_cloud")
    monkeypatch.setenv("QDRANT_URL", "https://example.qdrant.io")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    config = importlib.reload(importlib.import_module("app.config"))

    assert config.QDRANT_URL == "https://example.qdrant.io"
    assert config.QDRANT_API_KEY == "test-key"
    assert config.is_semantic_menu_configured() is True


def test_semantic_menu_not_configured_without_credentials(monkeypatch):
    _no_dotenv(monkeypatch)
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "qdrant_cloud")
    monkeypatch.setenv("QDRANT_URL", "https://example.qdrant.io")
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = importlib.reload(importlib.import_module("app.config"))

    assert config.is_semantic_menu_configured() is False


# ---------------------------------------------------------------------------
# 4. Qdrant collection initialization
# ---------------------------------------------------------------------------


def _store(client) -> QdrantVectorStore:
    return QdrantVectorStore(
        url="https://example.qdrant.io",
        api_key="secret",
        collection="grounded-menu",
        client=client,
    )


def test_qdrant_collection_created_when_missing():
    from qdrant_client.models import Distance

    client = _FakeQdrantClient(exists=False, size=None)
    status = _store(client).ensure_collection(vector_size=3072)

    assert status == "created"
    assert len(client.created) == 1
    name, vectors_config = client.created[0]
    assert name == "grounded-menu"
    assert vectors_config.size == 3072
    assert vectors_config.distance == Distance.COSINE


def test_qdrant_collection_validated_when_present():
    client = _FakeQdrantClient(exists=True, size=3072)
    store = _store(client)

    assert store.ensure_collection(vector_size=3072) == "exists"
    assert client.created == []


def test_qdrant_collection_dimension_mismatch_raises():
    client = _FakeQdrantClient(exists=True, size=768)
    store = _store(client)

    with pytest.raises(ProviderError, match="dimension"):
        store.ensure_collection(vector_size=3072)


def test_qdrant_store_requires_credentials_without_client():
    with pytest.raises(ConfigurationError, match="QDRANT_URL"):
        QdrantVectorStore(url="", api_key="", collection="grounded-menu")


# ---------------------------------------------------------------------------
# 5. Deterministic menu document generation
# ---------------------------------------------------------------------------


def test_menu_document_generation_is_deterministic():
    item = _menu_items()[0]
    assert menu_item_to_text(item) == menu_item_to_text(item)


def test_menu_document_generation_diffs_across_items():
    first, second = _menu_items()[:2]
    assert menu_item_to_text(first) != menu_item_to_text(second)


def test_menu_document_contains_semantic_fields_but_not_price_or_availability():
    text = menu_item_to_text(_menu_items()[0])
    assert "Mocha" in text
    assert "Hot Coffee" in text
    assert "Rich chocolate espresso drink." in text
    assert "chocolate" in text
    assert "creamy" in text
    assert "medium" in text  # sweetness/caffeine
    assert "dietary" in text.lower()
    assert "260" not in text
    assert "available" not in text


# ---------------------------------------------------------------------------
# 6. Menu ID preservation
# ---------------------------------------------------------------------------


def test_menu_chunk_id_is_deterministic_and_unique():
    assert menu_chunk_id("mocha") == menu_chunk_id("mocha")
    assert menu_chunk_id("mocha") != menu_chunk_id("cold-brew")


def test_qdrant_upsert_payload_preserves_menu_id():
    client = _FakeQdrantClient(exists=True, size=3)
    store = _store(client)
    indexer = MenuIndexer(
        embedder=GeminiEmbedder(model_name="m", api_key="k", backend=_FakeEmbeddingBackend(dimension=3)),
        vector_store=store,
    )
    chunks = [indexer.chunk_for(_menu_items()[0])]
    store.upsert_chunks(chunks, [[0.1, 0.2, 0.3]])

    point = client.upserts[0][0]
    assert point.payload["menu_id"] == "mocha"
    assert point.payload["document_id"] == "mocha"
    assert point.id == menu_chunk_id("mocha")
    # Credentials must never be stored in Qdrant payloads.
    assert "api_key" not in point.payload
    assert "secret" not in str(point.payload)


def test_semantic_search_extracts_menu_ids():
    import app.rag.menu as rag_menu

    embedder = GeminiEmbedder(model_name="m", api_key="k", backend=_FakeEmbeddingBackend())
    store = _FakeVectorStore(
        results=[
            _chunk_for_menu("mocha"),
            _chunk_for_menu("mocha"),  # duplicate must be deduped
            _chunk_for_menu("affogato"),
        ]
    )

    orig_embedder, orig_store = rag_menu.get_embedder, rag_menu.get_vector_store
    rag_menu.get_embedder = lambda: embedder
    rag_menu.get_vector_store = lambda: store
    try:
        ids = search_semantic_menu_ids("creamy chocolate", top_k=5)
    finally:
        rag_menu.get_embedder = orig_embedder
        rag_menu.get_vector_store = orig_store

    assert ids == ["mocha", "affogato"]
    assert store.search_calls[0][1] == 5


# ---------------------------------------------------------------------------
# 7. Indexing the existing menu
# ---------------------------------------------------------------------------


def test_indexing_existing_menu_embeds_and_upserts_all_items():
    from app.menu_ingestion import load_menu

    items = load_menu()
    embedder = GeminiEmbedder(model_name="m", api_key="k", backend=_FakeEmbeddingBackend(dimension=4))
    store = _FakeVectorStore()

    result = MenuIndexer(embedder=embedder, vector_store=store).index(items)

    assert result.document_count == len(items) == 100
    assert result.vector_count == 100
    assert result.vector_size == 4
    assert store.ensure_calls == [4]
    chunks, vectors = store.upsert_chunks_calls[0]
    assert len(chunks) == 100
    assert len(vectors) == 100


def test_indexing_requires_items():
    embedder = GeminiEmbedder(model_name="m", api_key="k", backend=_FakeEmbeddingBackend())
    store = _FakeVectorStore()
    indexer = MenuIndexer(embedder=embedder, vector_store=store)

    from app.rag.menu import MenuIndexingError

    with pytest.raises(MenuIndexingError):
        indexer.index([])


# ---------------------------------------------------------------------------
# 8. Duplicate-safe upsert behavior
# ---------------------------------------------------------------------------


def test_reindexing_uses_same_point_ids_no_duplicates():
    client = _FakeQdrantClient(exists=True, size=3)
    store = _store(client)
    items = _menu_items()
    indexer = MenuIndexer(
        embedder=GeminiEmbedder(model_name="m", api_key="k", backend=_FakeEmbeddingBackend(dimension=3)),
        vector_store=store,
    )

    indexer.index(items)
    indexer.index(items)

    assert len(client.upserts) == 2
    first_ids = [p.id for p in client.upserts[0]]
    second_ids = [p.id for p in client.upserts[1]]
    assert first_ids == second_ids
    assert len(set(first_ids)) == len(items)  # no duplicates within a pass
    assert len(client.upserts[0]) == len(client.upserts[1])


# ---------------------------------------------------------------------------
# Hybrid MenuService search
# ---------------------------------------------------------------------------

_SEMANTIC_IDS = ["mocha", "vanilla-cold-brew", "affogato"]


@pytest.fixture
def semantic_menu(monkeypatch):
    """Turn semantic retrieval on and stub its external calls."""
    by_id = {i["id"]: i for i in _menu_items()}

    def _ids(query, top_k=20):
        return list(_SEMANTIC_IDS)

    monkeypatch.setattr(menu_service_module, "is_semantic_menu_configured", lambda: True)
    monkeypatch.setattr(menu_service_module, "search_semantic_menu_ids", _ids)
    monkeypatch.setattr(menu_service_module, "get_menu_item", lambda mid: by_id.get(mid))


def test_semantic_query_without_exact_keywords_uses_embeddings(semantic_menu, monkeypatch):
    calls = []

    def _ids(query, top_k=20):
        calls.append(query)
        return ["mocha"]

    monkeypatch.setattr(menu_service_module, "search_semantic_menu_ids", _ids)

    service = menu_service_module.MenuService()
    items, diag = service._search(query="something comforting")

    assert calls == ["something comforting"]  # raw query, not tokenized keywords
    assert [i["id"] for i in items] == ["mocha"]
    assert diag["semantic_used"] is True


def test_structured_filters_combined_with_semantic(semantic_menu):
    service = menu_service_module.MenuService()
    items, _ = service._search(query="dessert-like", category="Cold Coffee", sweetness="high")

    assert [i["id"] for i in items] == ["affogato"]
    assert items[0]["price"] == 320


def test_hard_constraint_max_price_never_violated(semantic_menu):
    service = menu_service_module.MenuService()

    items, diag = service._search(query="creamy chocolate drink", max_price=250)

    # A semantically similar ₹320 item must not slip through.
    ids = [i["id"] for i in items]
    assert "affogato" not in ids
    assert all(i["price"] <= 250 for i in items)
    assert diag["semantic_used"] is True


def test_availability_is_a_hard_constraint(semantic_menu, monkeypatch):
    items = _menu_items()
    items[0]["available"] = False
    by_id = {i["id"]: i for i in items}
    monkeypatch.setattr(menu_service_module, "get_menu_item", lambda mid: by_id.get(mid))

    service = menu_service_module.MenuService()
    found, _ = service._search(query="chocolate")
    assert "mocha" not in {i["id"] for i in found}

    found, _ = service._search(query="chocolate", available=False)
    assert "mocha" in {i["id"] for i in found}


def test_final_facts_come_from_firestore_not_vector_payload(semantic_menu):
    """Even if a stale vector payload claimed a different price, Firestore wins."""
    service = menu_service_module.MenuService()
    items, _ = service._search(query="creamy chocolate drink")

    mocha = next(i for i in items if i["id"] == "mocha")
    assert mocha["price"] == 260  # from the Firestore-mocked item, not a payload


def test_missing_firestore_documents_are_ignored(semantic_menu, monkeypatch):
    by_id = {i["id"]: i for i in _menu_items()}
    monkeypatch.setattr(menu_service_module, "get_menu_item", lambda mid: by_id.get(mid))

    def _ids(query, top_k=20):
        return ["mocha", "deleted-from-firestore", "vanilla-cold-brew"]

    monkeypatch.setattr(menu_service_module, "search_semantic_menu_ids", _ids)

    service = menu_service_module.MenuService()
    items, diag = service._search(query="vanilla")

    ids = [i["id"] for i in items]
    assert "deleted-from-firestore" not in ids
    assert diag["missing_from_firestore"] == 1


def test_qdrant_failure_falls_back_to_structured_search(semantic_menu, monkeypatch):
    def _boom(query, top_k=20):
        raise ProviderError("Qdrant is down")

    monkeypatch.setattr(menu_service_module, "search_semantic_menu_ids", _boom)
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: _menu_items())

    service = menu_service_module.MenuService()
    items, diag = service._search(query="mocha", category="Hot Coffee")

    assert [i["id"] for i in items] == ["mocha"]
    assert diag["semantic_used"] is False
    assert diag["fallback_reason"] == "provider_failed"


def test_no_semantic_matches_falls_back_to_structured(semantic_menu, monkeypatch):
    monkeypatch.setattr(menu_service_module, "search_semantic_menu_ids", lambda q, top_k=20: [])
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: _menu_items())

    service = menu_service_module.MenuService()
    items, diag = service._search(query="mocha")

    assert [i["id"] for i in items] == ["mocha"]
    assert diag["fallback_reason"] == "no_semantic_matches"


def test_no_results_when_nothing_matches(semantic_menu, monkeypatch):
    monkeypatch.setattr(menu_service_module, "search_semantic_menu_ids", lambda q, top_k=20: [])
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: _menu_items())

    service = menu_service_module.MenuService()
    items, diag = service._search(query="pancakes")

    assert items == []
    assert diag["fallback_reason"] == "no_semantic_matches"


def test_existing_structured_search_still_works(monkeypatch):
    monkeypatch.setattr(menu_service_module, "is_semantic_menu_configured", lambda: False)
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: _menu_items())

    service = menu_service_module.MenuService()
    results = service.search(query="cold", dietary="vegan", temperature="cold")

    assert [i["id"] for i in results] == ["vanilla-cold-brew"]


def test_semantic_results_keep_candidate_ranking(semantic_menu, monkeypatch):
    monkeypatch.setattr(
        menu_service_module,
        "search_semantic_menu_ids",
        lambda q, top_k=20: ["affogato", "mocha", "vanilla-cold-brew"],
    )

    service = menu_service_module.MenuService()
    items, _ = service._search(query="dessert")

    assert [i["id"] for i in items] == ["affogato", "mocha", "vanilla-cold-brew"]


# ---------------------------------------------------------------------------
# 15. Embedding provider failure handling
# ---------------------------------------------------------------------------


def test_embedding_provider_failure_becomes_controlled_error():
    backend = _FakeEmbeddingBackend(error=RuntimeError("upstream exploded"))
    embedder = GeminiEmbedder(model_name="m", api_key="k", backend=backend)

    with pytest.raises(ProviderError, match="currently unavailable"):
        embedder.embed_query("warm drink")


# ---------------------------------------------------------------------------
# QdrantVectorStore.search behavior
# ---------------------------------------------------------------------------


def test_qdrant_search_returns_retrieved_chunks_for_menu():
    client = _FakeQdrantClient(
        exists=True,
        size=3,
        points=[_point("mocha"), _point("affogato", payload={"menu_id": "affogato"})],
    )
    store = _store(client)

    results = store.search([0.1, 0.2, 0.3], top_k=2)

    assert [r.chunk.document_id for r in results] == ["mocha", "affogato"]
    assert all(r.chunk.metadata.extra["menu_id"] == r.chunk.document_id for r in results)
    # Scores are internal — they are not part of the tool-facing contract.
    assert all(isinstance(r.score, float) for r in results)


# ---------------------------------------------------------------------------
# Referenced existing functionality (explicit smoke checks)
# ---------------------------------------------------------------------------


def test_search_menu_tool_still_delegates_to_service(monkeypatch):
    """search_menu tool wrapper and structured path remain intact."""
    from app.services.menu_tools import search_menu

    monkeypatch.setattr(menu_service_module, "is_semantic_menu_configured", lambda: False)
    fake = type("Fake", (), {})()
    fake.items = [_safety_item("latte", name="Latte", price=200)]
    fake.calls = []

    def _search(self, **kwargs):
        self.calls.append(kwargs)
        return self.items

    fake.search = _search.__get__(fake)
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: fake.items)

    output = search_menu.invoke({"query": "latte"})

    assert "Latte" in output
    assert "price 200" in output


# ---------------------------------------------------------------------------
# Integration tests (gated)
# ---------------------------------------------------------------------------

ENABLE_INTEGRATION = os.environ.get("RUN_INTEGRATION_TESTS", "0") == "1"


@pytest.mark.skipif(
    not ENABLE_INTEGRATION,
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)
class TestSemanticMenuIntegration:
    """Real Firestore + Qdrant round trip. Requires credentials in env."""

    def test_index_and_search_roundtrip(self):
        from app.repositories.menu import list_menu_items

        items = list_menu_items()
        assert items, "menu/ collection must be ingested to run this test"

        result = MenuIndexer().index(items)
        assert result.document_count == len(items)

        ids = search_semantic_menu_ids("creamy chocolate drink", top_k=5)
        assert ids, "expected at least one semantic result after indexing"

    def test_semantic_search_preserves_hard_filters(self):
        import app.services.menu_service as module

        module.is_semantic_menu_configured()  # ensure configured
        service = module.MenuService()
        items, diag = service._search(query="chocolate", max_price=250)
        assert diag["semantic_used"] is True
        assert all(i["price"] <= 250 for i in items)