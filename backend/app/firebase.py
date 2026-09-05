import logging

import firebase_admin
from firebase_admin import credentials

from app.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_PROJECT_ID

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase():
    """Initialize Firebase Admin SDK.

    Resolution order for credentials:
      1. FIREBASE_CREDENTIALS_PATH — explicit service-account JSON (if available)
      2. Application Default Credentials (gcloud ADC or metadata server)
      3. Project ID only (token verification works, Firestore won't)

    Token verification does NOT require this — it uses Google's public JWKS.
    This is needed for Admin SDK operations (Firestore, user management, etc.).
    """
    global _initialized
    if _initialized:
        return

    if FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin initialized with certificate")
        _initialized = True
        return

    try:
        import google.auth

        adc_creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        firebase_admin.initialize_app(
            cred=adc_creds, options={"projectId": FIREBASE_PROJECT_ID}
        )
        logger.info("Firebase Admin initialized with ADC")
        _initialized = True
    except Exception:
        firebase_admin.initialize_app(options={"projectId": FIREBASE_PROJECT_ID})
        logger.warning(
            "Firebase Admin initialized with project ID only — "
            "Firestore access will not work without credentials"
        )
        _initialized = True
