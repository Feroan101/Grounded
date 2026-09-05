from google.cloud import firestore

from app.firestore_client import get_firestore

COLLECTION = "menu"


def get_menu_item(item_id: str) -> dict | None:
    db = get_firestore()
    doc = db.collection(COLLECTION).document(item_id).get()
    if doc.exists:
        return doc.to_dict() | {"id": doc.id}
    return None


def search_menu(query: str | None = None, category: str | None = None) -> list[dict]:
    db = get_firestore()
    ref = db.collection(COLLECTION)
    q: firestore.Query = ref

    if category:
        q = q.where("category", "==", category)

    docs = q.stream()
    results = [doc.to_dict() | {"id": doc.id} for doc in docs]

    if query:
        query_lower = query.lower()
        results = [
            item for item in results
            if query_lower in item.get("name", "").lower()
            or query_lower in item.get("description", "").lower()
        ]

    return results


def save_menu_item(item_id: str, data: dict) -> None:
    db = get_firestore()
    db.collection(COLLECTION).document(item_id).set(data, merge=True)
