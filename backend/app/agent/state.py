"""Agent state model.

This is the shared, typed state that every node in the agent graph reads from
and writes to. The agent ends with a clean ``answer`` plus metadata — the API
layer maps this to the public chat response, never exposing raw graph state.
"""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.rag.models import Evidence, RetrievedChunk
from app.rag.retriever import EvidenceVerdict


class QueryAnalysis(TypedDict, total=False):
    """Structured analysis of the user's current message."""

    intent: str  # "greeting" | "menu_question" | "recommendation" | "chitchat"
    needs_retrieval: bool
    search_terms: list[str]
    filters: dict  # serialized RetrievalFilter kwargs


class AgentState(TypedDict):
    """Full state flowing through the agent graph."""

    # Conversation messages (role/content dicts), oldest to newest.
    messages: Annotated[list[dict], operator.add]

    # The query this turn operates on. Starts as the user's latest message and
    # may be refined by the evaluate/refine loop.
    query: str
    query_analysis: QueryAnalysis

    # Retrieval plan + candidates.
    filters: dict | None
    candidates: list[RetrievedChunk]
    retrieval_status: str | None  # "ok" | "empty" | "unavailable"
    evidence: Evidence | None
    evidence_verdict: EvidenceVerdict | None

    # Generation.
    answer: str | None
    citations: list[str]

    # Loop control. Bounded so a low-quality retrieval cannot spin forever.
    attempt_count: int
    max_attempts: int

    # Metadata for the API layer.
    used_retrieval: bool
    retrieval_count: int
    finished: bool


def initial_state(messages: list[dict], max_attempts: int = 2) -> AgentState:
    """Seed agent state from the API request (typed dict)."""
    return AgentState(
        messages=messages,
        query=messages[-1]["content"] if messages else "",
        query_analysis={"intent": "chitchat", "needs_retrieval": False},
        filters=None,
        candidates=[],
        retrieval_status=None,
        evidence=None,
        evidence_verdict=None,
        answer=None,
        citations=[],
        attempt_count=0,
        max_attempts=max_attempts,
        used_retrieval=False,
        retrieval_count=0,
        finished=False,
    )