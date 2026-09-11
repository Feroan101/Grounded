"""Scripted LLM for deterministic evaluation runs.

The reference model is a tiny state-machine: it drives tool calls defined by a
case's ``plan`` list, then produces a deterministic answer by parsing the real
tool output that the production pipeline executed. No external providers are
contacted.

Only ``bind_tools`` and ``invoke`` are implemented — the exact shape the chat
service uses.
"""
from __future__ import annotations

import re
from decimal import Decimal
from decimal import Decimal as D
from decimal import Decimal
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage


# --------------------------------------------------------------------------- #
# Parsers for real tool outputs
# --------------------------------------------------------------------------- #

def parse_menu_first(content: str) -> tuple[str | None, str | None]:
    """Parse ``name`` and ``price`` of the first menu line from search_menu."""
    m = re.search(r"(?:^|\n)\d+\.\s+(.+?)\s+\((.+?)\)\s+\|\s+price\s+(\S+)", content)
    if m:
        return m.group(1).strip(), m.group(3).strip()
    return None, None


def parse_conversion(content: str) -> tuple[str | None, str | None]:
    """Parse ``converted_amount`` and ``target_currency`` from convert_currency."""
    m = re.search(r"=\s*([\d.]+)\s+([A-Z]{3})", content)
    if m:
        return m.group(1), m.group(2)
    return None, None


def parse_order_item(content: str) -> str | None:
    m = re.search(r"(?m)^- (.+?)(?:\s+x\d+)?$", content)
    return m.group(1).strip() if m else None


def parse_order_empty(content: str) -> bool:
    return content.startswith("This customer has no past orders on record")


def parse_history_disabled(content: str) -> bool:
    return content.startswith("This customer has conversation history turned off")


def parse_history_empty(content: str) -> bool:
    return content.startswith("This customer has no recent past conversations")


def parse_history_user_msg(content: str) -> str | None:
    matches = re.findall(r"(?m)^User: (.+)$", content)
    return matches[-1].strip() if matches else None


def parse_prefs_disabled(content: str) -> bool:
    return content.startswith("The customer has switched off preference personalization")


def parse_prefs_empty(content: str) -> bool:
    return content.startswith("The customer has no stored preferences yet")


def parse_prefs_favorite(content: str) -> str | None:
    m = re.search(r"(?m)^- Favorite drink: (.+)$", content)
    return m.group(1).strip() if m else None


def parse_prefs_milk(content: str) -> str | None:
    m = re.search(r"(?m)^- Milk preference: (.+)$", content)
    return m.group(1).strip() if m else None


def parse_prefs_no_trivia(content: str) -> bool:
    return "Trivia:" in content


# --------------------------------------------------------------------------- #
# Context builder
# --------------------------------------------------------------------------- #

def _build_tool_context(messages) -> dict[str, str]:
    """Map tool names to the content of their *last* ToolMessage invocation."""
    id_to_name: dict[str, str] = {}
    name_to_content: dict[str, list[str]] = {}
    for msg in messages:
        if isinstance(msg, AIMessage):
            for call in (getattr(msg, "tool_calls", None) or []):
                if isinstance(call, dict):
                    call_id = call.get("id") or ""
                    name = call.get("name") or ""
                    if call_id and name:
                        id_to_name[call_id] = name
        if isinstance(msg, ToolMessage):
            name = id_to_name.get(msg.tool_call_id or "", msg.name or "")
            name_to_content.setdefault(name, []).append(str(msg.content or ""))
    return {name: pieces[-1] for name, pieces in name_to_content.items() if pieces}


# --------------------------------------------------------------------------- #
# Answer builder
# --------------------------------------------------------------------------- #

