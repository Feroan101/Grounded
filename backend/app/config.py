import os

from dotenv import load_dotenv

load_dotenv()

# Firebase project ID — used for token verification (public, no secrets)
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "grounded-coffeeshop-ai")

# Firebase Admin credentials — OPTIONAL for auth, REQUIRED for Firestore.
#
# Token verification uses Google's public JWKS keys and does NOT need credentials.
# Credentials are only needed for Admin SDK operations (Firestore, user management).
#
# Local development (recommended):
#   gcloud auth application-default login
#   Then GOOGLE_APPLICATION_CREDENTIALS is set automatically.
#
# Alternative (if you have a service-account JSON):
#   FIREBASE_CREDENTIALS_PATH=/home/you/.grounded/firebase-service-account.json
#
# Render (when Firestore access is needed):
#   Configure Workload Identity Federation or set
#   GOOGLE_APPLICATION_CREDENTIALS to the mounted credential file.
FIREBASE_CREDENTIALS_PATH = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000",
).split(",")

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))
