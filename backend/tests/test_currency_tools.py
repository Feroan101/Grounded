"""Tests for Gemini tool-calling: convert_currency.

Covers the full loop from the chat service down through the tool wrapper.
Gemini and the CurrencyService/external API are both mocked — the real
Frankfurter API is never contacted.
"""
from __future__ import annotations

from decimal import Decimal

from langchain_core.messages import AIMessage, ToolMessage

import app.services.chat_service as chat_service
import app.services.currency_tools as currency_tools
from app.api.schemas import ChatRequest
from app.errors import ProviderError
from app.services.currency_service import ConversionResult


# ── Fakes ─────────────────────────────────────────────────────────

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


class _FakeCurrencyService:
    """CurrencyService stand-in; never touches the network."""

    def __init__(self, result: ConversionResult | None, exc: Exception | None = None):
        self.result = result
        self.exc = exc
        self.calls: list[dict] = []

    def convert(self, *, amount, from_currency, to_currency):
        self.calls.append(
            {
                "amount": amount,
                "from_currency": from_currency,
                "to_currency": to_currency,
            }
        )
        if self.exc:
            raise self.exc
        return self.result


def _conversion_result() -> ConversionResult:
    return ConversionResult(
        original_amount=Decimal("100"),
        source_currency="USD",
        target_currency="INR",
        rate=Decimal("83.50"),
        converted_amount=Decimal("8350.00"),
        rate_date="2025-04-09",
    )


