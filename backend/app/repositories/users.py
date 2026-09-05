from google.cloud import firestore

from app.firestore_client import get_firestore


def _user_doc(uid: str) -> firestore.DocumentReference:
    return get_firestore().collection("users").document(uid)


def get_profile(uid: str) -> dict | None:
    doc = _user_doc(uid).collection("profile").document("current").get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_profile(uid: str, data: dict) -> None:
    _user_doc(uid).collection("profile").document("current").set(data, merge=True)


def get_preferences(uid: str) -> dict | None:
    doc = _user_doc(uid).collection("preferences").document("current").get()
    if doc.exists:
        return doc.to_dict()
    return None


def save_preferences(uid: str, data: dict) -> None:
    _user_doc(uid).collection("preferences").document("current").set(data, merge=True)


def update_preferences(uid: str, updates: dict) -> None:
    _user_doc(uid).collection("preferences").document("current").set(updates, merge=True)
