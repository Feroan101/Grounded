import logging

import firebase_admin
from firebase_admin import credentials

from app.config import FIREBASE_PROJECT_ID
from app.credentials import get_explicit_credentials_path, is_adc_available

logger = logging.getLogger(__name__)

_initialized = False


def init_firebase():
    """Initialize Firebase Admin SDK (best-effort, local-first).

    Resolution order for credentials:
      1. GOOGLE_APPLICATION_CREDENTIALS — the standard mechanism. Points at a
         service-account JSON locally or at the mounted Render Secret File
         (e.g. /etc/secrets/grounded-coffeeshop-ai.json).
      2. Explicit Application Default Credentials (the well-known gcloud ADC
         file, resolvable via ``is_adc_available``)
      3. Project ID only — Firestore calls will fail clearly at use-time, and
         Firebase auth keeps working (token verification uses public JWKS and
         does not need credentials).

    Startup must never block on google-auth's GCE metadata-server probe: on a
    host without a metadata server that probe can stall indefinitely instead of
    failing. ADC is therefore only attempted when an explicit local credential
    source exists (``is_adc_available``), so startup never hangs when Firestore
    credentials are not configured yet.
    """
    global _initialized
    if _initialized:
        return

    explicit = get_explicit_credentials_path()
    if explicit:
        # Standard mechanism: GOOGLE_APPLICATION_CREDENTIALS. Best-effort —
        # Firebase auth (JWKS token verification) keeps working without it.
        try:
            cred = credentials.Certificate(explicit)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin initialized with GOOGLE_APPLICATION_CREDENTIALS")
            _initialized = True
            return
        except Exception as exc:  # noqa: BLE001 — credential init is best-effort
            logger.warning(
                "Firebase Admin: GOOGLE_APPLICATION_CREDENTIALS unusable (%s) — "
                "falling back to ADC / project-only",
                exc,
            )

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