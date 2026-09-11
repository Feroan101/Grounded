"""Conversation-history retrieval: repository, service, agent tool, and chat.

Authorization is derived from the verified Firebase token; UIDs are never
accepted from the client and the tool exposes no user/path arguments. Firestore,
the preferences service, and the LLM are mocked — no real Firestore calls or
network traffic.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from google.cloud import firestore
from langchain_core.messages import AIMessage

import app.services.chat_service as chat_service
from app.api.schemas import ChatRequest
from app.errors import ProviderError
from app.repositories import conversations as conversations_repo
from app.services import conversation_history_service
from app.services import conversation_history_tools
from app.services.conversation_history_service import ConversationRecord
from app.services.conversation_history_tools import build_conversation_history_tools


# ── Repository (mocked Firestore) ─────────────────────────────────

class _FakeDoc:
    def __init__(self, data, doc_id):
        self._data = data
        self.id = doc_id

    def to_dict(self):
        return self._data


class _FakeQuery:
    def __init__(self, docs):
        self.docs = docs
        self.order_field = None
        self.order_direction = None
        self.limit_value = None

    def order_by(self, field, direction=None):
        self.order_field = field
        self.order_direction = direction
        return self

    def limit(self, n):
        self.limit_value = n
        return self

    def stream(self):
        return iter(self.docs)


class _FakeConversationsCol:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None

    def order_by(self, field, direction=None):
        query = _FakeQuery(self.docs)
        query.order_by(field, direction)
        self.last_query = query
        return query

    def document(self, _doc_id):
        raise AssertionError("history read must never open a conversation by id")

    def add(self, *_args, **_kwargs):
        raise AssertionError("history read must never write")


class _FakeSub:
    def __init__(self, docs, holder):
        self.docs = docs
        self.holder = holder

    def collection(self, _name):
        col = _FakeConversationsCol(self.docs)
        self.holder.last_col = col
        return col


class _FakeUserDoc:
    def __init__(self, docs_by_uid, holder):
        self.docs_by_uid = docs_by_uid
        self.holder = holder

    def document(self, uid):
        if uid not in self.docs_by_uid:
            raise AssertionError(f"read used unexpected uid path: {uid}")
        return _FakeSub(self.docs_by_uid[uid], self.holder)

    def collection(self, _name):
        raise AssertionError("unexpected nested collection access")


class _FakeFirestore:
    def __init__(self, docs_by_uid):
        self.docs_by_uid = docs_by_uid
        self.last_col = None

    def collection(self, _name):
        return _FakeUserDoc(self.docs_by_uid, self)


def _fake_firestore(monkeypatch, docs_by_uid):
    fake = _FakeFirestore(docs_by_uid)
    monkeypatch.setattr(conversations_repo, "get_firestore", lambda: fake)
    return fake


def _conv_doc(title, messages, created_at, doc_id="c1"):
    return _FakeDoc(
        {"title": title, "messages": messages, "createdAt": created_at}, doc_id
    )


def test_repo_reads_newest_conversation_docs_with_limits(monkeypatch):
    now = datetime(2026, 9, 10, 12, 0)
    _fake_firestore(
        monkeypatch,
        {
            "uid-1": [
                _conv_doc("First", [{"role": "user", "content": "hi"}], now, "c1"),
                _conv_doc("Second", [], now, "c2"),
            ]
        },
    )

    result = conversations_repo.get_recent_conversations("uid-1", limit=2)

    assert [doc["id"] for doc in result] == ["c1", "c2"]
    assert result[0]["title"] == "First"
    assert "id" in result[0]


def test_repo_is_scoped_to_the_verified_uid(monkeypatch):
    """Reading user A must touch exactly user A's collection path."""
    _fake_firestore(
        monkeypatch,
        {"uid-1": [_conv_doc("A", [{"role": "user", "content": "a"}], datetime(2026, 1, 1))]},
    )
    conversations_repo.get_recent_conversations("uid-1")
    with pytest.raises(AssertionError):
        conversations_repo.get_recent_conversations("uid-2")


def test_repo_orders_by_created_at_desc_and_applies_bounded_limit(monkeypatch):
    _fake_firestore(
        monkeypatch, {"uid-1": [_conv_doc("A", [], datetime(2026, 1, 1), "c1")]}
    )

    conversations_repo.get_recent_conversations("uid-1", limit=2)

    fake = conversations_repo.get_firestore()
    assert fake.last_col.last_query.order_field == "createdAt"
    assert fake.last_col.last_query.order_direction == firestore.Query.DESCENDING
    assert fake.last_col.last_query.limit_value == 2


def test_repo_empty_history_returns_empty_list(monkeypatch):
    _fake_firestore(monkeypatch, {"uid-1": []})

    assert conversations_repo.get_recent_conversations("uid-1") == []


# ── Service layer ─────────────────────────────────────────────────

def _patch_repo(monkeypatch, docs, repo_uid=None):
    seen = {}

    def fake_get(uid, **kwargs):
        seen["uid"] = uid
        return list(docs)

    monkeypatch.setattr(
        conversation_history_service.conversations_repo,
        "get_recent_conversations",
        fake_get,
    )
    return seen


