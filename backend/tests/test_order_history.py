"""Order-history retrieval: repository, service, agent tool, and chat.

Authorization is derived from the verified Firebase token; UIDs are never
accepted from the client and the tool exposes no user/path arguments. Firestore,
the order service, and the LLM are mocked — no real Firestore calls or network
traffic.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from google.cloud import firestore
from langchain_core.messages import AIMessage

import app.services.chat_service as chat_service
from app.api.schemas import ChatRequest
from app.errors import ProviderError
from app.repositories import orders as orders_repo
from app.services import order_history_service
from app.services import order_history_tools
from app.services.order_history_service import OrderRecord
from app.services.order_history_tools import build_order_history_tools


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


class _FakeOrdersCol:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None

    def order_by(self, field, direction=None):
        query = _FakeQuery(self.docs)
        query.order_by(field, direction)
        self.last_query = query
        return query

    def document(self, _doc_id):
        raise AssertionError("history read must never open an order by id")

    def add(self, *_args, **_kwargs):
        raise AssertionError("history read must never write")


class _FakeSub:
    def __init__(self, docs, holder):
        self.docs = docs
        self.holder = holder

    def collection(self, _name):
        col = _FakeOrdersCol(self.docs)
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
    monkeypatch.setattr(orders_repo, "get_firestore", lambda: fake)
    return fake


def _order_doc(items, total, created_at, doc_id="o1"):
    return _FakeDoc(
        {"items": items, "total": total, "createdAt": created_at}, doc_id
    )


def test_repo_reads_user_scoped_order_docs(monkeypatch):
    now = datetime(2026, 9, 10, 12, 0)
    _fake_firestore(
        monkeypatch,
        {
            "uid-1": [
                _order_doc(
                    [{"name": "Latte", "qty": 1}], 180.0, now, "o1"
                ),
                _order_doc([{"name": "Mocha", "qty": 2}], 290.0, now, "o2"),
            ]
        },
    )

    result = orders_repo.get_order_history("uid-1", limit=2)

    assert [doc["id"] for doc in result] == ["o1", "o2"]
    assert result[0]["items"][0]["name"] == "Latte"
    assert result[0]["total"] == 180.0


def test_repo_scopes_reads_to_the_verified_uid(monkeypatch):
    """Reading user A must touch exactly user A's collection path."""
    _fake_firestore(
        monkeypatch,
        {"uid-1": [_order_doc([], 0, datetime(2026, 1, 1))]},
    )
    orders_repo.get_order_history("uid-1")
    with pytest.raises(AssertionError):
        orders_repo.get_order_history("uid-2")


def test_repo_orders_by_created_at_desc_with_bounded_limit(monkeypatch):
    _fake_firestore(
        monkeypatch, {"uid-1": [_order_doc([], 0, datetime(2026, 1, 1), "o1")]}
    )

    orders_repo.get_order_history("uid-1", limit=3)

    fake = orders_repo.get_firestore()
    assert fake.last_col.last_query.order_field == "createdAt"
    assert fake.last_col.last_query.order_direction == firestore.Query.DESCENDING
    assert fake.last_col.last_query.limit_value == 3


def test_repo_default_limit_comes_from_config(monkeypatch):
    _fake_firestore(
        monkeypatch, {"uid-1": [_order_doc([], 0, datetime(2026, 1, 1), "o1")]}
    )

    orders_repo.get_order_history("uid-1")

    fake = orders_repo.get_firestore()
    assert (
        fake.last_col.last_query.limit_value == orders_repo.ORDER_HISTORY_FETCH_LIMIT
    )


def test_repo_empty_history_returns_empty_list(monkeypatch):
    _fake_firestore(monkeypatch, {"uid-1": []})
    assert orders_repo.get_order_history("uid-1") == []


# ── Service layer ─────────────────────────────────────────────────

def _patch_repo(monkeypatch, docs):
    def fake_get(uid, **kwargs):
        return list(docs)

    monkeypatch.setattr(order_history_service.orders_repo, "get_order_history", fake_get)
    return order_history_service.get_order_history_service()


def _doc(items, total, created_at=None, doc_id="o1"):
    return {
        "id": doc_id,
        "items": items,
        "total": total,
        "createdAt": created_at,
    }


def test_service_returns_bounded_orders_newest_first(monkeypatch):
    docs = [_doc([{"name": f"Item{i}"}], 100, doc_id=f"o{i}") for i in range(5)]
    service = _patch_repo(monkeypatch, docs)

    records = service.get_history("uid-1", max_orders=3)

    assert [r.items[0]["name"] for r in records] == ["Item0", "Item1", "Item2"]
    assert len(records) == 3


