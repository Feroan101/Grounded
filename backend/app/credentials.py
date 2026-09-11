import logging
import os
from pathlib import Path

import google.auth
import google.auth.credentials
from google.auth import environment_vars
from google.oauth2 import service_account

from app.config import FIREBASE_PROJECT_ID

logger = logging.getLogger(__name__)

_FIRESTORE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_ADC_FILENAME = "application_default_credentials.json"


def get_explicit_credentials_path() -> str | None:
    """Path from ``GOOGLE_APPLICATION_CREDENTIALS`` (tilde-expanded), if set.

    This is the standard mechanism for locating the Google service-account
    JSON, both locally (a filesystem path) and in production (the mounted
    Render Secret File, e.g. ``/etc/secrets/...``). The env value may use
    ``~`` (e.g. ``~/.secrets/...``); it is expanded here so validation and the
    loader agree on the real path. Returns ``None`` when the variable is
    unset or empty.
    """
    explicit = os.environ.get(environment_vars.CREDENTIALS, "").strip()
    if not explicit:
        return None
    return os.path.expanduser(explicit)


def _gcloud_adc_file() -> str | None:
    """Well-known gcloud ADC file (``gcloud auth application-default login``)."""
    config_dir = os.environ.get(environment_vars.CLOUD_SDK_CONFIG_DIR, "")
    if not config_dir:
        config_dir = str(Path.home() / ".config" / "gcloud")
    path = Path(config_dir, _ADC_FILENAME)
    return str(path) if path.is_file() else None


def _is_readable_file(path: str) -> bool:
    try:
        with Path(path).open("rb"):
            return True
    except OSError:
        return False


def is_adc_available() -> bool:
    """Whether ADC can be loaded from an explicit local source without probing
    the GCE metadata server.

    ``google.auth.default()`` falls back to a synchronous probe of
    ``metadata.google.internal`` when no explicit credential exists. On a host
    with no metadata server that probe can stall for a very long time (broken
    DNS / blackholed link-local traffic), so we only attempt ADC when an
    explicit, local credential source is present:

      * ``GOOGLE_APPLICATION_CREDENTIALS`` pointing at an existing, readable
        file, or
      * the well-known gcloud ADC file
        (``$CLOUDSDK_CONFIG/application_default_credentials.json`` or
        ``~/.config/gcloud/application_default_credentials.json``).

    This mirrors google-auth's own resolution order up to (but excluding) the
    metadata-server step.
    """
    explicit = get_explicit_credentials_path()
    if explicit and _is_readable_file(explicit):
        return True
    return _gcloud_adc_file() is not None


def get_credentials() -> google.auth.credentials.Credentials:
    """Load Google Cloud credentials for the backend's Firestore reads.

    ``GOOGLE_APPLICATION_CREDENTIALS`` is the standard mechanism: when it is
    set, the file MUST exist and be readable, and we fail loudly with the
    offending path rather than guessing. When it is unset we fall back to the
    well-known gcloud ADC file used by ``gcloud auth application-default
    login``. We never probe the GCE metadata server, so startup never stalls
    on a host with no metadata service.

    Raises RuntimeError with an actionable message if no credentials are found.
    """
    explicit = get_explicit_credentials_path()
    if explicit:
        path = Path(explicit)
        try:
            with path.open("rb"):
                pass
        except OSError as exc:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS is set but the file is missing "
                f"or cannot be read: {explicit}"
            ) from exc
        try:
            creds = service_account.Credentials.from_service_account_file(
                explicit, scopes=_FIRESTORE_SCOPES
            )
            project = creds.project_id
        except Exception as exc:  # malformed JSON, invalid key material, etc.
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS points to a file that could "
                f"not be loaded as Google credentials: {explicit}"
            ) from exc
        logger.info(
            "ADC loaded from GOOGLE_APPLICATION_CREDENTIALS (project=%s, type=%s)",
            project or FIREBASE_PROJECT_ID,
            type(creds).__name__,
        )
        return creds

    gcloud_file = _gcloud_adc_file()
    if gcloud_file:
        creds, project = google.auth.default(scopes=_FIRESTORE_SCOPES)
        logger.info(
            "ADC loaded from gcloud ADC file (project=%s, type=%s)",
            project or FIREBASE_PROJECT_ID,
            type(creds).__name__,
        )
        return creds

    raise RuntimeError(
        "No Google Cloud credentials found.\n\n"
        "GOOGLE_APPLICATION_CREDENTIALS is the standard mechanism. Set it to "
        "a Google service-account JSON file, for example in backend/.env:\n"
        "  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json\n\n"
        "The backend never probes the GCE metadata server, so a missing "
        "credential is reported here instead of stalling startup."
    )