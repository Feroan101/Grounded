"""Tests for Gemini tool-calling: search_menu.

Covers the full loop from the chat service down through the tool wrapper.
Gemini and the MenuService/Firestore are both mocked — real Firestore is
never contacted.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

import app.services.chat_service as chat_service
import app.services.menu_tools as menu_tools
from app.api.schemas import ChatRequest
from app.errors import ProviderError


# ── Helpers ────────────────────────────────────────────────────────

def _item(name: str = "Cappuccino", price: int = 240, **overrides) -> dict:
    item = {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "category": "Hot Coffee",
        "description": "Espresso with steamed milk.",
        "ingredients": ["espresso", "whole-milk"],
        "size": "240 ml",
        "price": price,
        "dietary": ["vegetarian"],
        "caffeine": "medium",
        "temperature": "hot",
        "sweetness": "medium",
        "flavor_profile": ["creamy", "bold"],
        "tags": ["milk-based"],
        "available": True,
    }
    item.update(overrides)
    return item


class _BoundModel:
    """Mimics ``llm.bind_tools(tools)`` returning a runnable with invoke()."""

    def __init__(self, script):
        self.script = list(script)
        self.supplied_messages = []

    def invoke(self, messages):
        self.supplied_messages.append(messages)
        return self.script.pop(0)


class _FakeLLM:
    """Mimics the ChatModel protocol: bind_tools + invoke."""

    def __init__(self, bound_model):
        self.bound_model = bound_model
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self.bound_model


class _FakeMenuService:
    """MenuService stand-in; never touches Firestore."""

    def __init__(self, items: list[dict] | None = None, exc: Exception | None = None):
        self.items = items or []
        self.exc = exc
        self.calls: list[dict] = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.items


def _tool_call_aimessage(args: dict, call_id: str = "call_menu_1"):
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "search_menu",
                "args": args,
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


def _final_answer(message: str):
    return AIMessage(content=message)


def _request(user_message: str) -> ChatRequest:
    return ChatRequest.model_validate(
        {"messages": [{"role": "user", "content": user_message}]}
    )


def _run_chat(monkeypatch, bound_script, fake_service, user_message=None):
    bound = _BoundModel(bound_script)
    llm = _FakeLLM(bound)
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr(menu_tools, "get_menu_service", lambda: fake_service)

    message = user_message or "What iced drinks do you have?"
    result = chat_service.ChatService().process(_request(message))
    return bound, llm, result, fake_service


# ── 1. Gemini decides to call search_menu for a menu question ──────

def test_gemini_calls_search_menu_for_menu_question(monkeypatch):
    fake_service = _FakeMenuService(items=[_item(name="Iced Americano", price=210)])
    bound, llm, result, service = _run_chat(
        monkeypatch,
        [
            _tool_call_aimessage({"query": "iced"}),
            _final_answer("I'd recommend the Iced Americano — it's 210."),
        ],
        fake_service,
    )

    assert result.ok
    assert result.answer == "I'd recommend the Iced Americano — it's 210."
    # The model was given both tools.
    assert sorted(t.name for t in llm.bound_tools) == [
        "convert_currency",
        "search_menu",
    ]
    # The model chose to call the menu tool exactly once.
    assert len(service.calls) == 1
    # And the loop produced a final answer after the tool round.
    assert len(bound.supplied_messages) == 2


# ── 2. Correct filter arguments are passed to the service ──────────

def test_correct_filters_passed_to_service(monkeypatch):
    fake_service = _FakeMenuService(items=[_item()])
    args = {
        "query": "iced",
        "category": "Cold Coffee",
        "max_price": 250,
        "dietary": "vegan",
        "caffeine": "high",
        "temperature": "cold",
        "sweetness": "none",
        "available": True,
        "flavor": "refreshing",
    }
    _, _, _, service = _run_chat(
        monkeypatch,
        [_tool_call_aimessage(args), _final_answer("done")],
        fake_service,
    )

    assert service.calls[0] == args


# ── 3. Tool result is returned to Gemini with real menu data ───────

def test_tool_result_returned_to_gemini_with_real_data(monkeypatch):
    fake_service = _FakeMenuService(items=[_item(name="Cappuccino", price=240)])
    bound, _, _, _ = _run_chat(
        monkeypatch,
        [_tool_call_aimessage({"query": "cappuccino"}), _final_answer("final")],
        fake_service,
    )

    # On the second invocation the tool result must be in the conversation.
    second_round_messages = bound.supplied_messages[1]
    tool_messages = [m for m in second_round_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_menu_1"
    assert "Cappuccino" in tool_messages[0].content
    assert "price 240" in tool_messages[0].content
    # The tool-calling AIMessage must also be in the conversation.
    assert any(isinstance(m, AIMessage) and m.tool_calls for m in second_round_messages)


# ── 4. Gemini produces a final answer from the tool result ────────

def test_gemini_produces_final_answer_from_tool_result(monkeypatch):
    fake_service = _FakeMenuService(items=[_item(name="Iced Americano", price=210)])
    _, _, result, service = _run_chat(
        monkeypatch,
        [
            _tool_call_aimessage({"query": "iced", "max_price": 250}),
            _final_answer(
                "The Iced Americano is 210 and it's vegan-friendly. "
                "It comes cold with bold, refreshing flavors."
            ),
        ],
        fake_service,
    )

    assert result.ok
    assert "Iced Americano" in result.answer
    assert "210" in result.answer
    # The answer reflects actual tool output — no invented items.
    assert service.calls[0]["query"] == "iced"
    assert service.calls[0]["max_price"] == 250


# ── 5. No match is reported honestly (no hallucination) ────────────

def test_no_match_is_reported_honestly(monkeypatch):
    fake_service = _FakeMenuService(items=[])
    bound, _, result, _ = _run_chat(
        monkeypatch,
        [
            _tool_call_aimessage({"query": "pancakes"}),
            _final_answer("We don't have pancakes on the menu."),
        ],
        fake_service,
    )

    assert result.ok
    assert "pancakes" in result.answer
    # The model was told there is no match rather than given invented data.
    second_round_messages = bound.supplied_messages[1]
    tool_messages = [m for m in second_round_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert "No menu items match" in tool_messages[0].content


# ── 6. Tool failure is handled without hallucinating ───────────────

def test_tool_failure_handled_without_hallucinating(monkeypatch):
    fake_service = _FakeMenuService(exc=ProviderError("Firestore is down"))
    bound, _, result, _ = _run_chat(
        monkeypatch,
        [
            _tool_call_aimessage({"query": "matcha"}),
            _final_answer(
                "I'm sorry, I can't look up the menu right now — it's "
                "temporarily unavailable."
            ),
        ],
        fake_service,
    )

    assert result.ok
    # No invented menu data appears in the final answer.
    assert "matcha" not in result.answer.lower()

    second_round_messages = bound.supplied_messages[1]
    tool_messages = [m for m in second_round_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert "failed" in tool_messages[0].content
    assert "Do not guess" in tool_messages[0].content


# ── 7. Honest metadata: retrieval is flagged when the menu is used ─

def test_retrieval_metadata_set_when_search_menu_used(monkeypatch):
    fake_service = _FakeMenuService(items=[_item()])
    _, _, result, _ = _run_chat(
        monkeypatch,
        [_tool_call_aimessage({"query": "latte"}), _final_answer("done")],
        fake_service,
    )

    assert result.context.retrieval_used is True
    assert result.context.retrieval_count == 1


def test_non_menu_question_skips_tool(monkeypatch):
    fake_service = _FakeMenuService(items=[_item()])
    bound, _, result, service = _run_chat(
        monkeypatch,
        [_final_answer("Happy to help! What can I get you?")],
        fake_service,
        user_message="Hi!",
    )

    assert result.ok
    assert service.calls == []  # tool never invoked
    assert result.context.retrieval_used is False
    assert len(bound.supplied_messages) == 1  # single round, no tool call


# ── Supporting behaviour ───────────────────────────────────────────

def test_display_capped_with_total_count(monkeypatch):
    many = [_item(name=f"Item {i}", price=150 + i) for i in range(10)]
    fake_service = _FakeMenuService(items=many)
    monkeypatch.setattr(menu_tools, "get_menu_service", lambda: fake_service)

    output = menu_tools.search_menu.invoke({"query": "item"})

    assert "10 items match" in output
    assert "showing the first 8" in output
    assert "Item 1" in output
    assert "Item 9" not in output  # beyond the display limit


def test_search_menu_tool_delegates_to_service_through_wrapper(monkeypatch):
    """The @tool delegates to MenuService — no duplicate logic."""
    fake_service = _FakeMenuService(items=[_item(name="Cappuccino", price=240)])
    monkeypatch.setattr(menu_tools, "get_menu_service", lambda: fake_service)

    output = menu_tools.search_menu.invoke({"query": "cappuccino"})

    assert len(fake_service.calls) == 1
    assert fake_service.calls[0]["query"] == "cappuccino"
    assert "Cappuccino" in output
    assert "price 240" in output