def _build_answer(step: dict, tool_ctx: dict[str, str], case: Any | None = None) -> str:
    style = step.get("style", "auto")
    explicit = step.get("text")
    if explicit:
        return explicit

    if style == "refusal":
        return "I can't confirm that from what I know."

    # --- currency answers -------------------------------------------------- #
    conv = tool_ctx.get("convert_currency")
    conv_amt, conv_tgt = parse_conversion(conv or "") if conv else (None, None)
    if style in ("currency", "currency_menu") and conv_amt and conv_tgt:
        if style == "currency_menu":
            src = "INR"
            amount_str = step.get("amount", "290")
            name = _first_menu_name(tool_ctx) or "the item"
            price = _first_menu_price(tool_ctx) or amount_str
            return f"I'd recommend the {name}, priced at {price} {src} — that's about {conv_amt} {conv_tgt}."
        amount = step.get("amount", "100")
        src_currency = step.get("src", "USD")
        tgt_currency = step.get("tgt", "INR")
        if style == "currency" and tgt_currency == "GBP":
            return f"{amount} EUR converts to {conv_amt} GBP at today's reference rate."
        return f"{amount} {src_currency} converts to {conv_amt} {conv_tgt} at today's reference rate."

    menu_result = tool_ctx.get("search_menu") or ""
    menu_name, menu_price = parse_menu_first(menu_result)
    no_match = menu_result.startswith("No menu items match the search criteria")
    hist_result = tool_ctx.get("get_conversation_history") or ""
    order_result = tool_ctx.get("get_order_history") or ""
    prefs_result = tool_ctx.get("get_customer_preferences") or ""

    # --- history ----------------------------------------------------------- #
    if hist_result and style in ("history", "history_menu", "auto"):
        if parse_history_disabled(hist_result):
            return "I can't access your past conversations — you've turned that off."
        if parse_history_empty(hist_result):
            return "I don't have any earlier conversations on record."
        user_msg = parse_history_user_msg(hist_result)
        if user_msg:
            if style == "history_menu" and menu_name and menu_price:
                topic = _user_question_topic(user_msg)
                return f"You asked about {topic} earlier — the {menu_name}, priced at {menu_price}, is available."
            return f'From a past conversation, you asked: "{user_msg}".'

    # --- order answers ----------------------------------------------------- #
    if order_result and style in ("orders", "auto") and not no_match:
        item = parse_order_item(order_result)
        if parse_order_empty(order_result):
            return "I don't have any past orders on record."
        if item and style == "orders":
            return f"In your past orders I can see the {item}."

    # --- preference-based answers ------------------------------------------ #
    disabled = parse_prefs_disabled(prefs_result)
    empty = parse_prefs_empty(prefs_result)
    fav = parse_prefs_favorite(prefs_result)
    if prefs_result and style in ("pref_menu", "pref_orders_menu"):
        if not disabled and fav and menu_name and menu_price:
            if fav == menu_name:
                return f"I'd recommend the {menu_name}, priced at {menu_price} — it matches a preference you've shared with me."
            # Favorite differs from first menu line; still recommend first.
            return f"I'd recommend the {menu_name}, priced at {menu_price} — it suits your stored taste profile."
        if style == "pref_menu":
            milk = parse_prefs_milk(prefs_result) if not disabled and not empty else None
            if milk and milk.lower() == "oat" and menu_name and menu_price:
                return f"I'd recommend the {menu_name}, priced at {menu_price}. I've kept your oat-milk preference in mind."
            if menu_name and menu_price:
                return f"I'd recommend the {menu_name}, priced at {menu_price}."
            if disabled:
                return "I'll keep your current request in mind and recommend from the menu."
            return "I'd recommend something from the current menu."

    if prefs_result and style == "pref_orders_menu":
        usual = parse_order_item(order_result) if order_result else None
        rec = menu_name
        if usual and rec and menu_price:
            return f"Different from your usual {usual}, I'd recommend the {rec}, priced at {menu_price} — it also suits your taste for lower sweetness."
        if rec and menu_price:
            return f"I'd recommend the {rec}, priced at {menu_price}."

    # --- no-result --------------------------------------------------------- #
    if no_match:
        return "I couldn't find anything matching that on our menu."

    # --- generic menu answer ----------------------------------------------- #
    if menu_name and menu_price:
        return f"I'd recommend the {menu_name}, priced at {menu_price}."

    return "I'll take care of that for you."


def _first_menu_name(tool_ctx: dict[str, str]) -> str | None:
    name, _ = parse_menu_first(tool_ctx.get("search_menu", ""))
    return name


def _first_menu_price(tool_ctx: dict[str, str]) -> str | None:
    _, price = parse_menu_first(tool_ctx.get("search_menu", ""))
    return price


def _user_question_topic(msg: str) -> str:
    q = re.sub(r"^(Did|Is|Are|Can|What|How|Should|Could|Would)\s+(I|we|you|they)?\s*", "", msg, flags=re.I)
    q = re.sub(r"\?+$", "", q).strip().lower()
    if "cold brew" in q:
        return "cold brew"
    return q or "that"


# --------------------------------------------------------------------------- #
# LLM + Model
# --------------------------------------------------------------------------- #

class ScriptedLLM:
    """Thin wrapper: ``bind_tools`` produces a one-shot ``_ScriptedModel``."""

    def __init__(self, case: Any):
        self.case = case

    def bind_tools(self, tools):  # noqa: D102
        return _ScriptedModel(self.case)


class _ScriptedModel:
    def __init__(self, case: Any):
        self.case = case
        self.step = 0
        self.plan = list(case.plan)

    def invoke(self, messages):
        # Find next tool-call step
        while self.step < len(self.plan):
            action = self.plan[self.step]
            self.step += 1
            if action.get("type") == "tools":
                calls = action["calls"]
                tool_calls = [
                    {
                        "name": c.get("name") or "",
                        "args": c.get("args") or {},
                        "id": f"call_{self.step - 1}_{i}",
                        "type": "tool_call",
                    }
                    for i, c in enumerate(calls)
                ]
                return AIMessage(content="", tool_calls=tool_calls)

        # Answer step: build final answer from real tool outputs
        tool_ctx = _build_tool_context(messages)
        return AIMessage(content=_build_answer(self.plan[-1], tool_ctx, self.case))