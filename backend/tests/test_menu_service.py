"""Unit tests for MenuService filtering (Firestore is mocked)."""
import os

import pytest

from app.errors import ProviderError
from app.services import menu_service as menu_service_module
from app.services.menu_service import MenuService


def _item(
    item_id: str = "cappuccino",
    *,
    name: str = "Cappuccino",
    category: str = "Hot Coffee",
    description: str = "Espresso with steamed milk.",
    ingredients=(),
    price=240,
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


@pytest.fixture
def sample_items():
    return [
        _item(
            "cappuccino",
            name="Cappuccino",
            category="Hot Coffee",
            ingredients=("espresso", "whole-milk"),
            price=240,
            dietary=("vegetarian",),
            caffeine="medium",
            temperature="hot",
            sweetness="medium",
            flavor_profile=("creamy", "bold"),
            tags=("milk-based",),
        ),
        _item(
            "iced-americano",
            name="Iced Americano",
            category="Cold Coffee",
            description="Espresso shaken over ice with cooling water.",
            ingredients=("espresso", "cold-water", "ice"),
            price=210,
            dietary=("vegan", "vegetarian"),
            caffeine="high",
            temperature="cold",
            sweetness="none",
            flavor_profile=("bold", "refreshing"),
            tags=("iced", "no-milk"),
        ),
        _item(
            "matcha-latte",
            name="Ceremonial Matcha Latte",
            category="Non-Coffee Beverages",
            ingredients=("matcha-powder", "whole-milk"),
            price=300,
            dietary=("vegetarian",),
            caffeine="low",
            temperature="hot",
            sweetness="low",
            flavor_profile=("earthy", "creamy"),
            tags=("matcha",),
        ),
        _item(
            "croissant",
            name="Butter Croissant",
            category="Food & Bakery",
            description="Flaky, buttery croissant.",
            ingredients=("butter", "flour"),
            price=180,
            dietary=("vegetarian",),
            caffeine="none",
            temperature="ambient",
            sweetness="low",
            flavor_profile=("buttery", "flaky"),
            tags=("bakery",),
        ),
        _item(
            "sold-out-brew",
            name="Vanilla Cold Brew",
            category="Cold Coffee",
            description="A slow-steeped cold brew with vanilla.",
            ingredients=("coffee",),
            price=260,
            dietary=("vegan",),
            caffeine="high",
            temperature="cold",
            sweetness="medium",
            flavor_profile=("smooth", "vanilla"),
            tags=("cold-brew",),
            available=False,
        ),
    ]


@pytest.fixture
def fake_repo(monkeypatch, sample_items):
    def _patch(items=None, exc=None):
        def _list_menu_items(category=None):
            if exc:
                raise exc
            return items if items is not None else sample_items

        monkeypatch.setattr(menu_service_module, "list_menu_items", _list_menu_items)
        return _list_menu_items

    _patch()
    return _patch


def _search(**kwargs):
    return MenuService().search(**kwargs)


@pytest.fixture(autouse=True)
def _structured_only(monkeypatch):
    """Unit tests exercise the deterministic structured path.

    They patch ``list_menu_items`` with fixture data, so semantic retrieval
    must be forced off regardless of whether real Qdrant/Gemini credentials
    happen to be present in the developer's local ``backend/.env``.
    """
    monkeypatch.setattr(
        menu_service_module, "is_semantic_menu_configured", lambda: False
    )


class TestMenuServiceSearch:
    def test_all_items_returned_without_filters(self, fake_repo):
        results = _search()
        assert len(results) == 4  # sold-out item is excluded by default
        # Results are sorted by name.
        assert [i["name"] for i in results] == sorted(i["name"] for i in results)

    def test_category_filter(self, fake_repo):
        results = _search(category="Cold Coffee")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_category_filter_is_case_insensitive(self, fake_repo):
        results = _search(category="cold coffee")
        assert len(results) == 1

    def test_max_price_filter(self, fake_repo):
        results = _search(max_price=210)
        names = {i["name"] for i in results}
        assert "Butter Croissant" in names  # 180
        assert "Iced Americano" in names  # 210
        assert "Cappuccino" not in names  # 240

    def test_dietary_filter(self, fake_repo):
        results = _search(dietary="vegan")
        names = {i["name"] for i in results}
        assert names == {"Iced Americano"}

    def test_caffeine_filter(self, fake_repo):
        results = _search(caffeine="high")
        names = {i["name"] for i in results}
        assert names == {"Iced Americano"}

    def test_temperature_filter(self, fake_repo):
        results = _search(temperature="cold")
        assert len(results) == 1
        assert results[0]["name"] == "Iced Americano"

    def test_sweetness_filter(self, fake_repo):
        results = _search(sweetness="none")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_flavor_enumerated_match(self, fake_repo):
        results = _search(flavor="creamy")
        names = {i["name"] for i in results}
        assert names == {"Cappuccino", "Ceremonial Matcha Latte"}

    def test_flavor_tag_match(self, fake_repo):
        results = _search(flavor="iced")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_available_default_excludes_sold_out(self, fake_repo):
        results = _search(category="Cold Coffee")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_available_false_returns_sold_out(self, fake_repo):
        results = _search(available=False)
        names = {i["name"] for i in results}
        assert names == {"Vanilla Cold Brew"}

    def test_free_text_matches_description(self, fake_repo):
        results = _search(query="shaken over ice")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_free_text_matches_ingredient(self, fake_repo):
        results = _search(query="matcha-powder")
        assert [i["name"] for i in results] == ["Ceremonial Matcha Latte"]

    def test_free_text_matches_flavor(self, fake_repo):
        results = _search(query="refreshing")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_free_text_matches_tag(self, fake_repo):
        results = _search(query="no-milk")
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_combined_filters(self, fake_repo):
        results = _search(query="iced", category="Cold Coffee", max_price=250)
        assert [i["name"] for i in results] == ["Iced Americano"]

    def test_no_match_returns_empty_list(self, fake_repo):
        assert _search(query="pancakes") == []

    def test_malformed_price_excluded_under_max_price(self, fake_repo, sample_items):
        bad = _item(
            "mystery-item",
            name="Mystery Item",
            description="Price on request.",
            price="on request",
        )
        fake_repo(items=sample_items + [bad])
        results = _search(max_price=999)
        assert "Mystery Item" not in {i["name"] for i in results}

    def test_upstream_failure_wrapped_as_provider_error(self, fake_repo):
        fake_repo(exc=RuntimeError("firestore unavailable"))
        with pytest.raises(ProviderError, match="menu is temporarily unavailable"):
            _search(query="latte")


ENABLE_INTEGRATION = os.environ.get("RUN_INTEGRATION_TESTS", "0") == "1"


@pytest.mark.skipif(
    not ENABLE_INTEGRATION,
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)
class TestMenuServiceIntegration:
    """Real Firestore tests — skipped unless RUN_INTEGRATION_TESTS=1."""

    def test_search_finds_documented_item(self):
        results = _search(query="cappuccino")
        assert results, "menu/ collection must be ingested to run this test"
        assert any("cappuccino" in i["name"].lower() for i in results)

    def test_category_filter_on_real_data(self):
        results = _search(category="Tea")
        assert results
        assert all(i["category"] == "Tea" for i in results)

    def test_saves_and_searches_unique_item(self):
        import uuid

        from app.repositories.menu import save_menu_item

        item_id = f"_search-menu-{uuid.uuid4().hex[:8]}"
        save_menu_item(
            item_id,
            {
                "name": "Test Search Latte",
                "category": "Hot Coffee",
                "description": "A unique integration-test item.",
                "ingredients": ["test"],
                "size": "240 ml",
                "price": 200,
                "dietary": ["vegan"],
                "caffeine": "medium",
                "temperature": "hot",
                "sweetness": "low",
                "flavor_profile": ["creamy"],
                "tags": ["integration-test"],
                "available": True,
            },
        )
        try:
            results = _search(query="integration-test")
            ids = {i["id"] for i in results}
            assert item_id in ids
        finally:
            from app.firestore_client import get_firestore

            get_firestore().collection("menu").document(item_id).delete()