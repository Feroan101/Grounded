import os
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# Firebase project ID — used for token verification (public, no secrets)
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "grounded-coffeeshop-ai")

# Firestore named database. The project uses a custom-named database ("grounded")
# rather than the default Firestore database. Set FIRESTORE_DATABASE if your
# project uses a different name.
FIRESTORE_DATABASE = os.environ.get("FIRESTORE_DATABASE", "grounded")

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

# Comma-separated list of browser origins allowed to call the backend.
# ONLY read from the ecosystem. No hardcoded origins — if unset or empty,
# cross-origin requests are denied (default-deny). Callers MUST configure
# this per environment (local dev, production).
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in _raw_origins.split(",")
    if origin.strip()
]

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = _env_int("API_PORT", 8000)

# Render sets PORT automatically; prefer it when present.
API_PORT = _env_int("PORT", API_PORT)

# -----------------------------------------------------------------------------
# Application environment
# -----------------------------------------------------------------------------
# In production we never fall back to a development-only authentication path.
# ENVIRONMENT is used to guard any development-only behavior.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"


# -----------------------------------------------------------------------------
# AI / LLM
# -----------------------------------------------------------------------------
class LLMProvider(str, Enum):
    GEMINI = "gemini"
    # Future providers plug in here without touching the API layer.


# Model provider + model selection. The provider must be one of the supported
# enums so configuration errors are caught early.
LLM_PROVIDER = LLMProvider(os.environ.get("LLM_PROVIDER", LLMProvider.GEMINI.value))
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")

# Gemini API key — loaded through the configuration system. GEMINI_API_KEY is
# the canonical variable; GOOGLE_API_KEY is accepted as a fallback (the Gemini
# SDK's default). Empty is fine at startup: the LLM is created lazily and
# raises a clear ConfigurationError on first use. NEVER commit a real key.
GEMINI_API_KEY = (
    os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
).strip()

# Gemini embedding model used for semantic menu retrieval. Shares the same
# GEMINI_API_KEY credential as the chat model. gemini-embedding-001 is the
# stable, generally-available text embedding model.
GEMINI_EMBEDDING_MODEL = os.environ.get(
    "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
).strip()

# Token/usage limits
LLM_MAX_TOKENS = _env_int("LLM_MAX_TOKENS", 1024)
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.4"))

# Which config section drives provider setup. Not a secret — never the key.
LLM_PROVIDER_NAME = LLM_PROVIDER.value


# -----------------------------------------------------------------------------
# RAG
# -----------------------------------------------------------------------------
class VectorStoreProvider(str, Enum):
    # We deliberately do NOT hard-code a vector database provider yet.
    # Set VECTOR_STORE_PROVIDER when one has been chosen for the deployment.
    QDRANT_CLOUD = "qdrant_cloud"
    PINECONE = "pinecone"


VECTOR_STORE_PROVIDER = os.environ.get(
    "VECTOR_STORE_PROVIDER", ""
).strip().lower() or None

# External vector store connection (never store secrets inline; use env at
# deploy time). These are optional until a provider is selected.
VECTOR_STORE_HOST = os.environ.get("VECTOR_STORE_HOST", "")
VECTOR_STORE_COLLECTION = os.environ.get("VECTOR_STORE_COLLECTION", "grounded_menu")

# Qdrant Cloud connection for semantic menu retrieval. Never store real
# credentials in source or tests; supply them per-environment.
QDRANT_URL = os.environ.get("QDRANT_URL", "").strip()
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "").strip()
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "grounded-menu").strip()

# Number of semantic candidates to fetch from the vector store before applying
# hard structured filters. Larger than the 8-item display cap so hard
# constraints can narrow results without starving the final list.
MENU_SEMANTIC_TOP_K = _env_int("MENU_SEMANTIC_TOP_K", 20)


def is_semantic_menu_configured() -> bool:
    """Whether hybrid semantic menu retrieval is fully configured.

    Requires the Qdrant provider, Qdrant connection credentials, and the shared
    Gemini API key. Semantic retrieval silently stays off until all are set.
    """
    qdrant_provider = VECTOR_STORE_PROVIDER in {"qdrant", "qdrant_cloud"}
    return bool(qdrant_provider and QDRANT_URL and QDRANT_API_KEY and GEMINI_API_KEY)

# Chunking tuning (start ranges — tunable without code changes).
PARENT_CHUNK_TOKENS_MIN = _env_int("PARENT_CHUNK_TOKENS_MIN", 600)
PARENT_CHUNK_TOKENS_MAX = _env_int("PARENT_CHUNK_TOKENS_MAX", 1200)
CHILD_CHUNK_TOKENS_MIN = _env_int("CHILD_CHUNK_TOKENS_MIN", 150)
CHILD_CHUNK_TOKENS_MAX = _env_int("CHILD_CHUNK_TOKENS_MAX", 300)

# Retrieval tuning
RETRIEVAL_TOP_K = _env_int("RETRIEVAL_TOP_K", 4)
RETRIEVAL_ENABLE_HYBRID = _env_bool("RETRIEVAL_ENABLE_HYBRID", False)
RETRIEVAL_ENABLE_RERANK = _env_bool("RETRIEVAL_ENABLE_RERANK", False)