def _msg(role, content):
    return {"role": role, "content": content}


def _doc(title, messages, created_at=None, doc_id="c1"):
    return {
        "id": doc_id,
        "title": title,
        "messages": messages,
        "createdAt": created_at,
    }


def test_service_passes_verified_uid_through(monkeypatch):
    seen = _patch_repo(monkeypatch, [_doc("A", [_msg("user", "hi")])])

    conversation_history_service.get_conversation_history_service().get_history("uid-9")

    assert seen["uid"] == "uid-9"


def test_service_returns_bounded_records_newest_first(monkeypatch):
    docs = [_doc(f"c{i}", [_msg("user", f"msg {i}")], doc_id=f"c{i}") for i in range(5)]
    _patch_repo(monkeypatch, docs)

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1", max_conversations=3
    )

    assert [r.messages[0]["content"] for r in records] == ["msg 0", "msg 1", "msg 2"]
    assert len(records) == 3


def test_service_keeps_only_recent_messages_per_conversation(monkeypatch):
    messages = [_msg("user", f"old {i}") for i in range(10)]
    _patch_repo(monkeypatch, [_doc("A", messages)])

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1", max_messages=4
    )

    assert [m["content"] for m in records[0].messages] == [
        "old 6",
        "old 7",
        "old 8",
        "old 9",
    ]


def test_service_truncates_long_message_content(monkeypatch):
    long_text = "x" * 500
    _patch_repo(monkeypatch, [_doc("A", [_msg("user", long_text)])])

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1", max_chars=50
    )

    body = records[0].messages[0]["content"]
    assert len(body) <= 53  # 50 chars + ellipsis
    assert body.endswith("...")


def test_service_excludes_current_conversation(monkeypatch):
    _patch_repo(
        monkeypatch,
        [
            _doc("current", [_msg("user", "right now")], doc_id="current"),
            _doc("past", [_msg("user", "back then")], doc_id="past"),
        ],
    )

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1", exclude_id="current"
    )

    assert [r.title for r in records] == ["past"]


def test_service_drops_malformed_records_and_messages(monkeypatch):
    docs = [
        _doc("A", [{"role": "system", "content": "hidden"}]),  # user/assistant only
        {"id": "B", "title": 99, "messages": "not-a-list"},
        _doc("C", [_msg("user", "   "), "garbage", {"role": "assistant", "content": "ok"}]),
        {"id": "D", "messages": [{"role": "user", "content": "x"}]},  # no title
    ]
    _patch_repo(monkeypatch, docs)

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1"
    )

    assert [r.title for r in records] == ["C", None]
    assert records[0].messages == [_msg("assistant", "ok")]
    assert records[1].messages == [_msg("user", "x")]


def test_service_deduplicates_consecutive_duplicate_messages(monkeypatch):
    _patch_repo(
        monkeypatch,
        [
            _doc(
                "A",
                [
                    _msg("user", "same"),
                    _msg("user", "same"),
                    _msg("assistant", "same answer"),
                    _msg("user", "different"),
                ],
            )
        ],
    )

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1"
    )

    assert [m["content"] for m in records[0].messages] == [
        "same",
        "same answer",
        "different",
    ]


def test_service_formats_created_at_to_date(monkeypatch):
    _patch_repo(
        monkeypatch,
        [_doc("A", [_msg("user", "hi")], created_at=datetime(2026, 9, 10, 14, 30))],
    )

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1"
    )

    assert records[0].date == "2026-09-10"


def test_service_gracefully_missing_timestamp(monkeypatch):
    _patch_repo(monkeypatch, [_doc("A", [_msg("user", "hi")], created_at="nope")])

    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1"
    )

    assert records[0].date is None


def test_service_empty_history_returns_empty(monkeypatch):
    _patch_repo(monkeypatch, [])
    records = conversation_history_service.get_conversation_history_service().get_history(
        "uid-1"
    )
    assert records == []


