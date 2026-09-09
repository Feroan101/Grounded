"""Agent graph (LangGraph).

Phase 1 establishes a real, branchy graph::

    START
      -> analyze_query_node
      -> decide_retrieval_node  (genuine branch)
            /need retrieval/       /no retrieval/
      retrieve_node             skip
      -> evaluate_evidence_node  (genuine branch)
            /sufficient/           /insufficient + attempts left/
      generate_node              refine_query_node -> back to retrieve_node
      -> END

Conditional edges are driven by real state, not a fixed sequence. The graph is
used by the chat service; raw graph state is never returned to the frontend.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    analyze_query_node,
    decide_retrieval_node,
    evaluate_evidence_node,
    generate_node,
    refine_query_node,
    retrieve_node,
)
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def _route_retrieval(state: AgentState) -> str:
    if state.get("used_retrieval") and state.get("query_analysis", {}).get("needs_retrieval"):
        return "retrieve"
    return "skip"


def _route_evidence(state: AgentState) -> str:
    status = state.get("retrieval_status")
    if status in ("unavailable", "skipped"):
        return "generate"
    verdict = state.get("evidence_verdict")
    if not verdict or not verdict.sufficient:
        if state.get("attempt_count", 0) < state.get("max_attempts", 2):
            return "refine_and_retrieve"
        return "generate"
    return "generate"


def build_agent() -> StateGraph:
    """Compile the grounded agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("analyze", analyze_query_node)
    builder.add_node("decide", decide_retrieval_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("skip", lambda state: {"used_retrieval": False, "retrieval_status": "skipped"})
    builder.add_node("evaluate", evaluate_evidence_node)
    builder.add_node("refine_and_retrieve", refine_query_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "decide")
    builder.add_conditional_edges(
        "decide",
        _route_retrieval,
        {
            "retrieve": "retrieve",
            "skip": "skip",
        },
    )
    builder.add_edge("retrieve", "evaluate")
    builder.add_edge("skip", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        _route_evidence,
        {
            "generate": "generate",
            "refine_and_retrieve": "refine_and_retrieve",
        },
    )
    builder.add_edge("refine_and_retrieve", "retrieve")
    builder.add_edge("generate", END)

    return builder.compile()


_agent = None


def get_agent():
    """Return the compiled agent graph (cached)."""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def reset_agent() -> None:
    """Drop the cached agent (for tests / config changes)."""
    global _agent
    _agent = None