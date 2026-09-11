"""Firestore integration tests.

These tests require real Google Cloud credentials (ADC).
They will be SKIPPED if no credentials are available.

Run:
    python -m pytest tests/test_firestore_integration.py -v

To set up credentials:
    gcloud auth application-default login
"""

import os
import uuid

import pytest

# Skip entire module if not explicitly enabled
ENABLE_INTEGRATION = os.environ.get("RUN_INTEGRATION_TESTS", "0") == "1"

pytestmark = pytest.mark.skipif(
    not ENABLE_INTEGRATION,
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


@pytest.fixture(scope="module")
def firestore_client():
    """Initialize a real Firestore client for testing."""
    from app.firestore_client import get_firestore, reset_firestore

    reset_firestore()
    client = get_firestore()
    yield client
    reset_firestore()


@pytest.fixture(scope="module")
def test_uid():
    """Generate a unique test UID."""
    return f"test-{uuid.uuid4().hex[:12]}"


class TestFirestoreConnectivity:
    """Basic connectivity and CRUD tests."""

    def test_client_initializes(self, firestore_client):
        assert firestore_client is not None
        assert firestore_client.project == "grounded-coffeeshop-ai"

    def test_write_and_read(self, firestore_client, test_uid):
        doc_ref = firestore_client.collection("_test").document(test_uid)
        doc_ref.set({"hello": "world", "uid": test_uid})

        doc = doc_ref.get()
        assert doc.exists
        assert doc.to_dict()["hello"] == "world"

        # Cleanup
        doc_ref.delete()

    def test_menu_repository(self):
        from app.repositories.menu import save_menu_item, get_menu_item

        item_id = f"test-item-{uuid.uuid4().hex[:8]}"
        test_data = {
            "name": "Test Latte",
            "category": "drinks",
            "price": 180.0,
            "available": True,
        }

        save_menu_item(item_id, test_data)
        result = get_menu_item(item_id)

        assert result is not None
        assert result["name"] == "Test Latte"
        assert result["price"] == 180.0

        # Cleanup
        from app.firestore_client import get_firestore
        get_firestore().collection("menu").document(item_id).delete()

    def test_user_repository(self, test_uid):
        from app.repositories.users import (
            save_profile,
            get_profile,
            save_preferences,
            get_preferences,
        )

        save_profile(test_uid, {"email": "test@example.com", "displayName": "Test User"})
        profile = get_profile(test_uid)
        assert profile is not None
        assert profile["email"] == "test@example.com"

        save_preferences(test_uid, {"milk": "oat", "sweetness": "low"})
        prefs = get_preferences(test_uid)
        assert prefs is not None
        assert prefs["milk"] == "oat"

    def test_conversation_repository(self, test_uid):
        from app.repositories.conversations import (
            create_conversation,
            append_message,
            get_conversation_messages,
            list_conversations,
        )

        conv_id = create_conversation(test_uid)
        assert conv_id is not None

        append_message(test_uid, conv_id, "user", "Hello")
        append_message(test_uid, conv_id, "assistant", "Hi there!")

        messages = get_conversation_messages(test_uid, conv_id)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["content"] == "Hi there!"

        conversations = list_conversations(test_uid)
        assert len(conversations) >= 1

    def test_order_repository(self, test_uid):
        from app.repositories.orders import save_order, get_order_history

        order_id = save_order(
            test_uid,
            items=[{"name": "Latte", "qty": 1}],
            total=180.0,
        )
        assert order_id is not None

        history = get_order_history(test_uid, limit=1)
        assert len(history) >= 1
        assert history[0]["total"] == 180.0

    def test_order_history_service(self, test_uid):
        """Service bounds and formats the real stored order schema."""
        from app.firestore_client import get_firestore
        from app.repositories.orders import save_order
        from app.services.order_history_service import get_order_history_service

        save_order(
            test_uid,
            items=[{"name": "Cappuccino", "qty": 2}, {"name": "Mocha", "qty": 1}],
            total=470.0,
        )

        records = get_order_history_service().get_history(test_uid)

        assert records
        assert records[0].total == "470"
        assert records[0].items[0] == {"name": "Cappuccino", "qty": 2}
        assert records[0].date is not None  # server timestamp present
