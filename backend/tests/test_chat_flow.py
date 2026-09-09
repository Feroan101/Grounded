"""Full chat flow tests: authenticated request -> (mocked) Gemini.

The auth dependency and the LLM are mocked; the FastAPI app, schema validation,
the endpoint, and the service run for real.
"""
from starlette.testclient import TestClient

import app.auth as auth_module
import app.services.chat_service as chat_service
from app.errors import ConfigurationError
from app.main import app


class _FakeModelOutput:
    def __init__(self, text):
        self.content = text


class _FakeModel:
    def __init__(self, text="Try the cold brew."):
        self.text = text
        self.calls = 0
        self.last_messages = None

    def invoke(self, messages):
        self.calls += 1
        self.last_messages = messages
        return _FakeModelOutput(self.text)


def _valid_headers(monkeypatch, *, token="valid.token"):
    monkeypatch.setattr(
        auth_module,
        "verify_firebase_token",
        lambda t: {
            "sub": "uid-123",
            "uid": "uid-123",
            "email": "a@b.com",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def _payload():
    return {"messages": [{"role": "user", "content": "hi"}]}


def test_authenticated_chat_returns_answer(monkeypatch):
    model = _FakeModel(text="I'd recommend the cold brew.")
    monkeypatch.setattr(chat_service, "get_llm", lambda: model)

    client = TestClient(app)
    resp = client.post("/api/chat", headers=_valid_headers(monkeypatch), json=_payload())

    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "I'd recommend the cold brew."
    assert data["context"]["retrieval_used"] is False
    assert data["context"]["retrieval_count"] == 0
    assert data["context"]["used_preferences"] is False
    assert model.calls == 1


def test_chat_sends_full_conversation_context(monkeypatch):
    model = _FakeModel()
    monkeypatch.setattr(chat_service, "get_llm", lambda: model)

    client = TestClient(app)
    resp = client.post(
        "/api/chat",
        headers=_valid_headers(monkeypatch),
        json={
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "first answer"},
                {"role": "user", "content": "second"},
            ]
        },
    )

    assert resp.status_code == 200
    history = [(type(m).__name__, m.content) for m in model.last_messages]
    assert ("SystemMessage", "first") not in history  # user turn only
    assert ("HumanMessage", "first") in history
    assert ("AIMessage", "first answer") in history
    assert ("HumanMessage", "second") in history
    assert history[0][0] == "SystemMessage"


def test_chat_rejects_unauthenticated_request():
    client = TestClient(app)
    resp = client.post("/api/chat", json=_payload())
    assert resp.status_code == 401


def test_chat_rejects_invalid_token(monkeypatch):
    def _reject(token):
        raise ValueError("bad")

    monkeypatch.setattr(auth_module, "verify_firebase_token", _reject)
    client = TestClient(app)
    resp = client.post(
        "/api/chat",
        headers={"Authorization": "Bearer not.a.real.token"},
        json=_payload(),
    )
    assert resp.status_code == 401


def test_chat_rejects_empty_messages(monkeypatch):
    _valid_headers(monkeypatch)
    client = TestClient(app)
    resp = client.post("/api/chat", headers=_valid_headers(monkeypatch), json={"messages": []})
    assert resp.status_code == 422


def test_chat_rejects_empty_content(monkeypatch):
    client = TestClient(app)
    resp = client.post(
        "/api/chat",
        headers=_valid_headers(monkeypatch),
        json={"messages": [{"role": "user", "content": ""}]},
    )
    assert resp.status_code == 422


def test_chat_rejects_last_message_not_user(monkeypatch):
    client = TestClient(app)
    resp = client.post(
        "/api/chat",
        headers=_valid_headers(monkeypatch),
        json={
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hi there"},
            ]
        },
    )
    assert resp.status_code == 422


def test_gemini_failure_returns_502(monkeypatch):
    class _BoomModel:
        def invoke(self, messages):
            raise RuntimeError("upstream exploded")

    monkeypatch.setattr(chat_service, "get_llm", lambda: _BoomModel())
    client = TestClient(app)
    resp = client.post("/api/chat", headers=_valid_headers(monkeypatch), json=_payload())

    assert resp.status_code == 502
    assert "Something went wrong" in resp.json()["detail"]


def test_missing_api_key_returns_503(monkeypatch):
    def _no_key():
        raise ConfigurationError(
            "Gemini API key is not configured. Set GEMINI_API_KEY (or GOOGLE_API_KEY) "
            "in backend/.env or your environment."
        )

    monkeypatch.setattr(chat_service, "get_llm", _no_key)
    client = TestClient(app)
    resp = client.post("/api/chat", headers=_valid_headers(monkeypatch), json=_payload())

    assert resp.status_code == 503
    assert "API key" in resp.json()["detail"]
    assert "GEMINI_API_KEY" in resp.json()["detail"]