def test_service_preserves_item_names_and_quantities(monkeypatch):
    _patch_repo(
        monkeypatch,
        [_doc([{"name": "Cappuccino", "qty": 1}, {"name": "Mocha", "qty": 2}], 190.0)],
    )

    records = order_history_service.get_order_history_service().get_history("u1")

    items = records[0].items
    assert items[0] == {"name": "Cappuccino", "qty": 1}
    assert items[1] == {"name": "Mocha", "qty": 2}


def test_service_bounds_items_per_order(monkeypatch):
    items = [{"name": f"Item{i}", "qty": 1} for i in range(10)]
    _patch_repo(monkeypatch, [_doc(items, 100)])

    records = order_history_service.get_order_history_service().get_history(
        "u1", max_items=4
    )

    assert len(records[0].items) == 4


def test_service_truncates_item_names(monkeypatch):
    _patch_repo(monkeypatch, [_doc([{"name": "x" * 300}], 100)])

    records = order_history_service.get_order_history_service().get_history(
        "u1", max_chars=40
    )

    name = records[0].items[0]["name"]
    assert len(name) <= 43
    assert name.endswith("...")


def test_service_preserves_dates(monkeypatch):
    _patch_repo(
        monkeypatch, [_doc([{"name": "Latte"}], 180, datetime(2026, 9, 8, 9, 30))]
    )

    records = order_history_service.get_order_history_service().get_history("u1")

    assert records[0].date == "2026-09-08"


def test_service_preserves_numeric_total(monkeypatch):
    _patch_repo(monkeypatch, [_doc([{"name": "Latte", "qty": 1}], 180.5)])

    records = order_history_service.get_order_history_service().get_history("u1")

    assert records[0].total == "180.5"


def test_service_handles_missing_total(monkeypatch):
    _patch_repo(monkeypatch, [_doc([{"name": "Latte"}], None)])

    records = order_history_service.get_order_history_service().get_history("u1")

    assert records[0].total is None


def test_service_ignores_malformed_records(monkeypatch):
    docs = [
        {"id": "a", "items": "not-a-list", "total": 100},  # items not a list
        {"id": "b", "items": ["garbage", {"qty": 2}, {"name": "  "}], "total": 50},
        {"id": "c", "items": [{"name": "Mocha", "qty": "two"}], "total": 90},
        {"id": "d", "items": [{"name": "Mocha", "qty": 1}], "total": "bogus"},
        {"id": "e", "items": [], "total": 10},  # no line items -> not useful
        "not-a-dict",
        {"id": "f", "items": [{"name": "Latte", "qty": 1}, {"name": None, "qty": 1}]},
    ]
    _patch_repo(monkeypatch, docs)

    records = order_history_service.get_order_history_service().get_history("u1")

    # a (not a list), b (no valid items), e (empty) and the string are dropped.
    assert [r.items[0]["name"] for r in records] == ["Mocha", "Mocha", "Latte"]
    assert records[0].total == "90"
    assert records[0].items[0].get("qty") is None  # non-numeric qty dropped
    assert records[1].total is None  # bogus total not invented


def test_service_no_unsupported_fields_invented(monkeypatch):
    # Even if the raw doc carried extra metadata, the service keeps only
    # name/qty per item and a numeric total — never doc ids or unknown keys.
    _patch_repo(
        monkeypatch,
        [
            {
                "id": "secret-id",
                "items": [{"name": "Latte", "qty": 1, "notes": "extra"}],
                "total": 180,
                "internalNote": "do not leak",
            }
        ],
    )

    records = order_history_service.get_order_history_service().get_history("u1")

    assert records[0].items == [{"name": "Latte", "qty": 1}]
    assert records[0].total == "180"
    assert "secret-id" not in str(records[0])


def test_service_empty_history_returns_empty(monkeypatch):
    _patch_repo(monkeypatch, [])
    records = order_history_service.get_order_history_service().get_history("u1")
    assert records == []


def test_service_firestore_failure_is_provider_error(monkeypatch):
    def boom(uid, **kwargs):
        raise RuntimeError("firestore down")

    monkeypatch.setattr(order_history_service.orders_repo, "get_order_history", boom)

    with pytest.raises(ProviderError):
        order_history_service.get_order_history_service().get_history("u1")


# ── Agent tool ────────────────────────────────────────────────────