def test_service_firestore_failure_is_provider_error(monkeypatch):
    def boom(uid, **kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(
        conversation_history_service.conversations_repo,
        "get_recent_conversations",
        boom,
    )

    with pytest.raises(ProviderError):
        conversation_history_service.get_conversation_history_service().get_history("u1")


# ── Agent tool ────────────────────────────────────────────────────

def _enabled_prefs(**overrides):
    prefs = {"conversationHistoryEnabled": True}
    prefs.update(overrides)
    return prefs


class _FakePreferencesService:
    def __init__(self, prefs):
        self.prefs = prefs
        self.calls = []

    def get_preferences(self, uid):
        self.calls.append(uid)
        return self.prefs


class _FakeHistoryService:
    def __init__(self, records=None, exc=None):
        self.records = records if records is not None else []
        self.exc = exc
        self.calls = []

    def get_history(self, uid, *, exclude_id=None):
        self.calls.append((uid, exclude_id))
        if self.exc:
            raise self.exc
        return list(self.records)


def _patch_tool_deps(monkeypatch, prefs_fake, history_fake):
    monkeypatch.setattr(
        conversation_history_tools, "get_preferences_service", lambda: prefs_fake
    )
    monkeypatch.setattr(
        conversation_history_tools,
        "get_conversation_history_service",
        lambda: history_fake,
    )


def _history_tool(uid="uid-1", exclude=None):
    return [
        t
        for t in build_conversation_history_tools(uid, exclude_conversation_id=exclude)
        if t.name == "get_conversation_history"
    ][0]


def test_build_registers_only_history_tool():
    tools = build_conversation_history_tools("uid-1")
    assert [t.name for t in tools] == ["get_conversation_history"]


def test_tool_has_no_user_or_path_arguments():
    tool = _history_tool()
    assert tool.args == {}  # the model can never supply a UID or document path


def test_tool_reads_history_for_closed_over_uid(monkeypatch):
    _patch_tool_deps(
        monkeypatch,
        _FakePreferencesService(_enabled_prefs()),
        _FakeHistoryService(),
    )

    output = _history_tool(uid="uid-42").invoke({})

    history = conversation_history_tools.get_conversation_history_service()
    assert history.calls == [("uid-42", None)]


def test_tool_never_accepts_a_uid_from_the_model(monkeypatch):
    history_fake = _FakeHistoryService()
    _patch_tool_deps(
        monkeypatch, _FakePreferencesService(_enabled_prefs()), history_fake
    )

    tool = _history_tool()
    assert tool.args == {}  # no uid/path parameter exists for the model to use

    tool.invoke({})  # empty invocation binds to the closed-over uid
    tool.invoke({"uid": "uid-other"})  # stray args are ignored by the framework
    assert history_fake.calls == [("uid-1", None), ("uid-1", None)]


def test_tool_respects_disabled_history_preference(monkeypatch):
    prefs_fake = _FakePreferencesService(_enabled_prefs(conversationHistoryEnabled=False))
    history_fake = _FakeHistoryService()
    _patch_tool_deps(monkeypatch, prefs_fake, history_fake)

    output = _history_tool().invoke({})

    assert "turned off" in output
    assert history_fake.calls == []


def test_tool_fails_safe_when_preferences_unavailable(monkeypatch):
    prefs_fake = _FakePreferencesService(_enabled_prefs())
    prefs_fake.get_preferences = lambda uid: (_ for _ in ()).throw(
        ProviderError("prefs down")
    )
    history_fake = _FakeHistoryService()
    _patch_tool_deps(monkeypatch, prefs_fake, history_fake)

    output = _history_tool().invoke({})

    assert "unavailable" in output
    assert history_fake.calls == []


def test_tool_returns_empty_message_when_no_history(monkeypatch):
    _patch_tool_deps(
        monkeypatch,
        _FakePreferencesService(_enabled_prefs()),
        _FakeHistoryService(),
    )

    output = _history_tool().invoke({})

    assert "no recent past conversations" in output


def test_tool_renders_bounded_history(monkeypatch):
    prefs_fake = _FakePreferencesService(_enabled_prefs())
    history_fake = _FakeHistoryService(
        records=[
            ConversationRecord(
                title="Oat milk phase",
                date="2026-09-10",
                messages=[
                    _msg("user", "I want something iced"),
                    _msg("assistant", "Try the cold brew."),
                ],
            ),
            ConversationRecord(title=None, date=None, messages=[_msg("user", "hi")]),
        ]
    )
    _patch_tool_deps(monkeypatch, prefs_fake, history_fake)

    output = _history_tool().invoke({})

    assert '"Oat milk phase" (from 2026-09-10)' in output
    assert "User: I want something iced" in output
    assert "Assistant: Try the cold brew." in output
    assert "uid" not in output.lower()


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


def test_chat_binds_history_tool_for_authenticated_user(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="hello")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What should I get?"), user={"uid": "uid-123"}
    )

    assert result.ok
    names = [t.name for t in llm.bound_tools]
    assert "get_conversation_history" in names


def test_chat_marks_history_used_when_retrieved(monkeypatch):
    _patch_tool_deps(
        monkeypatch,
        _FakePreferencesService(_enabled_prefs()),
        _FakeHistoryService(),
    )
    llm = _FakeLLM(
        _BoundModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_conversation_history",
                            "args": {},
                            "id": "hist_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="You ordered an iced mocha last time."),
            ]
        )
    )
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What did I order last time?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_conversation_history is True


def test_chat_does_not_mark_history_for_plain_question(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="Try the cappuccino.")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What's on the menu?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_conversation_history is False


def test_chat_respects_disabled_history_end_to_end(monkeypatch):
    prefs_fake = _FakePreferencesService(_enabled_prefs(conversationHistoryEnabled=False))
    history_fake = _FakeHistoryService()
    _patch_tool_deps(monkeypatch, prefs_fake, history_fake)
    llm = _FakeLLM(
        _BoundModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_conversation_history",
                            "args": {},
                            "id": "hist_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="I don't have memory of that."),
            ]
        )
    )
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("Did I say my dog's name before?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_conversation_history is True
    assert history_fake.calls == []  # retrieval never happened


def test_system_prompt_includes_history_guidance():
    prompt = chat_service.SYSTEM_PROMPT
    assert "get_conversation_history" in prompt
    assert "ONLY when" in prompt