import logging
import os
from pathlib import Path

import google.auth
import google.auth.credentials
from google.auth import environment_vars

from app.config import FIREBASE_PROJECT_ID

logger = logging.getLogger(__name__)

_FIRESTORE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_ADC_FILENAME = "application_default_credentials.json"


def is_adc_available() -> bool:
    """Whether ADC can be loaded from an explicit local source without probing
    the GCE metadata server.

    ``google.auth.default()`` falls back to a synchronous probe of
    ``metadata.google.internal`` when no explicit credential exists. On a host
    with no metadata server that probe can stall for a very long time (broken
    DNS / blackholed link-local traffic), so we only attempt ADC when an
    explicit, local credential source is present:

      * ``GOOGLE_APPLICATION_CREDENTIALS`` pointing at an existing file, or
      * the well-known gcloud ADC file
        (``$CLOUDSDK_CONFIG/application_default_credentials.json`` or
        ``~/.config/gcloud/application_default_credentials.json``).

    This mirrors google-auth's own resolution order up to (but excluding) the
    metadata-server step.
    """
    explicit = os.environ.get(environment_vars.CREDENTIALS, "")
    if explicit and Path(explicit).is_file():
        return True

    config_dir = os.environ.get(environment_vars.CLOUD_SDK_CONFIG_DIR, "")
    if not config_dir:
        config_dir = str(Path.home() / ".config" / "gcloud")
    return Path(config_dir, _ADC_FILENAME).is_file()


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
