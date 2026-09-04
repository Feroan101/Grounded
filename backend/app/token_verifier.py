import google.auth.transport.requests
import google.oauth2.id_token

from app.config import FIREBASE_PROJECT_ID

_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
_ISSUER_PREFIX = "https://securetoken.google.com/"

_request = google.auth.transport.requests.Request()


def verify_firebase_token(id_token: str) -> dict:
    if not FIREBASE_PROJECT_ID:
        raise ValueError("FIREBASE_PROJECT_ID is not configured")

    decoded = google.oauth2.id_token.verify_token(
        id_token,
        request=_request,
        audience=FIREBASE_PROJECT_ID,
        certs_url=_CERTS_URL,
    )

    decoded["uid"] = decoded["sub"]
    return decoded