def _tool_call_aimessage(extra_content: str = ""):
    return AIMessage(
        content=extra_content,
        tool_calls=[
            {
                "name": "convert_currency",
                "args": {
                    "amount": 100,
                    "from_currency": "USD",
                    "to_currency": "INR",
                },
                "id": "call_1",
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
    """Patch the LLM + currency service, then run ChatService.process()."""
    bound = _BoundModel(bound_script)
    llm = _FakeLLM(bound)
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr(currency_tools, "get_currency_service", lambda: fake_service)

    message = user_message or "How much is 100 USD in INR?"
    result = chat_service.ChatService().process(_request(message))
    return bound, llm, result, fake_service


# ── 1. Gemini decides to call convert_currency ────────────────────

def test_gemini_calls_convert_currency_for_conversion_question(monkeypatch):
    fake_service = _FakeCurrencyService(_conversion_result())
    bound, llm, result, service = _run_chat(
        monkeypatch,
        [_tool_call_aimessage(), _final_answer("100 USD is about 8350.00 INR.")],
        fake_service,
    )

    assert result.ok
    assert result.answer == "100 USD is about 8350.00 INR."
    # The model was given the chance to use tools.
    assert sorted(t.name for t in llm.bound_tools) == [
        "convert_currency",
        "search_menu",
    ]
    # The model chose to call the tool exactly once.
    assert len(service.calls) == 1
    # And the loop produced a final answer after the tool round.
    assert len(bound.supplied_messages) == 2


# ── 2. Correct arguments are passed to the tool ───────────────────

def test_correct_arguments_passed_to_tool(monkeypatch):
    fake_service = _FakeCurrencyService(_conversion_result())
    _, _, _, service = _run_chat(
        monkeypatch,
        [_tool_call_aimessage(), _final_answer("done")],
        fake_service,
    )

    call = service.calls[0]
    assert call["amount"] == 100
    assert call["from_currency"] == "USD"
    assert call["to_currency"] == "INR"


# ── 3. Tool result is returned to Gemini ──────────────────────────

def test_tool_result_returned_to_gemini(monkeypatch):
    fake_service = _FakeCurrencyService(_conversion_result())
    bound, _, _, service = _run_chat(
        monkeypatch,
        [_tool_call_aimessage(), _final_answer("final")],
        fake_service,
    )

    # On the second invocation the tool result must be in the conversation.
    second_round_messages = bound.supplied_messages[1]
    tool_messages = [m for m in second_round_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_1"
    assert "8350.00 INR" in tool_messages[0].content
    assert "exchange rate: 1 USD = 83.50 INR" in tool_messages[0].content
    assert "Frankfurter" in tool_messages[0].content
    # The tool-calling AIMessage must also be in the conversation.
    assert any(isinstance(m, AIMessage) and m.tool_calls for m in second_round_messages)


# ── 4. Gemini produces a final answer from the tool result ────────

def test_gemini_produces_final_answer_from_tool_result(monkeypatch):
    fake_service = _FakeCurrencyService(_conversion_result())
    _, _, result, service = _run_chat(
        monkeypatch,
        [
            _tool_call_aimessage(),
            _final_answer(
                "100 USD is about ₹8,350.00 — the exchange rate is "
                "1 USD = 83.50 INR, published on 2025-04-09. "
                "Note this is a reference rate, not a live trading price."
            ),
        ],
        fake_service,
    )

    assert result.ok
    assert "100 USD is about ₹8,350.00" in result.answer
    # The answer reflects actual tool output — no invented numbers.
    assert service.calls[0]["amount"] == 100


# ── 5. Tool failure is handled without hallucinating ──────────────

def test_tool_failure_handled_without_hallucinating(monkeypatch):
    fake_service = _FakeCurrencyService(
        result=None, exc=ProviderError("the exchange-rate service is down")
    )
    bound, _, result, service = _run_chat(
        monkeypatch,
        [
            _tool_call_aimessage(),
            _final_answer(
                "I'm sorry, I can't convert that right now — the exchange-rate "
                "service is temporarily unavailable."
            ),
        ],
        fake_service,
    )

    assert result.ok
    # No invented conversion appears in the final answer.
    assert "₹" not in result.answer
    assert "unavailable" in result.answer

    # Gemini was told the tool failed rather than given a made-up number.
    second_round_messages = bound.supplied_messages[1]
    tool_messages = [m for m in second_round_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert "failed" in tool_messages[0].content
    assert "Do not guess" in tool_messages[0].content


# ── Supporting behaviour ──────────────────────────────────────────

def test_non_conversion_question_skips_tool(monkeypatch):
    fake_service = _FakeCurrencyService(_conversion_result())
    bound, _, result, service = _run_chat(
        monkeypatch,
        [_final_answer("Try the cold brew.")],
        fake_service,
        user_message="What should I order?",
    )

    assert result.ok
    assert result.answer == "Try the cold brew."
    assert service.calls == []  # tool never invoked
    assert len(bound.supplied_messages) == 1  # single round, no tool call


def test_unknown_tool_name_reported_to_model(monkeypatch):
    fake_service = _FakeCurrencyService(_conversion_result())
    unknown_call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "not_a_real_tool",
                "args": {},
                "id": "call_unknown",
                "type": "tool_call",
            }
        ],
    )
    bound, _, result, _service = _run_chat(
        monkeypatch,
        [unknown_call, _final_answer("I don't have that capability.")],
        fake_service,
    )

    assert result.ok
    second_round_messages = bound.supplied_messages[1]
    tool_messages = [m for m in second_round_messages if isinstance(m, ToolMessage)]
    assert tool_messages[0].content == "Tool 'not_a_real_tool' is not available."


def test_tool_loop_terminates_at_max_rounds(monkeypatch):
    """If the model keeps requesting tools, the loop caps and stops."""
    fake_service = _FakeCurrencyService(_conversion_result())
    bound, _, result, service = _run_chat(
        monkeypatch,
        [_tool_call_aimessage() for _ in range(10)],
        fake_service,
    )

    # The loop terminated instead of running all 10 scripted calls.
    assert len(bound.supplied_messages) == 4  # _MAX_TOOL_ROUNDS
    # With no final text produced, the service surfaces an honest empty answer.
    assert result.status_code == 502


def test_currency_tool_uses_existing_service_through_wrapper(monkeypatch):
    """The @tool delegates to CurrencyService — no duplicate logic."""
    fake_service = _FakeCurrencyService(_conversion_result())
    monkeypatch.setattr(currency_tools, "get_currency_service", lambda: fake_service)

    output = currency_tools.convert_currency.invoke(
        {"amount": 100, "from_currency": "USD", "to_currency": "INR"}
    )

    assert len(fake_service.calls) == 1
    assert fake_service.calls[0]["amount"] == 100
    assert "8350.00 INR" in output
    assert "83.50" in output
    assert "Frankfurter" in output


# ── Real-service helpers (mock httpx, keep real CurrencyService) ──

_RATES = {
    ("INR", "USD"): ("0.01048", "2026-09-11"),
    ("USD", "INR"): ("85.25", "2026-09-10"),
}


def _mock_rate_get(*args, **kwargs):
    """Return the correct Frankfurter v2 /rate payload for the requested pair."""
    import json, re
    url = args[0] if args else kwargs.get("url", "")
    m = re.search(r"/rate/(\w+)/(\w+)$", str(url))
    base, quote = (m.group(1), m.group(2)) if m else ("USD", "INR")
    rate_str, date = _RATES.get((base, quote), ("1.0", "2026-01-01"))

    class _Resp:
        status_code = 200
        def json(self):
            return {"base": base, "quote": quote, "rate": rate_str, "date": date}
        @property
        def text(self):
            return json.dumps(self.json())

    return _Resp()


def _run_chat_with_real_service(monkeypatch, script, user_message="How much is ₹190 in USD?"):
    import app.services.currency_service as cs_mod

    bound = _BoundModel(script)
    llm = _FakeLLM(bound)
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr(cs_mod.httpx, "get", _mock_rate_get)
    result = chat_service.ChatService().process(_request(user_message))
    return bound, result


class _FakeMenuService:
    """Menu stub for the menu→currency ordering tests."""
    def __init__(self):
        self.calls: list[dict] = []
    def search(self, **kwargs):
        self.calls.append(kwargs)
        return [{
            "id": "m1",
            "name": "Chilled House Nut Milk",
            "category": "Non-Coffee Beverages",
            "price": 190.0,
            "size": "300 ml",
            "caffeine": "none",
            "temperature": "cold",
            "sweetness": "low",
            "dietary": ["vegan", "dairy-free"],
            "available": True,
            "description": "House-made nut milk, chilled.",
        }]


# ── 1. ₹190 → USD ─────────────────────────────────────────────

def test_inr190_to_usd_via_tool(monkeypatch):
    tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "convert_currency",
            "args": {"amount": 190, "from_currency": "₹", "to_currency": "USD"},
            "id": "c1",
            "type": "tool_call",
        }],
    )
    bound, result = _run_chat_with_real_service(
        monkeypatch,
        [tool_call, AIMessage(content="₹190 is about $1.99.")],
    )
    assert result.ok
    tool_msgs = [m for m in bound.supplied_messages[1] if isinstance(m, ToolMessage)]
    assert len(tool_msgs) == 1
    assert "190.0 INR" in tool_msgs[0].content
    assert "1.99 USD" in tool_msgs[0].content
    assert "0.01048" in tool_msgs[0].content
    assert result.answer == "₹190 is about $1.99."


