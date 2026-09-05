import time

from google.cloud import firestore

from app.firestore_client import get_firestore


def _conversations_col(uid: str) -> firestore.CollectionReference:
    return get_firestore().collection("users").document(uid).collection("conversations")


def create_conversation(uid: str) -> str:
    col = _conversations_col(uid)
    ref = col.add({
        "createdAt": firestore.SERVER_TIMESTAMP,
        "updatedAt": firestore.SERVER_TIMESTAMP,
        "messageCount": 0,
    })[1]
    return ref.id


def append_message(uid: str, conversation_id: str, role: str, content: str) -> None:
    conv_ref = _conversations_col(uid).document(conversation_id)
    messages_ref = conv_ref.collection("messages")

    messages_ref.add({
        "role": role,
        "content": content,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })

    conv_ref.set({
        "updatedAt": firestore.SERVER_TIMESTAMP,
        "messageCount": firestore.Increment(1),
    }, merge=True)


def get_conversation_messages(uid: str, conversation_id: str, limit: int = 50) -> list[dict]:
    msgs = (
        _conversations_col(uid)
        .document(conversation_id)
        .collection("messages")
        .order_by("timestamp", direction=firestore.Query.ASCENDING)
        .limit(limit)
        .stream()
    )
    return [msg.to_dict() for msg in msgs]


def list_conversations(uid: str, limit: int = 20) -> list[dict]:
    docs = (
        _conversations_col(uid)
        .order_by("updatedAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [doc.to_dict() | {"id": doc.id} for doc in docs]


def save_summary(uid: str, conversation_id: str, summary: dict) -> None:
    _conversations_col(uid).document(conversation_id).collection("summaries").add(
        {
            "summary": summary,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )


def get_latest_summary(uid: str, conversation_id: str) -> dict | None:
    docs = (
        _conversations_col(uid)
        .document(conversation_id)
        .collection("summaries")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return doc.to_dict().get("summary")
    return None
