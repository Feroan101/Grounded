import logging

import google.auth
import google.auth.credentials

from app.config import FIREBASE_PROJECT_ID

logger = logging.getLogger(__name__)

_FIRESTORE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def get_credentials() -> google.auth.credentials.Credentials:
    """Load Google Cloud credentials via Application Default Credentials.

    Resolution order:
      1. GOOGLE_APPLICATION_CREDENTIALS env var (service-account JSON or WIF config)
      2. gcloud CLI ADC (gcloud auth application-default login)
      3. Metadata server (GCE, Cloud Run, GKE)

    Raises RuntimeError with an actionable message if no credentials are found.
    """
    try:
        creds, project = google.auth.default(scopes=_FIRESTORE_SCOPES)
        logger.info(
            "ADC loaded (project=%s, type=%s)",
            project or FIREBASE_PROJECT_ID,
            type(creds).__name__,
        )
        return creds
    except google.auth.exceptions.DefaultCredentialsError:
        raise RuntimeError(
            "No Google Cloud credentials found.\n\n"
            "For local development:\n"
            "  1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install\n"
            "  2. Run: gcloud auth application-default login\n"
            "  3. Restart the backend\n\n"
            "For Render deployment:\n"
            "  Configure Workload Identity Federation or set\n"
            "  GOOGLE_APPLICATION_CREDENTIALS to a valid credential file.\n"
        ) from None
