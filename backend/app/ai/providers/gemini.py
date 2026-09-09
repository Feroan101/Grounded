"""Gemini provider integration.

Uses LangChain's ``langchain-google-genai`` package (``ChatGoogleGenerativeAI``)
to connect to Google's Gemini models. The repository already specifies Gemini
as the model provider; this module is the only place that imports the Gemini
integration.
"""
from __future__ import annotations

from app.config import GEMINI_API_KEY, IS_PRODUCTION
from app.errors import ConfigurationError


class GeminiChatModel:
    """Thin wrapper around LangChain's Gemini chat model.

    We keep a tiny facade so the rest of the application (agent, services)
    depends on ``app.ai.llm.ChatModel`` rather than on LangChain classes
    directly. In future phases this wrapper can expose typed invocation,
    streaming, and token accounting without leaking LangChain types outward.
    """

    def __init__(self, model_name: str, temperature: float = 0.4, api_key: str = ""):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ConfigurationError(
                "langchain-google-genai is not installed. "
                "Run: pip install -r requirements.txt"
            )

        if not api_key:
            raise ConfigurationError(
                "Gemini API key is not configured. Set GEMINI_API_KEY "
                "(or GOOGLE_API_KEY) in backend/.env or your environment."
            )

        try:
            self._model = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=api_key,
            )
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                f"Failed to initialize Gemini model: {exc}"
            ) from exc

    def invoke(self, messages):
        return self._model.invoke(messages)


def create_gemini_chat_model(
    model_name: str, temperature: float = 0.4
) -> GeminiChatModel:
    """Instantiate the Gemini-backed chat model.

    The API key comes from ``app.config.GEMINI_API_KEY`` (read from the
    ``GEMINI_API_KEY`` environment variable, with ``GOOGLE_API_KEY`` as a
    fallback). The key is never logged or accepted from the caller.
    """
    if not model_name:
        raise ConfigurationError("LLM_MODEL is not configured.")

    try:
        return GeminiChatModel(
            model_name=model_name,
            temperature=temperature,
            api_key=GEMINI_API_KEY,
        )
    except ConfigurationError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        if IS_PRODUCTION:
            raise ConfigurationError(
                "Failed to initialize the configured model."
            ) from exc
        raise