"""Customer preferences: API, service, and agent tools.

Authorization is derived from the verified Firebase token; UIDs are never
accepted from the client. Firestore, the LLM, and the preferences service are
mocked — no real Firestore calls or network traffic.
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from starlette.testclient import TestClient

import app.auth as auth_module
import app.services.chat_service as chat_service
import app.services.preferences_service as preferences_service
from app.api.schemas import ChatRequest
from app.errors import ProviderError, ValidationError
from app.main import app
from app.services import preference_tools
from app.services.preference_tools import build_preference_tools


# ── Helpers ───────────────────────────────────────────────────────

def _valid_headers(monkeypatch, *, token="valid.token"):
    monkeypatch.setattr(
        auth_module,
        "verify_firebase_token",
        lambda t: {"sub": "uid-123", "uid": "uid-123", "email": "a@b.com"},
    )
    return {"Authorization": f"Bearer {token}"}


def _full_prefs(**overrides) -> dict:
    prefs = {
        "coffee": {
            "favoriteDrink": "",
            "temperature": "either",
            "milkPreference": "",
            "sweetness": "",
            "strength": "",
            "caffeinePreference": "",
            "roastPreference": "",
            "brewMethod": "",
            "dietaryPreference": [],
            "allergiesOrIntolerances": "",
        },
        "aiContext": {
            "customContext": "",
            "responseStyle": "balanced",
            "tone": "friendly",
            "recommendationStyle": "best",
            "usePreferencesInConversations": True,
        },
        "conversationHistoryEnabled": True,
        "createdAt": None,
        "updatedAt": None,
    }
    prefs.update(overrides)
    return prefs


class _FakePreferencesService:
    """PreferencesService stand-in; never touches Firestore."""

    def __init__(self, stored=None, exc: Exception | None = None):
        self.stored = stored if stored is not None else _full_prefs()
        self.exc = exc
        self.calls: list[tuple] = []

    def get_preferences(self, uid: str) -> dict:
        self.calls.append(("get", uid))
        if self.exc:
            raise self.exc
        return self.stored

    def update_preferences(self, uid: str, updates: dict) -> dict:
        self.calls.append(("update", uid, updates))
        if self.exc:
            raise self.exc
        return self.stored


def _patch_service(monkeypatch, fake_service):
    monkeypatch.setattr(
        preferences_service, "get_preferences_service", lambda: fake_service
    )
    # The agent tools import the factory by name at module import time, so they
    # need patching on their own module too.
    monkeypatch.setattr(
        preference_tools, "get_preferences_service", lambda: fake_service
    )
    return fake_service


# ── API: authentication ───────────────────────────────────────────

def test_get_preferences_requires_auth():
    resp = TestClient(app).get("/api/preferences")
    assert resp.status_code == 401


def test_get_preferences_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(auth_module, "verify_firebase_token", lambda t: (_ for _ in ()).throw(ValueError("bad")))
    resp = TestClient(app).get("/api/preferences", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_patch_preferences_requires_auth():
    resp = TestClient(app).patch("/api/preferences", json={"coffee": {"sweetness": "less"}})
    assert resp.status_code == 401


# ── API: GET ──────────────────────────────────────────────────────

def test_get_preferences_returns_defaults(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService(stored=_full_prefs()))
    resp = TestClient(app).get("/api/preferences", headers=_valid_headers(monkeypatch))

    assert resp.status_code == 200
    data = resp.json()
    assert fake.calls == [("get", "uid-123")]  # UID from the token, never the client
    assert data["conversationHistoryEnabled"] is True
    assert data["coffee"]["temperature"] == "either"
    assert data["coffee"]["dietaryPreference"] == []
    assert data["aiContext"]["usePreferencesInConversations"] is True


def test_get_preferences_returns_stored_values(monkeypatch):
    stored = _full_prefs(
        coffee={
            "favoriteDrink": "Iced Mocha",
            "temperature": "iced",
            "dietaryPreference": ["Vegan", "Sugar-free"],
        }
    )
    _patch_service(monkeypatch, _FakePreferencesService(stored=stored))
    resp = TestClient(app).get("/api/preferences", headers=_valid_headers(monkeypatch))

    assert resp.status_code == 200
    data = resp.json()
    assert data["coffee"]["favoriteDrink"] == "Iced Mocha"
    assert data["coffee"]["temperature"] == "iced"
    assert data["coffee"]["dietaryPreference"] == ["Vegan", "Sugar-free"]


def test_preferences_scoped_to_authenticated_user(monkeypatch):
    """Two users get their OWN preferences — the UID is never client-supplied."""
    seen: list[str] = []

    class _Scoped:
        def get_preferences(self, uid):
            seen.append(uid)
            return _full_prefs()

        def update_preferences(self, uid, updates):
            seen.append(uid)
            return _full_prefs()

    _patch_service(monkeypatch, _Scoped())
    _valid_headers(monkeypatch)

    client = TestClient(app)
    client.get("/api/preferences", headers=_valid_headers(monkeypatch))
    client.patch(
        "/api/preferences",
        headers=_valid_headers(monkeypatch),
        json={"coffee": {"temperature": "hot"}},
    )
    assert seen == ["uid-123", "uid-123"]


# ── API: PATCH ────────────────────────────────────────────────────

def test_patch_updates_allowed_field(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService())
    resp = TestClient(app).patch(
        "/api/preferences",
        headers=_valid_headers(monkeypatch),
        json={"coffee": {"temperature": "hot"}, "conversationHistoryEnabled": False},
    )

    assert resp.status_code == 200
    assert fake.calls[0][0] == "update"
    assert fake.calls[0][1] == "uid-123"
    assert fake.calls[0][2] == {
        "coffee": {"temperature": "hot"},
        "conversationHistoryEnabled": False,
    }


def test_patch_passes_only_provided_fields(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService())
    TestClient(app).patch(
        "/api/preferences",
        headers=_valid_headers(monkeypatch),
        json={"coffee": {"sweetness": "less"}},
    )

    assert fake.calls[0][0] == "update"
    assert fake.calls[0][1] == "uid-123"
    assert fake.calls[0][2] == {"coffee": {"sweetness": "less"}}


def test_patch_rejects_unknown_field(monkeypatch):
    _patch_service(monkeypatch, _FakePreferencesService())
    resp = TestClient(app).patch(
        "/api/preferences",
        headers=_valid_headers(monkeypatch),
        json={"coffee": {"password": "hunter2"}},
    )
    assert resp.status_code == 422


def test_patch_rejects_unknown_top_level_key(monkeypatch):
    _patch_service(monkeypatch, _FakePreferencesService())
    resp = TestClient(app).patch(
        "/api/preferences",
        headers=_valid_headers(monkeypatch),
        json={"uid": "someone-else", "coffee": {"temperature": "hot"}},
    )
    assert resp.status_code == 422


def test_patch_rejects_invalid_enum_value(monkeypatch):
    _patch_service(monkeypatch, _FakePreferencesService())
    resp = TestClient(app).patch(
        "/api/preferences",
        headers=_valid_headers(monkeypatch),
        json={"coffee": {"temperature": "steaming"}},
    )
    assert resp.status_code == 422


def test_patch_rejects_empty_body(monkeypatch):
    _patch_service(monkeypatch, _FakePreferencesService())
    resp = TestClient(app).patch(
        "/api/preferences", headers=_valid_headers(monkeypatch), json={}
    )
    assert resp.status_code == 422


def test_preferences_firestore_failure_is_502(monkeypatch):
    _patch_service(
        monkeypatch,
        _FakePreferencesService(exc=ProviderError("Preferences are temporarily unavailable.")),
    )
    resp = TestClient(app).get("/api/preferences", headers=_valid_headers(monkeypatch))

    assert resp.status_code == 502
    assert "unavailable" in resp.json()["detail"]


# ── Service layer ─────────────────────────────────────────────────

def _patch_repo(monkeypatch, *, stored=None, update_exc=None):
    calls = {"get": [], "update": []}

    def fake_get(uid):
        calls["get"].append(uid)
        if stored is not None:
            return dict(stored)
        return None

    def fake_update(uid, updates):
        calls["update"].append((uid, updates))
        if update_exc:
            raise update_exc

    monkeypatch.setattr(preferences_service.preferences_repo, "get_preferences", fake_get)
    monkeypatch.setattr(preferences_service.preferences_repo, "update_preferences", fake_update)
    return calls


def test_service_returns_safe_defaults_when_missing(monkeypatch):
    calls = _patch_repo(monkeypatch, stored=None)
    result = preferences_service.get_preferences_service().get_preferences("u1")

    assert calls["get"] == ["u1"]
    assert result["coffee"]["temperature"] == "either"
    assert result["coffee"]["dietaryPreference"] == []
    assert result["aiContext"]["responseStyle"] == "balanced"
    assert result["conversationHistoryEnabled"] is True
    assert result["createdAt"] is None


def test_service_partial_update_preserves_unrelated_fields(monkeypatch):
    calls = _patch_repo(
        monkeypatch,
        stored={"coffee": {"favoriteDrink": "Latte"}, "aiContext": {"tone": "playful"}},
    )
    result = preferences_service.get_preferences_service().update_preferences(
        "u1", {"coffee": {"sweetness": "less"}}
    )

    assert result["coffee"]["favoriteDrink"] == "Latte"
    assert result["coffee"]["sweetness"] == "less"
    assert result["aiContext"]["tone"] == "playful"
    assert result["conversationHistoryEnabled"] is True
    assert result["updatedAt"] is not None
    assert calls["update"][0][0] == "u1"
    payload = calls["update"][0][1]
    assert payload["coffee"]["favoriteDrink"] == "Latte"
    assert payload["coffee"]["sweetness"] == "less"
    assert payload["coffee"]["temperature"] == "either"  # safe default filled in
    assert payload["updatedAt"] is not None


def test_service_update_rejects_unknown_nested_field(monkeypatch):
    _patch_repo(monkeypatch, stored=None)
    with pytest.raises(ValidationError):
        preferences_service.get_preferences_service().update_preferences(
            "u1", {"coffee": {"milk": "oat"}}
        )


def test_service_update_rejects_unknown_top_level(monkeypatch):
    _patch_repo(monkeypatch, stored=None)
    with pytest.raises(ValidationError):
        preferences_service.get_preferences_service().update_preferences(
            "u1", {"memories": ["secret notes"]}
        )


def test_service_update_firestore_failure_is_provider_error(monkeypatch):
    _patch_repo(monkeypatch, stored=None, update_exc=RuntimeError("boom"))
    with pytest.raises(ProviderError):
        preferences_service.get_preferences_service().update_preferences(
            "u1", {"conversationHistoryEnabled": False}
        )


# ── Agent field parsing ───────────────────────────────────────────

def test_parse_agent_preference_enum_field():
    assert preferences_service.parse_agent_preference("temperature", " hot ") == {
        "coffee": {"temperature": "hot"}
    }


def test_parse_agent_preference_rejects_bad_enum_value():
    with pytest.raises(ValidationError):
        preferences_service.parse_agent_preference("temperature", "steaming")


def test_parse_agent_preference_dietary_normalizes():
    assert preferences_service.parse_agent_preference(
        "dietaryPreference", "Vegan, sugar-free"
    ) == {"coffee": {"dietaryPreference": ["Vegan", "Sugar-free"]}}


def test_parse_agent_preference_boolean():
    assert preferences_service.parse_agent_preference(
        "usePreferencesInConversations", "false"
    ) == {"aiContext": {"usePreferencesInConversations": False}}


def test_parse_agent_preference_rejects_non_customer_fields():
    for field in ("conversationHistoryEnabled", "uid", "orders", "title"):
        with pytest.raises(ValidationError):
            preferences_service.parse_agent_preference(field, "x")


# ── Agent tools ───────────────────────────────────────────────────

def test_build_preference_tools_names():
    tools = build_preference_tools("uid-9")
    assert [t.name for t in tools] == ["get_customer_preferences", "save_preference"]


def test_get_customer_preferences_summarizes_stored(monkeypatch):
    stored = _full_prefs(
        coffee={
            "favoriteDrink": "Latte",
            "temperature": "iced",
            "milkPreference": "oat",
            "sweetness": "less",
        },
        aiContext={
            "customContext": "Prefers strong coffee",
            "responseStyle": "short",
            "usePreferencesInConversations": True,
        },
    )
    _patch_service(monkeypatch, _FakePreferencesService(stored=stored))

    output = [t for t in build_preference_tools("uid-9") if t.name == "get_customer_preferences"][0].invoke({})

    assert "Favorite drink: Latte" in output
    assert "Milk preference: oat" in output
    assert "Prefers strong coffee" in output


def test_get_customer_preferences_respects_opt_out(monkeypatch):
    stored = _full_prefs(
        coffee={"favoriteDrink": "Mocha"},
        aiContext={"usePreferencesInConversations": False},
    )
    _patch_service(monkeypatch, _FakePreferencesService(stored=stored))

    output = [t for t in build_preference_tools("uid-9") if t.name == "get_customer_preferences"][0].invoke({})

    assert "switched off preference personalization" in output
    assert "Favorite drink" not in output


def test_get_customer_preferences_no_prefs_yet(monkeypatch):
    _patch_service(monkeypatch, _FakePreferencesService(stored=_full_prefs()))
    output = [t for t in build_preference_tools("uid-9") if t.name == "get_customer_preferences"][0].invoke({})
    assert "no stored preferences yet" in output


def test_save_preference_writes_scoped_field(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService())
    save = [t for t in build_preference_tools("uid-9") if t.name == "save_preference"][0]

    output = save.invoke({"field": "temperature", "value": "hot"})

    assert "Saved preference: Preferred temperature = hot" in output
    assert fake.calls == [("update", "uid-9", {"coffee": {"temperature": "hot"}})]


def test_save_preference_rejects_unknown_field(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService())
    save = [t for t in build_preference_tools("uid-9") if t.name == "save_preference"][0]

    with pytest.raises(Exception):
        save.invoke({"field": "notAField", "value": "x"})
    assert fake.calls == []


def test_save_preference_rejects_bad_value_with_message(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService())
    save = [t for t in build_preference_tools("uid-9") if t.name == "save_preference"][0]

    output = save.invoke({"field": "temperature", "value": "steaming"})

    assert "Could not save that preference" in output
    assert fake.calls == []


def test_save_preference_never_writes_conversation_control(monkeypatch):
    fake = _patch_service(monkeypatch, _FakePreferencesService())
    save = [t for t in build_preference_tools("uid-9") if t.name == "save_preference"][0]

    with pytest.raises(Exception):
        save.invoke({"field": "conversationHistoryEnabled", "value": "true"})
    assert fake.calls == []


# ── Chat service integration ──────────────────────────────────────

class _BoundModel:
    def __init__(self, script):
        self.script = list(script)
        self.supplied_messages = []

    def invoke(self, messages):
        self.supplied_messages.append(messages)
        return self.script.pop(0)


class _FakeLLM:
    def __init__(self, bound):
        self.bound = bound
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self.bound


def _request(user_message: str) -> ChatRequest:
    return ChatRequest.model_validate(
        {"messages": [{"role": "user", "content": user_message}]}
    )


def test_chat_service_binds_preference_tools_for_authenticated_user(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="hello")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What should I get?"), user={"uid": "uid-123"}
    )

    assert result.ok
    names = sorted(t.name for t in llm.bound_tools)
    assert names == [
        "convert_currency",
        "get_conversation_history",
        "get_customer_preferences",
        "get_order_history",
        "save_preference",
        "search_menu",
    ]


def test_chat_service_without_user_skips_preference_tools(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="hello")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    chat_service.ChatService().process(_request("hi"))

    assert sorted(t.name for t in llm.bound_tools) == ["convert_currency", "search_menu"]


def test_chat_marks_preferences_used_when_retrieved(monkeypatch):
    _patch_service(monkeypatch, _FakePreferencesService(stored=_full_prefs()))
    llm = _FakeLLM(
        _BoundModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_customer_preferences",
                            "args": {},
                            "id": "pref_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="Your usual is a Latte."),
            ]
        )
    )
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What should I get?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_preferences is True


def test_chat_preferences_not_used_when_only_menu_tool(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="Try the cappuccino.")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What's on the menu?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_preferences is False


def test_system_prompt_includes_preference_guidance():
    prompt = chat_service.SYSTEM_PROMPT
    assert "get_customer_preferences" in prompt
    assert "save_preference" in prompt
    assert "stable" in prompt