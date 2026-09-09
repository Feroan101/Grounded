"""Validation tests for the canonical Grounded menu dataset."""
import json
from pathlib import Path

MENU_PATH = Path(__file__).resolve().parents[1] / "data" / "menu.json"

EXPECTED_CATEGORIES = {
    "Hot Coffee",
    "Cold Coffee",
    "Non-Coffee Beverages",
    "Tea",
    "Food & Bakery",
}

REQUIRED_FIELDS = {
    "id",
    "name",
    "category",
    "description",
    "ingredients",
    "size",
    "price",
    "dietary",
    "caffeine",
    "temperature",
    "sweetness",
    "flavor_profile",
    "tags",
    "available",
}


def load_menu():
    with open(MENU_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_menu_json_parses():
    items = load_menu()
    assert isinstance(items, list)


def test_total_item_count():
    items = load_menu()
    assert len(items) == 100


def test_category_counts():
    items = load_menu()
    counts = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    assert set(counts) == EXPECTED_CATEGORIES
    for category in EXPECTED_CATEGORIES:
        assert counts[category] == 20, f"{category} has {counts[category]} items"


def test_ids_are_unique():
    items = load_menu()
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))


def test_ids_are_kebab_case():
    items = load_menu()
    for item in items:
        assert item["id"] == item["id"].lower()
        assert " " not in item["id"]


def test_required_fields_present():
    items = load_menu()
    for item in items:
        missing = REQUIRED_FIELDS - set(item)
        assert not missing, f"item {item.get('id')} missing {missing}"


def test_prices_are_realistic():
    items = load_menu()
    for item in items:
        assert isinstance(item["price"], int), item["id"]
        assert item["price"] > 0, item["id"]


def test_available_is_boolean():
    items = load_menu()
    for item in items:
        assert isinstance(item["available"], bool), item["id"]


def test_ingredients_and_flavors_are_nonempty():
    items = load_menu()
    for item in items:
        assert isinstance(item["ingredients"], list) and item["ingredients"], item["id"]
        assert isinstance(item["flavor_profile"], list) and item["flavor_profile"], item["id"]
        assert isinstance(item["tags"], list) and item["tags"], item["id"]
        assert isinstance(item["dietary"], list), item["id"]


def test_no_duplicate_names():
    items = load_menu()
    names = [item["name"] for item in items]
    assert len(names) == len(set(names))
