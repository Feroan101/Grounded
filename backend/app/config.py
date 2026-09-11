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
# Token verification uses Google's public JWKS keys and does NOT need
# credentials. Credentials are only needed for Admin SDK operations (Firestore,
# user management). The backend reads the service-account JSON location from
# the standard GOOGLE_APPLICATION_CREDENTIALS environment variable (see
# app/credentials.py); nothing here stores or embeds the JSON itself.
#
# Local development (recommended):
#   gcloud auth application-default login
#   Then GOOGLE_APPLICATION_CREDENTIALS is set automatically.
#
# Alternative (service-account JSON kept outside the repo — never committed):
#   GOOGLE_APPLICATION_CREDENTIALS=/home/you/.grounded/grounded-coffeeshop-ai.json
#
# Render (production):
#   Upload the service-account JSON as a Render Secret File
#   (grounded-coffeeshop-ai.json) and point the env var at its mount path:
#   GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/grounded-coffeeshop-ai.json

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

# Conversation-history retrieval tuning.
#
# History is read lazily through the get_conversation_history tool, never
# attached to every request. Limits keep reads bounded and the context compact:
# CONVERSATION_HISTORY_FETCH_LIMIT bounds the Firestore read, while the
# remaining constants bound what the model is shown per conversation.
CONVERSATION_HISTORY_FETCH_LIMIT = _env_int("CONVERSATION_HISTORY_FETCH_LIMIT", 8)
CONVERSATION_HISTORY_MAX_CONVERSATIONS = _env_int(
    "CONVERSATION_HISTORY_MAX_CONVERSATIONS", 3
)
CONVERSATION_HISTORY_MAX_MESSAGES = _env_int("CONVERSATION_HISTORY_MAX_MESSAGES", 6)
CONVERSATION_HISTORY_MAX_CHARS = _env_int("CONVERSATION_HISTORY_MAX_CHARS", 240)

# Order-history retrieval tuning.
#
# Like conversation history, order history is read lazily through the
# get_order_history tool — never attached to every request. The fetch limit
# bounds the Firestore read; the remaining constants bound what the model is
# shown (number of orders, line items per order, characters per item name).
ORDER_HISTORY_FETCH_LIMIT = _env_int("ORDER_HISTORY_FETCH_LIMIT", 8)
ORDER_HISTORY_MAX_ORDERS = _env_int("ORDER_HISTORY_MAX_ORDERS", 5)
ORDER_HISTORY_MAX_ITEMS = _env_int("ORDER_HISTORY_MAX_ITEMS", 6)
ORDER_HISTORY_MAX_CHARS = _env_int("ORDER_HISTORY_MAX_CHARS", 120)

# Retrieval tuning
RETRIEVAL_TOP_K = _env_int("RETRIEVAL_TOP_K", 4)
RETRIEVAL_ENABLE_HYBRID = _env_bool("RETRIEVAL_ENABLE_HYBRID", False)
RETRIEVAL_ENABLE_RERANK = _env_bool("RETRIEVAL_ENABLE_RERANK", False)
