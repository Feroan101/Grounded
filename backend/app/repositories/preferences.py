"""User preferences data access.

Preferences live at ``users/{uid}/preferences/current`` (user-scoped). The
document is shared with the frontend settings UI, so this repository is the
single owner of that path on the backend side. The UID must always come from
the verified Firebase token — never from the client.
"""
from google.cloud import firestore

from app.firestore_client import get_firestore


def _preferences_doc(uid: str) -> firestore.DocumentReference:
    return get_firestore().collection("users").document(uid).collection("preferences").document("current")


def get_preferences(uid: str) -> dict | None:
    doc = _preferences_doc(uid).get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_preferences(uid: str, data: dict) -> None:
    _preferences_doc(uid).set(data, merge=True)


def update_preferences(uid: str, updates: dict) -> None:
    _preferences_doc(uid).set(updates, merge=True)