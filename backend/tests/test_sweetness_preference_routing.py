"""Regression tests for natural-language preference routing.

A production bug let "something that's not too sweet" produce an answer
claiming the assistant has no search/vector-database capability instead of
using menu retrieval. These tests pin down the fix:

- the agent routes everyday preference phrasing to ``search_menu``
- ``search_menu`` maps "not too sweet" to the real menu sweetness values
- deterministic constraints (dairy-free, price) keep filtering
- ``convert_currency`` is untouched
- internal tool/database/vector-search details never reach the user
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

import app.services.chat_service as chat_service
import app.services.currency_tools as currency_tools
import app.services.menu_tools as menu_tools
import app.services.menu_service as menu_service_module
from app.api.schemas import ChatRequest


NO_SEARCH_UNAVAILABLE_MARKERS = (
    "don't have access to",
    "no access to",
    "vector database",
    "search functionality",
    "search system",
    "database",
    "retrieval",
    "embedding",
    "qdrant",
    "firestore",
    "gemini",
    "search_menu",
)


def _leaks_internal_details(answer: str) -> bool:
    lowered = (answer or "").lower()
    return any(marker in lowered for marker in NO_SEARCH_UNAVAILABLE_MARKERS)


# ── Fixtures ──────────────────────────────────────────────────────────────

def _item(name: str = "Cold Brew", price: int = 240, **overrides) -> dict:
    item = {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "category": "Cold Coffee",
        "description": "Smooth and lightly sweet.",
        "ingredients": ["coffee", "water"],
        "size": "240 ml",
        "price": price,
        "dietary": ["vegan", "vegetarian"],
        "caffeine": "medium",
        "temperature": "cold",
        "sweetness": "low",
        "flavor_profile": ["smooth"],
        "tags": ["cold-brew"],
        "available": True,
    }
    item.update(overrides)
    return item


class _BoundModel:
    def __init__(self, script):
        self.script = list(script)
        self.supplied_messages = []

    def invoke(self, messages):
        self.supplied_messages.append(messages)
        return self.script.pop(0)


class _FakeLLM:
    def __init__(self, bound_model):
        self.bound_model = bound_model
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self.bound_model


class _FakeMenuService:
    def __init__(self, items: list[dict] | None = None):
        self.items = list(items or [])
        self.calls: list[dict] = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.items


class _FakeCurrencyService:
    def convert(self, amount, from_currency, to_currency):
        return SimpleNamespace(
            original_amount=amount,
            source_currency=from_currency,
            converted_amount=1.99,
            target_currency=to_currency,
            rate=0.01047,
            rate_date="2026-09-13",
            provider="Frankfurter",
        )


def _tool_call(call_id: str, name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def _final_answer(message: str) -> AIMessage:
    return AIMessage(content=message)


def _request(user_message: str) -> ChatRequest:
    return ChatRequest.model_validate({"messages": [{"role": "user", "content": user_message}]})


def _run(monkeypatch, bound_script, fake_service, user_message, fake_currency=None):
    bound = _BoundModel(bound_script)
    llm = _FakeLLM(bound)
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr(menu_tools, "get_menu_service", lambda: fake_service)
    if fake_currency is not None:
        monkeypatch.setattr(currency_tools, "get_currency_service", lambda: fake_currency)
    result = chat_service.ChatService().process(_request(user_message))
    return bound, llm, result, fake_service


# ── 1. "not too sweet" routes to menu retrieval (never "search unavailable") ──

def test_not_too_sweet_uses_menu_retrieval(monkeypatch):
    fake = _FakeMenuService(
        items=[_item(name="Cold Brew", sweetness="none"), _item(name="Cappuccino", sweetness="low")]
    )
    _, llm, result, service = _run(
        monkeypatch,
        [
            _tool_call("c1", "search_menu", {"query": "not too sweet", "sweetness": "none, low"}),
            _final_answer("I'd recommend the Cold Brew — it's not sweet at all."),
        ],
        fake,
        "something that's not too sweet",
    )
    assert result.ok
    assert result.answer == "I'd recommend the Cold Brew — it's not sweet at all."
    assert service.calls and service.calls[0]["sweetness"] == "none, low"
    assert service.calls[0]["query"] == "not too sweet"
    # retrieval actually happened
    assert result.context.retrieval_used is True
    trace_tools = [step["tool"] for step in result.trace]
    assert "search_menu" in trace_tools
    # the assistant never told the customer search is unavailable
    assert not _leaks_internal_details(result.answer)
    # and the model was offered the menu + currency tools
    assert sorted(t.name for t in llm.bound_tools) == ["convert_currency", "search_menu"]


def test_less_sweet_uses_menu_retrieval(monkeypatch):
    fake = _FakeMenuService(items=[_item(name="Cappuccino", sweetness="low")])
    _, _, result, service = _run(
        monkeypatch,
        [
            _tool_call("c1", "search_menu", {"query": "less sweet", "sweetness": "low"}),
            _final_answer("The Cappuccino is naturally on the lighter, less-sweet side."),
        ],
        fake,
        "I want something less sweet",
    )
    assert result.ok
    assert "less-sweet" in result.answer
    assert service.calls and service.calls[0]["sweetness"] == "low"
    assert result.context.retrieval_used is True
    assert not _leaks_internal_details(result.answer)


def test_recommend_something_sweet_uses_menu_retrieval(monkeypatch):
    fake = _FakeMenuService(items=[_item(name="Mocha", sweetness="medium")])
    _, _, result, service = _run(
        monkeypatch,
        [
            _tool_call("c1", "search_menu", {"query": "sweet", "sweetness": "medium, high"}),
            _final_answer("The Mocha hits the spot if you're in for something sweet."),
        ],
        fake,
        "recommend something sweet",
    )
    assert result.ok
    assert "Mocha" in result.answer
    assert service.calls and service.calls[0]["sweetness"] == "medium, high"
    assert not _leaks_internal_details(result.answer)


# ── 2. Equivalent variations follow the same retrieval path ────────────────

@pytest.mark.parametrize(
    "user_message,query",
    [
        ("anything that's not overly sweet?", "not overly sweet"),
        ("I don't want something very sugary", "not sugary"),
        ("give me a less sweet coffee", "less sweet coffee"),
    ],
)
def test_synonymous_preference_phrasing_routes_to_menu(monkeypatch, user_message, query):
    fake = _FakeMenuService(items=[_item(name="Cappuccino", sweetness="low")])
    _, _, result, service = _run(
        monkeypatch,
        [
            _tool_call("c1", "search_menu", {"query": query, "sweetness": "none, low"}),
            _final_answer("I'd suggest the Cappuccino; it stays mild and not too sweet."),
        ],
        fake,
        user_message,
    )
    assert result.ok
    assert "Cappuccino" in result.answer
    assert result.context.retrieval_used is True
    assert service.calls and service.calls[0]["sweetness"] == "none, low"
    assert not _leaks_internal_details(result.answer)


# ── 3. Deterministic constraints still filter (dairy-free + price) ─────────

def test_dairy_free_under_price_is_deterministic(monkeypatch):
    """Hard constraints are applied as filters, not left to semantic guessing."""
    fake = _FakeMenuService(items=[_item(name="Coconut Mocha", price=320, dietary=["dairy-free"])])
    _, _, result, service = _run(
        monkeypatch,
        [
            _tool_call(
                "c1",
                "search_menu",
                {"query": "dairy-free", "dietary": "dairy-free", "max_price": 200},
            ),
            _final_answer(
                "We don't currently carry a dairy-free option under ₹200."
            ),
        ],
        fake,
        "something dairy-free under ₹200",
    )
    assert result.ok
    caller = service.calls[0]
    assert caller["dietary"] == "dairy-free"
    assert caller["max_price"] == 200
    assert "₹200" in result.answer
    assert not _leaks_internal_details(result.answer)


def test_menu_service_applies_sweetness_list_as_hard_filter(monkeypatch):
    """'none, low' returns items whose real sweetness is none or low — nothing else."""
    items = [
        _item("Cold Brew", sweetness="none"),
        _item("Cappuccino", sweetness="low"),
        _item("Mocha", sweetness="medium"),
        _item("Caramel", sweetness="high"),
    ]
    monkeypatch.setattr(menu_service_module, "is_semantic_menu_configured", lambda: False)
    monkeypatch.setattr(
        menu_service_module, "list_menu_items", lambda category=None: items
    )

    service = menu_service_module.MenuService()
    results = service.search(query=None, sweetness="none, low")
    names = {i["id"] for i in results}
    assert names == {"cold-brew", "cappuccino"}


def test_menu_service_single_sweetness_still_exact(monkeypatch):
    items = [
        _item("Cold Brew", sweetness="none"),
        _item("Cappuccino", sweetness="low"),
    ]
    monkeypatch.setattr(menu_service_module, "is_semantic_menu_configured", lambda: False)
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: items)

    service = menu_service_module.MenuService()
    results = service.search(query=None, sweetness="low")
    assert [i["id"] for i in results] == ["cappuccino"]


def test_sweetness_filter_accepts_list_of_values(monkeypatch):
    items = [_item("Cold Brew", sweetness="none"), _item("Cappuccino", sweetness="low")]
    monkeypatch.setattr(menu_service_module, "is_semantic_menu_configured", lambda: False)
    monkeypatch.setattr(menu_service_module, "list_menu_items", lambda category=None: items)

    service = menu_service_module.MenuService()
    results = service.search(query=None, sweetness=["none", "low"])
    assert {i["id"] for i in results} == {"cold-brew", "cappuccino"}


# ── 4. Currency conversion unaffected ──────────────────────────────────────

def test_currency_conversion_unaffected(monkeypatch):
    fake_menu = _FakeMenuService()
    fake_currency = _FakeCurrencyService()
    _, _, result, service = _run(
        monkeypatch,
        [
            _tool_call(
                "c2",
                "convert_currency",
                {"amount": 190, "from_currency": "INR", "to_currency": "USD"},
            ),
            _final_answer("₹190 is about $1.99 at today's reference rate."),
        ],
        fake_menu,
        "how much is ₹190 in USD?",
        fake_currency=fake_currency,
    )
    assert result.ok
    assert "$1.99" in result.answer
    assert service.calls == []  # no menu lookup for a pure currency question
    trace_tools = [step["tool"] for step in result.trace]
    assert trace_tools == ["convert_currency"]
    assert result.context.retrieval_used is False
    assert not _leaks_internal_details(result.answer)


# ── 5. Internal tool/database details are never surfaced ───────────────────

def test_leak_guard_detects_internal_phrasings():
    for leaked in (
        "I don't have access to a vector database or search functionality like that.",
        "I have no access to search.",
        "I can't access the menu database right now.",
        "The retrieval system failed.",
        "The embedding search returned no results.",
        "I use Qdrant to power my recommendations.",
        "I called search_menu and found it for you.",
        "I'll pull that from Firestore now.",
        "Gemini couldn't fetch the menu.",
        "We don't have a tool for that yet.",
    ):
        assert chat_service.contains_internal_leak(leaked), f"not caught: {leaked}"


def test_leak_guard_allows_harmless_phrasing():
    for harmless in (
        "We don't have any menu items that match.",
        "I couldn't find that on the menu.",
        "We don't carry anything like that on the menu.",
        "The dark hot chocolate is rich but not too sweet.",
        "I'd recommend the Iced Americano at 210.",
        "I'm sorry, we don't have any dairy-free items under 200.",
    ):
        assert not chat_service.contains_internal_leak(harmless), f"false positive: {harmless}"


def test_leaking_answer_is_replaced_with_safe_text(monkeypatch):
    leaked = (
        "I don't have access to a vector database or search functionality like that. "
        "I rely on our specific menu database."
    )
    _, _, result, _ = _run(
        monkeypatch,
        [_final_answer(leaked)],
        _FakeMenuService(),
        "something that's not too sweet",
    )
    assert result.ok
    assert result.answer == chat_service.INTERNAL_LEAK_SAFE_ANSWER
    assert result.answer == "I couldn't check the menu right now. Please try again."
    assert not _leaks_internal_details(result.answer)


def test_normal_answer_is_not_replaced(monkeypatch):
    _, _, result, _ = _run(
        monkeypatch,
        [_final_answer("I'd recommend the Cold Brew — it's not too sweet.")],
        _FakeMenuService(items=[_item()]),
        "something that's not too sweet",
    )
    assert result.ok
    assert result.answer == "I'd recommend the Cold Brew — it's not too sweet."


# ── 6. Agent instructions contain the routing + no-internals rules ─────────

def test_system_prompt_instructs_sweetness_filter_mapping():
    prompt = chat_service.SYSTEM_PROMPT
    assert "none, low" in prompt
    assert 'sweetness="none, low"' in prompt
    assert "never free-form adjectives" in prompt


def test_system_prompt_forbids_exposing_internals():
    prompt = chat_service.SYSTEM_PROMPT
    assert "never reveal how Grounded works internally" in prompt
    assert "I couldn't check the menu right now. Please try again." in prompt
    assert "lack search, a database, or retrieval" in prompt


def test_search_menu_docstring_documents_valid_values():
    description = menu_tools.search_menu.description or ""
    assert "not too sweet" in description
    assert "none, low" in description
    assert "very-high" in description.lower()
    assert "Never pass free-form adjectives" in description