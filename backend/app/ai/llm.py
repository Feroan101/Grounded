"""AI abstraction layer.

The API layer never talks to a provider directly. It goes through
``ChatModel``, an interface that hides which provider/model is in use.
Provider-specific integration lives under ``app/ai/providers``.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.config import LLM_MODEL, LLM_PROVIDER, LLM_PROVIDER_NAME, IS_PRODUCTION
from app.errors import ConfigurationError, ProviderError
from app.ai.providers.gemini import create_gemini_chat_model


@runtime_checkable
class ChatModel(Protocol):
    """Minimal chat model contract used by the agent.

    This keeps the agent decoupled from any specific LangChain/GenAI class.
    It models the shape of a LangChain chat model, so a LangChain
    ``BaseChatModel`` satisfies this protocol directly.
    """

    def invoke(self, messages):  # pragma: no cover - Protocol
        ...


class LLMError(ProviderError):
    """Raised when the LLM provider cannot be reached or configured."""


_llm: ChatModel | None = None


def llm_provider_name() -> str:
    return LLM_PROVIDER_NAME


def is_llm_configured() -> bool:
    """Whether an LLM provider is configured.

    In production we require an LLM. During local development (no API key)
    the app still boots so the health / contract surface works.
    """
    return LLM_PROVIDER is not None


def _configured_or_error() -> None:
    if LLM_PROVIDER is None:
        raise ConfigurationError(
            "No LLM provider is configured. Set LLM_PROVIDER."
        )


def get_llm() -> ChatModel:
    """Return a singleton chat model for the configured provider.

    Builds the model lazily so provider credential issues surface at first
    use, not at import time (which would break the health endpoint).
    """
    global _llm
    if _llm is not None:
        return _llm

    _configured_or_error()

    if LLM_PROVIDER.name == "GEMINI":
        try:
            _llm = create_gemini_chat_model(
                model_name=LLM_MODEL,
                temperature=0.4,
            )
        except ConfigurationError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            if IS_PRODUCTION:
                raise LLMError() from exc
            # Development: let the underlying import/credential failure raise
            # so it is visible locally.
            raise
    else:  # pragma: no cover - future provider
        raise ConfigurationError(
            f"Unsupported LLM provider: {LLM_PROVIDER.value!r}"
        )

    return _llm


def reset_llm() -> None:
    """Reset the cached model (mainly for tests)."""
    global _llm
    _llm = None