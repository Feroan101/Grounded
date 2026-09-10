"""Menu ingestion: validate and write canonical menu.json to Firestore.

Usage:
    python -m app.menu_ingestion              # ingest from default path
    python -m app.menu_ingestion path/to.json # ingest from custom path

Firestore structure:
    menu/{item_id}  — one document per menu item, complete item fields.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from app.firestore_client import get_firestore
from app.repositories.menu import COLLECTION

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "menu.json"

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

EXPECTED_COUNT = 100
EXPECTED_PER_CATEGORY = 20


class MenuValidationError(Exception):
    """Raised when the menu dataset fails validation."""


def load_menu(path: Path | str = DATA_PATH) -> list[dict]:
    """Load and parse the menu JSON file."""
    path = Path(path)
    if not path.exists():
        raise MenuValidationError(f"Menu file not found: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise MenuValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, list):
        raise MenuValidationError(
            f"Expected a JSON array, got {type(data).__name__}"
        )

    return data


def validate_menu(items: list[dict]) -> None:
    """Validate the menu dataset. Raises MenuValidationError on failure."""

    if len(items) != EXPECTED_COUNT:
        raise MenuValidationError(
            f"Expected {EXPECTED_COUNT} items, got {len(items)}"
        )

    ids = [item.get("id") for item in items]
    if None in ids:
        raise MenuValidationError("One or more items missing 'id' field")

    if len(set(ids)) != len(ids):
        seen: set[str] = set()
        duplicates: list[str] = []
        for item_id in ids:
            if item_id in seen:
                duplicates.append(item_id)
            seen.add(item_id)
        raise MenuValidationError(f"Duplicate IDs: {duplicates}")

    for item in items:
        missing = REQUIRED_FIELDS - set(item)
        if missing:
            raise MenuValidationError(
                f"Item '{item.get('id', '?')}' missing fields: {missing}"
            )

    category_counts: dict[str, int] = {}
    for item in items:
        cat = item["category"]
        if cat not in EXPECTED_CATEGORIES:
            raise MenuValidationError(
                f"Item '{item['id']}' has invalid category: '{cat}'. "
                f"Valid categories: {sorted(EXPECTED_CATEGORIES)}"
            )
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for category in EXPECTED_CATEGORIES:
        count = category_counts.get(category, 0)
        if count != EXPECTED_PER_CATEGORY:
            raise MenuValidationError(
                f"Category '{category}' has {count} items, expected {EXPECTED_PER_CATEGORY}"
            )


def ingest_menu(items: list[dict]) -> int:
    """Write validated menu items to Firestore. Returns count written.

    Uses set() (not merge) so each write fully replaces the document.
    This is idempotent: running multiple times overwrites the same docs.
    Only the specified documents are touched — no other Firestore data.
    """
    db = get_firestore()
    batch = db.batch()
    count = 0

    for item in items:
        item_id = item["id"]
        ref = db.collection(COLLECTION).document(item_id)
        batch.set(ref, item)
        count += 1

    batch.commit()
    logger.info("Ingested %d menu items into Firestore collection '%s'", count, COLLECTION)
    return count


def run(path: Path | str = DATA_PATH) -> int:
    """Load, validate, and ingest the menu. Returns count written."""
    items = load_menu(path)
    validate_menu(items)
    count = ingest_menu(items)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_PATH
    try:
        written = run(target)
        print(f"Done — {written} menu items written to Firestore.")
    except MenuValidationError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)
