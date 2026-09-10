"""Configuration validation tests."""
import importlib


def test_env_defaults():
    import app.config as config

    importlib.reload(config)
    assert config.ENVIRONMENT in {"development", "production"}
    assert config.IS_PRODUCTION in {True, False}
    assert config.LLM_PROVIDER is not None
    assert config.LLM_MODEL
    assert config.API_PORT > 0


def test_llm_provider_enum():
    from app.config import LLMProvider

    assert LLMProvider.GEMINI.value == "gemini"
    # A bogus provider string must fail enum validation loudly.
    import pytest

    with pytest.raises(ValueError):
        LLMProvider("neptune")


def test_chunking_bounds_are_tunable_and_sane():
    from app.config import (
        CHILD_CHUNK_TOKENS_MAX,
        CHILD_CHUNK_TOKENS_MIN,
        PARENT_CHUNK_TOKENS_MAX,
        PARENT_CHUNK_TOKENS_MIN,
    )

    assert 0 < CHILD_CHUNK_TOKENS_MIN <= CHILD_CHUNK_TOKENS_MAX
    assert 0 < PARENT_CHUNK_TOKENS_MIN <= PARENT_CHUNK_TOKENS_MAX
    # Parent range must envelop child range by design.
    assert PARENT_CHUNK_TOKENS_MAX >= CHILD_CHUNK_TOKENS_MAX


def test_retrieval_config_sane():
    from app.config import RETRIEVAL_TOP_K

    assert RETRIEVAL_TOP_K >= 1


def _no_dotenv(monkeypatch):
    """Keep tests hermetic: ignore backend/.env, use only process env vars."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)


def test_gemini_api_key_loads_through_config(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-placeholder")
    importlib.reload(config)
    assert config.GEMINI_API_KEY == "test-key-placeholder"


def test_gemini_api_key_falls_back_to_google(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key-placeholder")
    importlib.reload(config)
    assert config.GEMINI_API_KEY == "google-key-placeholder"


def test_gemini_api_key_may_be_empty_for_local_boot(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    importlib.reload(config)
    assert config.GEMINI_API_KEY == ""


def test_allowed_origins_returns_list(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(config)

    assert isinstance(config.ALLOWED_ORIGINS, list)


def test_allowed_origins_unset_means_deny_all(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(config)

    # No hardcoded origins: unset env defaults to deny-all.
    assert config.ALLOWED_ORIGINS == []


def test_allowed_origins_empty_env_means_deny_all(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.setenv("ALLOWED_ORIGINS", "")
    importlib.reload(config)

    assert config.ALLOWED_ORIGINS == []


def test_allowed_origins_no_hardcoded_production_origin(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(config)

    # The production frontend URL must NOT be baked into the code.
    assert "https://grounded-coffeeshop-ai.web.app" not in config.ALLOWED_ORIGINS


def test_allowed_origins_from_env(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://app.example.com, https://dev.example.com",
    )
    importlib.reload(config)

    assert config.ALLOWED_ORIGINS == [
        "https://app.example.com",
        "https://dev.example.com",
    ]


def test_allowed_origins_whitespace_filtered(monkeypatch):
    import app.config as config

    _no_dotenv(monkeypatch)
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://one.example.com, ,, https://two.example.com",
    )
    importlib.reload(config)

    assert config.ALLOWED_ORIGINS == [
        "https://one.example.com",
        "https://two.example.com",
    ]