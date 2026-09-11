"""Full chat flow tests: authenticated request -> (mocked) Gemini.

The auth dependency and the LLM are mocked; the FastAPI app, schema validation,
the endpoint, and the service run for real.
"""
import json
from types import SimpleNamespace

import app.services.chat_service as chat_service
import app.services.currency_tools as currency_tools
import app.services.menu_tools as menu_tools
from starlette.testclient import TestClient

import app.auth as auth_module
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

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

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
        def bind_tools(self, tools):
            return self

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


class _ScriptedOutput:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _ScriptedModel:
    """Returns pre-arranged outputs (text or tool calls) in order."""

    def __init__(self, outputs):
        self.outputs = outputs
        self.index = 0

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages):
        out = self.outputs[self.index]
        self.index += 1
        return out


class _FakeMenuService:
    def search(self, **kwargs):
        return [
            {
                "name": "Vanilla Cold Brew",
                "category": "coffee",
                "price": 4.5,
                "size": "16 oz",
                "caffeine": "high",
                "temperature": "cold",
                "sweetness": "medium",
                "dietary": [],
                "available": True,
                "description": "Smooth cold brew with vanilla.",
            }
        ]


class _FakeCurrencyService:
    def convert(self, amount, from_currency, to_currency):
        return SimpleNamespace(
            original_amount=amount,
            source_currency=from_currency,
            converted_amount=390.23,
            target_currency=to_currency,
            rate=86.72,
            rate_date="2026-09-11",
            provider="Frankfurter",
        )


def _search_menu_call():
    return {
        "name": "search_menu",
        "args": {"query": "cold brew"},
        "id": "call_1",
        "type": "tool_call",
    }


def _convert_currency_call():
    return {
        "name": "convert_currency",
        "args": {"amount": 4.5, "from_currency": "USD", "to_currency": "INR"},
        "id": "call_2",
        "type": "tool_call",
    }


def _patch_tool_services(monkeypatch):
    monkeypatch.setattr(menu_tools, "get_menu_service", lambda: _FakeMenuService())
    monkeypatch.setattr(currency_tools, "get_currency_service", lambda: _FakeCurrencyService())


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        data = "".join(
            line[5:] for line in block.splitlines() if line.startswith("data:")
        )
        if not data:
            continue
        try:
            events.append(json.loads(data))
        except ValueError:
            pass
    return events


def _sse_headers(monkeypatch):
    return {**_valid_headers(monkeypatch), "Accept": "text/event-stream"}


def test_sse_stream_emits_tool_events_then_done(monkeypatch):
    model = _ScriptedModel(
        [
            _ScriptedOutput(tool_calls=[_search_menu_call(), _convert_currency_call()]),
            _ScriptedOutput(content="The Vanilla Cold Brew is $4.50, about ₹390."),
        ]
    )
    monkeypatch.setattr(chat_service, "get_llm", lambda: model)
    _patch_tool_services(monkeypatch)

    client = TestClient(app)
    resp = client.post("/api/chat", headers=_sse_headers(monkeypatch), json=_payload())

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.text)
    assert [e["type"] for e in events] == ["tool", "tool", "generating", "done"]
    assert [e.get("name") for e in events if e["type"] == "tool"] == [
        "search_menu",
        "convert_currency",
    ]
    done = events[-1]
    assert done["answer"] == "The Vanilla Cold Brew is $4.50, about ₹390."
    assert done["context"]["retrieval_count"] == 1
    assert done["context"]["used_preferences"] is False


def test_sse_stream_emits_generating_between_tool_rounds(monkeypatch):
    model = _ScriptedModel(
        [
            _ScriptedOutput(tool_calls=[_search_menu_call()]),
            _ScriptedOutput(tool_calls=[_convert_currency_call()]),
            _ScriptedOutput(content="Here are the details."),
        ]
    )
    monkeypatch.setattr(chat_service, "get_llm", lambda: model)
    _patch_tool_services(monkeypatch)

    client = TestClient(app)
    resp = client.post("/api/chat", headers=_sse_headers(monkeypatch), json=_payload())

    assert resp.status_code == 200
    types = [e["type"] for e in _parse_sse(resp.text)]
    assert types == ["tool", "generating", "tool", "generating", "done"]


def test_sse_stream_sanitizes_generation_errors(monkeypatch):
    class _BoomModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            raise RuntimeError("upstream exploded")

    monkeypatch.setattr(chat_service, "get_llm", lambda: _BoomModel())

    client = TestClient(app)
    resp = client.post("/api/chat", headers=_sse_headers(monkeypatch), json=_payload())

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "error"
    assert events[-1]["message"] == "Something went wrong while preparing the response."
    assert "upstream exploded" not in resp.text


def test_sse_stream_sanitizes_configuration_error(monkeypatch):
    def _no_key():
        raise ConfigurationError(
            "Gemini API key is not configured. Set GEMINI_API_KEY (or GOOGLE_API_KEY) "
            "in backend/.env or your environment."
        )

    monkeypatch.setattr(chat_service, "get_llm", _no_key)

    client = TestClient(app)
    resp = client.post("/api/chat", headers=_sse_headers(monkeypatch), json=_payload())

    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "error"
    assert events[-1]["message"] == (
        "Grounded is still warming up. Please try again in a moment."
    )
    assert "GEMINI_API_KEY" not in resp.text


def test_sse_stream_requires_authentication():
    client = TestClient(app)
    resp = client.post(
        "/api/chat", headers={"Accept": "text/event-stream"}, json=_payload()
    )
    assert resp.status_code == 401