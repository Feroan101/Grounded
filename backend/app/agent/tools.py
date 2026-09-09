"""Agent tools.

Tools are only usable against real infrastructure. Phase 1 has no vector store
or embedding provider configured, so ``get_agent_tools()`` returns an empty
list — no hard-coded tools, no canned answers.

The tool function signatures below define the interface the agent will expose
once retrieval exists. LangChain tools can be generated from these at the same
time, through a single registry entry, without touching the graph nodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    """Metadata for a knowledge-base tool available to the agent."""

    name: str
    description: str
    args_schema: dict = field(default_factory=dict)


def _knowledge_tool_specs() -> list[ToolSpec]:
    """Specs for knowledge tools (usable once RAG is configured)."""
    return [
        ToolSpec(
            name="search_knowledge",
            description=(
                "Search the coffee shop knowledge base for information about "
                "menu items, ingredients, prices, milk options, sizes, and "
                "customizations. Use this when the customer asks about the menu."
            ),
            args_schema={
                "query": {"type": "string", "required": True},
            },
        ),
        ToolSpec(
            name="search_topic",
            description=(
                "Search a knowledge-base topic (e.g. 'iced drinks', milk "
                "options, brewing) and apply metadata filters."
            ),
            args_schema={
                "query": {"type": "string", "required": True},
                "topic": {"type": "string", "required": True},
            },
        ),
        ToolSpec(
            name="expand_context",
            description=(
                "Expand a retrieved child chunk to its parent block for fuller "
                "context around a passing mention."
            ),
            args_schema={
                "chunk_id": {"type": "string", "required": True},
            },
        ),
        ToolSpec(
            name="get_source",
            description=(
                "Return the original source (document, section, heading) for a "
                "retrieved chunk for citation."
            ),
            args_schema={
                "chunk_id": {"type": "string", "required": True},
            },
        ),
    ]


def get_tool_specs() -> list[ToolSpec]:
    """Return the tool specs currently usable.

    With no RAG infrastructure configured, no tools are returned. Once a
    vector store and embedder exist, these become real tools.
    """
    if not _rag_available():
        return []
    return _knowledge_tool_specs()


def _rag_available() -> bool:
    from app.rag.retriever import is_retrieval_configured

    return is_retrieval_configured()


# Exposed for graph/agent construction in later phases.
KNOWLEDGE_TOOL_SPECS = _knowledge_tool_specs()