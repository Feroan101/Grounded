from google.cloud import firestore

from app.firestore_client import get_firestore

# Preference access moved to its own module so the backend owns that document
# path in one place. Kept as re-exports so existing imports continue to work.
from app.repositories.preferences import (  # noqa: F401
    get_preferences,
    save_preferences,
    update_preferences,
)


def _user_doc(uid: str) -> firestore.DocumentReference:
    return get_firestore().collection("users").document(uid)


def get_profile(uid: str) -> dict | None:
    doc = _user_doc(uid).collection("profile").document("current").get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_profile(uid: str, data: dict) -> None:
    _user_doc(uid).collection("profile").document("current").set(data, merge=True)