# ── 2. INR → USD using currency names ──────────────────────────

def test_currency_names_inr_to_usd(monkeypatch):
    tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "convert_currency",
            "args": {
                "amount": 190,
                "from_currency": "Indian rupees",
                "to_currency": "US dollars",
            },
            "id": "c1",
            "type": "tool_call",
        }],
    )
    bound, result = _run_chat_with_real_service(
        monkeypatch,
        [tool_call, AIMessage(content="190 INR ≈ $1.99.")],
    )
    assert result.ok
    tool_msgs = [m for m in bound.supplied_messages[1] if isinstance(m, ToolMessage)]
    assert "190.0 INR" in tool_msgs[0].content
    assert "1.99 USD" in tool_msgs[0].content


# ── 3. USD → INR ───────────────────────────────────────────────

def test_usd_to_inr_reversed_via_tool(monkeypatch):
    tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "convert_currency",
            "args": {"amount": 25, "from_currency": "USD", "to_currency": "INR"},
            "id": "c1",
            "type": "tool_call",
        }],
    )
    bound, result = _run_chat_with_real_service(
        monkeypatch,
        [tool_call, AIMessage(content="25 USD ≈ ₹2131.25.")],
    )
    assert result.ok
    tool_msgs = [m for m in bound.supplied_messages[1] if isinstance(m, ToolMessage)]
    assert "25.0 USD" in tool_msgs[0].content
    assert "2131.25 INR" in tool_msgs[0].content


# ── 4. Menu price → currency conversion (ordering) ─────────────

def test_menu_price_then_currency_conversion(monkeypatch):
    import app.services.menu_tools as menu_tools_mod

    menu_svc = _FakeMenuService()
    bound = _BoundModel([
        AIMessage(
            content="",
            tool_calls=[{
                "name": "search_menu",
                "args": {"dietary": "dairy-free", "max_price": 200},
                "id": "c1",
                "type": "tool_call",
            }],
        ),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "convert_currency",
                "args": {"amount": 190, "from_currency": "INR", "to_currency": "USD"},
                "id": "c2",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Chilled House Nut Milk is ₹190, about $1.99."),
    ])
    llm = _FakeLLM(bound)
    import app.services.currency_service as cs_mod
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr(menu_tools_mod, "get_menu_service", lambda: menu_svc)
    monkeypatch.setattr(cs_mod.httpx, "get", _mock_rate_get)
    result = chat_service.ChatService().process(
        _request("I want something dairy-free under ₹200. What is that in USD?")
    )

    assert result.ok
    assert menu_svc.calls[0]["dietary"] == "dairy-free"
    assert menu_svc.calls[0]["max_price"] == 200
    # Round 1: search_menu result
    round1_tools = [m for m in bound.supplied_messages[1] if isinstance(m, ToolMessage)]
    assert any("Chilled House Nut Milk" in m.content for m in round1_tools)
    # Round 2: convert_currency result — amount matches the menu price
    round2_tools = [m for m in bound.supplied_messages[2] if isinstance(m, ToolMessage)]
    assert any("190.0 INR" in m.content for m in round2_tools)
    assert any("1.99 USD" in m.content for m in round2_tools)
    assert result.answer == "Chilled House Nut Milk is ₹190, about $1.99."


# ── 5. Normal menu question — currency tool must NOT be invoked ─

def test_menu_question_does_not_invoke_currency(monkeypatch):
    import app.services.menu_tools as menu_tools_mod

    fake_currency = _FakeCurrencyService(_conversion_result())
    menu_svc = _FakeMenuService()
    bound = _BoundModel([
        AIMessage(
            content="",
            tool_calls=[{
                "name": "search_menu",
                "args": {"temperature": "cold"},
                "id": "c1",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="Chilled House Nut Milk is a cold option."),
    ])
    llm = _FakeLLM(bound)
    monkeypatch.setattr(chat_service, "get_llm", lambda: llm)
    monkeypatch.setattr(menu_tools_mod, "get_menu_service", lambda: menu_svc)
    monkeypatch.setattr(currency_tools, "get_currency_service", lambda: fake_currency)
    result = chat_service.ChatService().process(_request("What cold drinks do you have?"))

    assert result.ok
    assert fake_currency.calls == []
    assert len(menu_svc.calls) == 1