import logging

from google.cloud import firestore

from app.config import FIREBASE_PROJECT_ID
from app.credentials import get_credentials

logger = logging.getLogger(__name__)

_db: firestore.Client | None = None


def get_firestore() -> firestore.Client:
    """Return a Firestore client, initializing on first call.

    Uses ADC for authentication. The client is reused across requests.
    """
    global _db
    if _db is not None:
        return _db

    creds = get_credentials()
    _db = firestore.Client(
        project=FIREBASE_PROJECT_ID,
        credential=creds,
    )
    logger.info("Firestore client initialized (project=%s)", FIREBASE_PROJECT_ID)
    return _db


def reset_firestore() -> None:
    """Reset the client (for testing)."""
    global _db
    _db = None
