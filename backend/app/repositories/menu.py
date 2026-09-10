from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.firestore_client import get_firestore

COLLECTION = "menu"


def get_menu_item(item_id: str) -> dict | None:
    db = get_firestore()
    doc = db.collection(COLLECTION).document(item_id).get()
    if doc.exists:
        return doc.to_dict() | {"id": doc.id}
    return None


def list_menu_items(category: str | None = None) -> list[dict]:
    """Return all menu items, optionally narrowed by category in Firestore.

    Filtering beyond ``category`` (free-text query, price, dietary, caffeine,
    temperature, sweetness, flavor, availability) is applied by the service
    layer, which searches the returned documents client-side.
    """
    db = get_firestore()
    q: firestore.Query = db.collection(COLLECTION)

    if category:
        q = q.where(filter=FieldFilter("category", "==", category))

    return [doc.to_dict() | {"id": doc.id} for doc in q.stream()]


def save_menu_item(item_id: str, data: dict) -> None:
    db = get_firestore()
    db.collection(COLLECTION).document(item_id).set(data, merge=True)
