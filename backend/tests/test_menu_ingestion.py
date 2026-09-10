"""Tests for menu ingestion validation and Firestore write logic.

Unit tests use mocked Firestore — no credentials required.
Integration tests (gated by RUN_INTEGRATION_TESTS=1) use real Firestore.
"""

import json
import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.menu_ingestion import (
    DATA_PATH,
    EXPECTED_CATEGORIES,
    EXPECTED_COUNT,
    EXPECTED_PER_CATEGORY,
    REQUIRED_FIELDS,
    MenuValidationError,
    ingest_menu,
    load_menu,
    run,
    validate_menu,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_ITEMS_PATH = DATA_PATH


def _make_item(item_id: str = "test-item", category: str = "Hot Coffee") -> dict:
    """Create a minimal valid menu item."""
    return {
        "id": item_id,
        "name": f"Test {item_id}",
        "category": category,
        "description": "A test item.",
        "ingredients": ["test"],
        "size": "250 ml",
        "price": 200,
        "dietary": ["vegan"],
        "caffeine": "medium",
        "temperature": "hot",
        "sweetness": "medium",
        "flavor_profile": ["sweet"],
        "tags": ["test"],
        "available": True,
    }


def _make_valid_dataset() -> list[dict]:
    """Build a valid 100-item dataset (20 per category)."""
    categories = sorted(EXPECTED_CATEGORIES)
    items = []
    for cat in categories:
        for i in range(EXPECTED_PER_CATEGORY):
            items.append(_make_item(f"{cat.lower().replace(' ', '-').replace('&', '')}-{i}", cat))
    return items


# ---------------------------------------------------------------------------
# load_menu
# ---------------------------------------------------------------------------


class TestLoadMenu:
    def test_loads_real_dataset(self):
        items = load_menu(VALID_ITEMS_PATH)
        assert isinstance(items, list)
        assert len(items) == 100

    def test_file_not_found(self, tmp_path):
        with pytest.raises(MenuValidationError, match="not found"):
            load_menu(tmp_path / "missing.json")

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json")
        with pytest.raises(MenuValidationError, match="Invalid JSON"):
            load_menu(path)

    def test_not_an_array(self, tmp_path):
        path = tmp_path / "object.json"
        path.write_text(json.dumps({"items": []}))
        with pytest.raises(MenuValidationError, match="Expected a JSON array"):
            load_menu(path)


# ---------------------------------------------------------------------------
# validate_menu
# ---------------------------------------------------------------------------


class TestValidateMenu:
    def test_valid_dataset(self):
        items = load_menu(VALID_ITEMS_PATH)
        validate_menu(items)  # should not raise

    def test_valid_synthetic_dataset(self):
        items = _make_valid_dataset()
        validate_menu(items)  # should not raise

    def test_wrong_total_count(self):
        items = _make_valid_dataset()[:99]
        with pytest.raises(MenuValidationError, match="Expected 100 items, got 99"):
            validate_menu(items)

    def test_duplicate_ids(self):
        items = _make_valid_dataset()
        items[0]["id"] = items[1]["id"]
        with pytest.raises(MenuValidationError, match="Duplicate IDs"):
            validate_menu(items)

    def test_missing_id_field(self):
        items = _make_valid_dataset()
        del items[0]["id"]
        with pytest.raises(MenuValidationError, match="missing 'id' field"):
            validate_menu(items)

    def test_missing_required_field(self):
        items = _make_valid_dataset()
        del items[5]["description"]
        with pytest.raises(MenuValidationError, match="missing fields"):
            validate_menu(items)

    def test_invalid_category(self):
        items = _make_valid_dataset()
        items[0]["category"] = "Smoothies"
        with pytest.raises(MenuValidationError, match="invalid category"):
            validate_menu(items)

    def test_wrong_category_count(self):
        items = _make_valid_dataset()
        # Move two "Tea" items to "Hot Coffee" → Tea=18, Hot Coffee=22
        tea_items = [i for i, item in enumerate(items) if item["category"] == "Tea"]
        items[tea_items[0]]["category"] = "Hot Coffee"
        items[tea_items[1]]["category"] = "Hot Coffee"
        with pytest.raises(MenuValidationError, match="has .* items, expected"):
            validate_menu(items)


# ---------------------------------------------------------------------------
# ingest_menu (unit — mocked Firestore)
# ---------------------------------------------------------------------------


class TestIngestMenu:
    @patch("app.menu_ingestion.get_firestore")
    def test_writes_all_items(self, mock_get_firestore):
        mock_db = MagicMock()
        mock_get_firestore.return_value = mock_db

        items = _make_valid_dataset()
        count = ingest_menu(items)

        assert count == 100
        mock_db.batch.assert_called_once()
        batch = mock_db.batch.return_value
        assert batch.set.call_count == 100

    @patch("app.menu_ingestion.get_firestore")
    def test_document_ids_match_item_ids(self, mock_get_firestore):
        mock_db = MagicMock()
        mock_get_firestore.return_value = mock_db

        # Track what document() is called with
        written_doc_ids = []
        original_document = mock_db.collection.return_value.document

        def track_document(doc_id):
            written_doc_ids.append(doc_id)
            ref = MagicMock()
            ref.id = doc_id
            return ref

        original_document.side_effect = track_document

        items = _make_valid_dataset()
        ingest_menu(items)

        expected_ids = {item["id"] for item in items}
        assert set(written_doc_ids) == expected_ids

    @patch("app.menu_ingestion.get_firestore")
    def test_document_data_is_complete_item(self, mock_get_firestore):
        mock_db = MagicMock()
        mock_get_firestore.return_value = mock_db

        item = _make_item("cappuccino", "Hot Coffee")
        ingest_menu([item])

        batch = mock_db.batch.return_value
        written_data = batch.set.call_args_list[0][0][1]
        assert written_data == item

    @patch("app.menu_ingestion.get_firestore")
    def test_idempotent_writes_same_docs(self, mock_get_firestore):
        mock_db = MagicMock()
        mock_get_firestore.return_value = mock_db

        items = _make_valid_dataset()
        ingest_menu(items)
        first_call_count = mock_db.batch.return_value.set.call_count

        mock_db.reset_mock()
        mock_get_firestore.return_value = mock_db
        ingest_menu(items)
        second_call_count = mock_db.batch.return_value.set.call_count

        assert first_call_count == second_call_count == 100

    @patch("app.menu_ingestion.get_firestore")
    def test_uses_menu_collection(self, mock_get_firestore):
        mock_db = MagicMock()
        mock_get_firestore.return_value = mock_db

        items = [_make_item("test-1")]
        ingest_menu(items)

        # Verify db.collection() was called with the "menu" collection
        mock_db.collection.assert_called_with("menu")

    @patch("app.menu_ingestion.get_firestore")
    def test_batch_commit_called(self, mock_get_firestore):
        mock_db = MagicMock()
        mock_get_firestore.return_value = mock_db

        ingest_menu([_make_item("x")])
        mock_db.batch.return_value.commit.assert_called_once()


# ---------------------------------------------------------------------------
# run (integration of load + validate + ingest, mocked Firestore)
# ---------------------------------------------------------------------------


class TestRun:
    @patch("app.menu_ingestion.get_firestore")
    def test_run_with_real_data(self, mock_get_firestore):
        mock_get_firestore.return_value = MagicMock()
        count = run(VALID_ITEMS_PATH)
        assert count == 100

    @patch("app.menu_ingestion.get_firestore")
    def test_run_with_custom_path(self, mock_get_firestore, tmp_path):
        mock_get_firestore.return_value = MagicMock()
        items = _make_valid_dataset()
        path = tmp_path / "menu.json"
        path.write_text(json.dumps(items))
        count = run(path)
        assert count == 100

    def test_run_validates_before_writing(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps([{"id": "only-one"}]))
        with pytest.raises(MenuValidationError):
            run(bad)


# ---------------------------------------------------------------------------
# Firestore integration tests (gated)
# ---------------------------------------------------------------------------

ENABLE_INTEGRATION = os.environ.get("RUN_INTEGRATION_TESTS", "0") == "1"

pytestmark_integration = pytest.mark.skipif(
    not ENABLE_INTEGRATION,
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


@pytest.mark.skipif(
    not ENABLE_INTEGRATION,
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)
class TestIngestionIntegration:
    """Real Firestore tests — skipped unless RUN_INTEGRATION_TESTS=1."""

    @pytest.fixture(autouse=True)
    def _setup_firestore(self):
        from app.firestore_client import get_firestore, reset_firestore

        reset_firestore()
        self.db = get_firestore()
        yield
        reset_firestore()

    def _cleanup(self):
        docs = list(self.db.collection("menu").stream())
        for doc in docs:
            doc.reference.delete()

    def test_ingest_writes_to_firestore(self):
        items = _make_valid_dataset()
        count = ingest_menu(items)
        assert count == 100

        docs = list(self.db.collection("menu").stream())
        assert len(docs) == 100

        self._cleanup()

    def test_ingest_is_idempotent(self):
        items = _make_valid_dataset()
        ingest_menu(items)
        ingest_menu(items)

        docs = list(self.db.collection("menu").stream())
        assert len(docs) == 100

        self._cleanup()

    def test_ingest_does_not_delete_other_docs(self):
        self.db.collection("menu").document("_test_marker").set({"test": True})

        items = _make_valid_dataset()
        ingest_menu(items)

        marker = self.db.collection("menu").document("_test_marker").get()
        assert marker.exists

        docs = list(self.db.collection("menu").stream())
        assert len(docs) == 101  # 100 items + 1 marker

        self._cleanup()

    def test_run_end_to_end(self):
        count = run(VALID_ITEMS_PATH)
        assert count == 100

        doc = self.db.collection("menu").document("classic-espresso").get()
        assert doc.exists
        assert doc.to_dict()["name"] == "Classic Espresso"

        self._cleanup()
