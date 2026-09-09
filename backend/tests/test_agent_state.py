"""Agent state initialization tests."""
from app.agent.analysis import analyze_query, filters_from_analysis
from app.agent.graph import build_agent
from app.agent.state import initial_state


class _FakeModel:
    def invoke(self, messages):
        return _FakeOutput("Hello! How can I help?")


class _FakeOutput:
    def __init__(self, content):
        self.content = content


def _patch_llm(monkeypatch):
    import app.ai.llm as llm_module

    monkeypatch.setattr(llm_module, "get_llm", lambda: _FakeModel())


def test_initial_state_seeds_query_from_last_user_message():
    state = initial_state(
        [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "second"},
        ]
    )
    assert state["query"] == "second"
    assert state["max_attempts"] == 2
    assert state["attempt_count"] == 0
    assert state["used_retrieval"] is False
    assert state["finished"] is False


def test_initial_state_never_trusts_client():
    # There is no place for a client-supplied identity in agent state.
    state = initial_state([{"role": "user", "content": "hi"}])
    assert "uid" not in state
    assert "user_id" not in state


def test_graph_compiles():
    graph = build_agent()
    assert graph is not None


def test_analyze_query_menu_question():
    analysis = analyze_query("Do you have iced lattes on the menu?")
    assert analysis["intent"] == "menu_question"
    assert analysis["needs_retrieval"] is True
    assert any("lattes" in t for t in analysis["search_terms"])


def test_analyze_query_detects_iced_filter():
    analysis = analyze_query("something cold and not too sweet")
    assert analysis["filters"] == {"topic": "iced"}


def test_analyze_query_greeting():
    analysis = analyze_query("hello there")
    assert analysis["intent"] == "greeting"
    assert analysis["needs_retrieval"] is False


def test_filters_from_analysis():
    analysis = analyze_query("hot drinks")
    rfilter = filters_from_analysis(analysis)
    assert rfilter is not None
    assert rfilter.topic == "hot"

    no_filter = filters_from_analysis(analyze_query("hello"))
    assert no_filter is None


def test_menu_query_without_rag_yields_honest_no_retrieval_answer():
    """The graph must produce an honest 'unavailable' answer when RAG is not
    configured — not a made-up menu answer."""
    graph = build_agent()
    result = graph.invoke(
        initial_state([{"role": "user", "content": "what drinks do you have?"}])
    )
    assert result["query_analysis"]["needs_retrieval"] is True
    assert result.get("retrieval_status") == "unavailable"
    assert result["answer"] and "look that up" in result["answer"]


def test_greeting_skips_retrieval(monkeypatch):
    """A greeting should never touch the retrieve path."""
    _patch_llm(monkeypatch)
    graph = build_agent()
    result = graph.invoke(initial_state([{"role": "user", "content": "hi"}]))
    assert result["query_analysis"]["intent"] == "greeting"
    assert result.get("retrieval_status") == "skipped"
    assert result["used_retrieval"] is False
    assert result["answer"] == "Hello! How can I help?"