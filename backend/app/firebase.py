import logging

import firebase_admin
from firebase_admin import credentials

from app.config import FIREBASE_CREDENTIALS_PATH, FIREBASE_PROJECT_ID
from app.credentials import is_adc_available

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase():
    """Initialize Firebase Admin SDK (best-effort, local-first).

    Resolution order for credentials:
      1. FIREBASE_CREDENTIALS_PATH — explicit service-account JSON (if available)
      2. Explicit Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS
         or the well-known gcloud ADC file)
      3. Project ID only — Firestore calls will fail clearly at use-time, and
         Firebase auth keeps working (token verification uses public JWKS and
         does not need credentials).

    Startup must never block on google-auth's GCE metadata-server probe: on a
    host without a metadata server that probe can stall indefinitely instead of
    failing. DAC is therefore only attempted when an explicit local credential
    source exists (``is_adc_available``), so startup never hangs when Firestore
    credentials are not configured yet.
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

    if is_adc_available():
        # ADC via an explicit env var / well-known file only — this reads from
        # disk and never probes the metadata server.
        import google.auth

        adc_creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        firebase_admin.initialize_app(
            cred=adc_creds, options={"projectId": FIREBASE_PROJECT_ID}
        )
        logger.info("Firebase Admin initialized with ADC")
        _initialized = True
        return

    firebase_admin.initialize_app(options={"projectId": FIREBASE_PROJECT_ID})
    logger.warning(
        "Firebase Admin initialized with project ID only — "
        "Firestore access will not work without credentials"
    )
    _initialized = True