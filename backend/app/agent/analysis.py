"""Query analysis for the agent.

Phase 1 uses a deterministic, testable classifier to decide intent and what to
search for. This is a real decision made against real state.

In a later phase an LLM-powered analyzer can replace the keyword logic behind
the same interface (``analyze_query()``), leaving the graph shape unchanged.
No internal chain-of-thought is ever exposed to the client.
"""
from __future__ import annotations

import re

from app.agent.state import QueryAnalysis
from app.rag.retriever import RetrievalFilter

_MENU_INTENT_TERMS = {
    "menu",
    "drink",
    "coffee",
    "latte",
    "espresso",
    "cold brew",
    "cappuccino",
    "americano",
    "mocha",
    "matcha",
    "tea",
    "order",
    "price",
    "cost",
    "ingredient",
    "what do you have",
    "on the menu",
    "size",
    "milk",
    "oat milk",
    "food",
    "pastry",
    "bagel",
    "sandwich",
}

_GREETING_TERMS = {"hi", "hello", "hey", "yo", "good morning", "good evening", "good afternoon"}

_COLD_TERMS = {"iced", "cold", "cold brew", "chilled"}
_HOT_TERMS = {"hot", "warm", "steaming"}

_INTENT_ORDER = ("greeting", "menu_question", "recommendation")


def _has_any(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    for term in terms:
        if term in lowered:
            return True
    return False


def analyze_query(
    query: str,
    latest_message: str = "",
) -> QueryAnalysis:
    """Analyze the current user message.

    ``latest_message`` — if provided — is the newest user turn; ``query`` may
    be a refined (rewritten) query from the evaluate loop. Both are looked at
    for term detection so refinement never loses the original intent.
    """
    combined = (query + " " + latest_message).strip() or query
    lowered = combined.lower()

    is_greeting = _has_any(lowered, _GREETING_TERMS) and len(lowered.strip()) < 40
    is_menu_question = _has_any(lowered, _MENU_INTENT_TERMS)

    if is_greeting and not is_menu_question:
        intent = "greeting"
        needs_retrieval = False
    elif is_menu_question:
        intent = "menu_question"
        needs_retrieval = True
    else:
        intent = "chitchat"
        needs_retrieval = False

    # Search terms: drop filler words, keep meaningful tokens, add menu idioms.
    tokens = re.findall(r"[a-z]+(?:\s[a-z]+)?", lowered)
    stopwords = {
        "a", "an", "the", "and", "or", "of", "for", "to", "me", "i", "i'd",
        "is", "what", "which", "with", "without", "my", "some", "something",
        "recommend", "recommendation", "get", "want", "would", "nice", "like",
        "prefer", "usually", "how", "much", "do", "you", "have", "on",
    }
    search_terms = []
    seen = set()
    for token in tokens:
        key = token.strip()
        if key and key not in stopwords and key not in seen:
            seen.add(key)
            search_terms.append(key)
    search_terms = search_terms[:6]

    if not search_terms and is_menu_question:
        search_terms = ["menu"]

    # Metadata/topic hints for filtering.
    topic = None
    if _has_any(lowered, _COLD_TERMS):
        topic = "iced"
    elif _has_any(lowered, _HOT_TERMS):
        topic = "hot"

    filters_kwargs: dict = {}
    if topic:
        filters_kwargs["topic"] = topic

    return QueryAnalysis(
        intent=intent,
        needs_retrieval=needs_retrieval,
        search_terms=search_terms,
        filters=filters_kwargs or None,
    )


def filters_from_analysis(analysis: QueryAnalysis) -> RetrievalFilter | None:
    """Translate analysis filters into a RetrievalFilter."""
    raw_filters = analysis.get("filters") or {}
    if not raw_filters:
        return None
    return RetrievalFilter(**raw_filters)