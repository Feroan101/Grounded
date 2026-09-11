from google.cloud import firestore

from app.config import ORDER_HISTORY_FETCH_LIMIT
from app.firestore_client import get_firestore


def _orders_col(uid: str) -> firestore.CollectionReference:
    return get_firestore().collection("users").document(uid).collection("orders")


def save_order(uid: str, items: list[dict], total: float | None = None) -> str:
    ref = _orders_col(uid).add(
        {
            "items": items,
            "total": total,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )[1]
    return ref.id


def get_order_history(uid: str, limit: int = ORDER_HISTORY_FETCH_LIMIT) -> list[dict]:
    """Return the customer's newest order documents, bounded read-only.

    User-scoped to ``users/{uid}/orders`` (the UID comes from a verified
    Firebase token). Newest first, deterministic ordering, never more than
    ``limit`` documents, graceful empty result. Never opens arbitrary paths.
    """
    docs = (
        _orders_col(uid)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [doc.to_dict() | {"id": doc.id} for doc in docs]


def get_order(uid: str, order_id: str) -> dict | None:
    doc = _orders_col(uid).document(order_id).get()
    if doc.exists:
        return doc.to_dict() | {"id": doc.id}
    return None