class _FakeHistoryService:
    def __init__(self, records=None, exc=None):
        self.records = records if records is not None else []
        self.exc = exc
        self.calls = []

    def get_history(self, uid, **kwargs):
        self.calls.append(uid)
        if self.exc:
            raise self.exc
        return list(self.records)


def _patch_service(monkeypatch, fake):
    monkeypatch.setattr(
        order_history_tools,
        "get_order_history_service",
        lambda: fake,
    )
    return fake


def test_build_registers_only_order_tool():
    tools = build_order_history_tools("uid-1")
    assert [t.name for t in tools] == ["get_order_history"]


def test_tool_has_empty_arg_schema():
    tool = build_order_history_tools("uid-1")[0]
    assert tool.args == {}  # the model can never supply a UID or path


def test_tool_reads_history_for_closed_over_uid(monkeypatch):
    fake = _patch_service(monkeypatch, _FakeHistoryService())

    build_order_history_tools("uid-42")[0].invoke({})

    assert fake.calls == ["uid-42"]


def test_tool_never_accepts_a_uid_from_the_model(monkeypatch):
    fake = _patch_service(monkeypatch, _FakeHistoryService())

    tool = build_order_history_tools("uid-1")[0]
    assert tool.args == {}

    tool.invoke({})
    tool.invoke({"uid": "uid-other"})  # stray args are ignored by the framework
    assert fake.calls == ["uid-1", "uid-1"]


def test_tool_user_isolation(monkeypatch):
    """User A's tool reads only user A — there is no way to select user B."""
    fake = _patch_service(monkeypatch, _FakeHistoryService())

    build_order_history_tools("uid-A")[0].invoke({})
    build_order_history_tools("uid-B")[0].invoke({})

    assert fake.calls == ["uid-A", "uid-B"]


def test_tool_returns_empty_message_when_no_orders(monkeypatch):
    _patch_service(monkeypatch, _FakeHistoryService())

    output = build_order_history_tools("uid-1")[0].invoke({})

    assert "no past orders on record" in output


def test_tool_returns_unavailable_on_provider_error(monkeypatch):
    _patch_service(monkeypatch, _FakeHistoryService(exc=ProviderError("down")))

    output = build_order_history_tools("uid-1")[0].invoke({})

    assert "unavailable" in output


def test_tool_renders_compact_order_history(monkeypatch):
    _patch_service(
        monkeypatch,
        _FakeHistoryService(
            records=[
                OrderRecord(
                    date="2026-09-08",
                    items=[
                        {"name": "Cappuccino", "qty": 1},
                        {"name": "Chocolate Croissant", "qty": 1},
                    ],
                    total="390",
                ),
                OrderRecord(
                    date=None,
                    items=[{"name": "Cafe Mocha", "qty": 1}],
                    total="290",
                ),
            ]
        ),
    )

    output = build_order_history_tools("uid-1")[0].invoke({})

    assert "Order from 2026-09-08" in output
    assert "- Cappuccino x1" in output
    assert "- Chocolate Croissant x1" in output
    assert "Total: 390" in output
    assert "- Cafe Mocha x1" in output
    assert "uid" not in output.lower()
    assert "recent orders" in output.lower()


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


def test_chat_binds_order_tool_for_authenticated_user(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="hello")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What should I get?"), user={"uid": "uid-123"}
    )

    assert result.ok
    names = list(llm.bound_tools)
    assert "get_order_history" in [t.name for t in names]


def test_chat_marks_orders_used_when_retrieved(monkeypatch):
    _patch_service(monkeypatch, _FakeHistoryService())
    llm = _FakeLLM(
        _BoundModel(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_order_history",
                            "args": {},
                            "id": "order_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="Your last order was a cappuccino."),
            ]
        )
    )
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("What did I order last time?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_order_history is True


def test_chat_does_not_mark_orders_for_plain_menu_question(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="A cappuccino is 180.")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    result = chat_service.ChatService().process(
        _request("How much is a cappuccino?"), user={"uid": "uid-123"}
    )

    assert result.ok
    assert result.context.used_order_history is False


def test_chat_without_user_skips_order_tool(monkeypatch):
    llm = _FakeLLM(_BoundModel([AIMessage(content="hello")]))
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)

    chat_service.ChatService().process(_request("hi"))

    names = [t.name for t in llm.bound_tools]
    assert "get_order_history" not in names


def test_system_prompt_includes_order_history_guidance():
    prompt = chat_service.SYSTEM_PROMPT
    assert "get_order_history" in prompt
    assert "previous purchases" in prompt
    assert "never claim an order was placed" in prompt