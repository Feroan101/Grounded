import firebase_admin
from firebase_admin import credentials

from app.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_PROJECT_ID

_initialized = False


def init_firebase():
    """Initialize Firebase Admin SDK if credentials are available.

    Token verification does NOT require this — it uses Google's public JWKS.
    This is only needed for Admin SDK operations (Firestore, user management, etc.).
    """
    global _initialized
    if _initialized:
        return

    if FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _initialized = True
    else:
        try:
            firebase_admin.initialize_app(options={"projectId": FIREBASE_PROJECT_ID})
            _initialized = True
        except Exception:
            pass
