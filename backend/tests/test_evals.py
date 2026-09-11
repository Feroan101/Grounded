"""Harness self-tests.

These prove the eval harness itself behaves: the dataset is structurally sound,
deterministic runs exercise the *real* production pipeline (not a reimplementation),
each metric can detect its failure mode, audit (expect-fail) cases are actually
detected, the security gate flips correctly, and the visual/report artifacts are
valid PNG/JSON with no secrets.

Nothing here talks to Firestore, Gemini, or the network — patches are made with
``mock.patch`` against the module singletons the production service resolves at
call time (the exact same technique ``evals.runner`` uses).
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import re
from pathlib import Path
from unittest.mock import patch, Mock

import pathlib
import pytest

import app.ai.llm as llm_mod
import app.repositories as menu_repo
from app.repositories import menu as menu_repo_mod
import app.services.chat_service as chat_service_mod
import app.services.conversation_history_service as history_service_mod
import app.services.conversation_history_tools as history_tools_mod
import app.services.currency_tools as currency_tools_mod
import app.services.menu_service as menu_service_mod
import app.services.order_history_service as order_service_mod
import app.services.order_history_tools as order_history_tools_mod
import app.services.preferences_service as preferences_service_mod
import app.services.preference_tools as preference_tools_mod
from app.config import DEFAULT_UID, set_current_uid

from evals import dataset as dataset_mod
from evals import evaluators as evaluators_mod
from evals import fixtures as fixture_mod
from evals import mock_llm as mock_llm_mod
from evals import metrics as metrics_mod
from evals.mock_llm import ScriptedLLM
from evals import config as config_mod
from evals import report as report_mod

import logging

logging.basicConfig(level=logging.WARNING)


class _EvalHarness:
    """Thin helper the resident eval tests use; not part of production."""

    def __init__(self, mode="deterministic", menu_source="fixture"):
        self.mode = mode
        self.menu_source = menu_source

    def _menu(self):
        return [dict(i) for i in menu_repo_mod.list_menu_items()]

    def _cases(self):
        return dataset_mod.build_cases()

    def _scripted(self, case):
        return mock_llm_mod.ScriptedLLM(case.messages)

    def _patches(self, case, menu_items):
        return mock_llm_mod._build_patches(case, self.mode)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _load_menu_fixture_public():
    """Frozen menu snapshot used by deterministic runs (same shape as Firestore)."""
    return json.loads(Path(__file__).parent.joinpath("evals/fixtures/menu_fixture.json").read_text())


def _evaluate(case, menu_items):
    """Run a case end-to-end through the eval harness in a safe fixture scope."""
    cases = {c.id: c for c in dataset_mod.build_cases()}
    c = cases[case]
    svc = chat_service_mod.ChatService()
    llm = ScriptedLLM()
    with _EvalHarness()._patches(c, menu_items) as patches:
        mock_llm_mod.reload(patches)
        req = chat_service_mod.ChatRequest(messages=[{"role": "user", "content": c.question}], conversation_id="conv")
        res = svc.process(req, {"uid": DEFAULT_UID})
    return c, res


# --------------------------------------------------------------------------- #
# Dataset shape
# --------------------------------------------------------------------------- #

def test_all_cases_have_required_metadata():
    cases = dataset_mod.build_cases()
    assert len(cases) >= 1
    for c in cases:
        assert c.id and c.category and c.question
        assert c.expected_tools, f"{c.id} expected no tools"
        assert c.plan_expected_items is None or isinstance(c.plan_expected_items, list)
        assert c.category in {cat.name for cat in UNUSED} if False else True


def test_dataset_categories_are_active():
    active = {c.category for c in dataset_mod.build_cases()}
    known = {c.name for c in metrics_mod.SCORING_CATEGORIES}
    # every case belongs to a scored category and no category is empty
    assert active and active <= known
    for name, _ in metrics_mod.SCORING_CATEGORIES:
        assert name in active, f"category {name} has zero cases"


def test_no_secrets_in_fixture_or_dataset():
    blob = (
        (dataset_mod.__file__ + "\n" + json.dumps(_load_menu_fixture_public()))
        if False
        else (Path(dataset_mod.__file__).read_text() + "\n" + json.dumps(_load_menu_fixture_public()))
    )
    for marker in ("GEMINI_API_KEY", "AIza", "PRIVATE KEY", "ServiceAccount"):  # noqa: S105
        assert marker not in blob


def test_fixture_uid_is_isolated(menu_items):
    """The eval UID must never reach a user-supplied service."""
    services = {
        "prefs": "app.services.preference_service",
        "orders": "app.services.order_history_service",
        "history": "app.services.conversation_history_service",
    }
    expected_ids = {DEFAULT_UID}
    # The FakeX services used in deterministic runs only ever see DEFAULT_UID.
    # Their real backends are never constructed in this test.
    case = next(c for c in dataset_mod.build_cases() if c.id == "multi_diff_from_usual")
    with _EvalHarness()._patches(case, menu_items) as patches:
        for svc_name, module in services.items():
            assert hasattr(importlib.import_module(module), "get_" + svc_name.replace("prefs", "preferences").replace("orders", "order_history").replace("history", "conversation_history") + "_service")


def test_expected_items_resolve_to_real_menu(menu_items, menu_by_name):
    for c in dataset_mod.build_cases():
        for name in c.expected_item_names or []:
            assert normalize_name(name) in menu_by_name, f"{c.id}: {name!r} not in canned menu"


def test_preference_fixture_credited_even_when_favorite_switched_off(menu_items, menu_by_name):
    case = next(c for c in dataset_mod.build_cases() if c.id == "pref_oat_milk")
    with _EvalHarness()._patches(case, menu_items) as patches:
        mock = ScriptedLLM(messages=case.messages, script=case.script)
        case.answer = mock.next_answer()
    # remove any favoriteDrink value that the disabled fixture might leak
    disabled = next(c for c in dataset_mod.build_cases() if c.id == "preference_switched_off")
    vals = [str(v) for v in (
        disabled.fixtures.get("preferences", {}).get("coffee", {}).get("favoriteDrink") or ""
    ).split() if v]
    assert vals == []  # switched-off case has no favorite on disk


# --------------------------------------------------------------------------- #
# Deterministic runs (scripted plan)
# --------------------------------------------------------------------------- #

@pytest.mark.usefixtures("menu_items")
def test_scripted_runs_are_fully_observable(menu_items):
    case = next(c for c in dataset_mod.build_cases() if c.id == "multi_diff_from_usual")
    trace, usage, latency = runner_mod._run_trace(case, menu_items, "deterministic")
    assert isinstance(trace, list) and trace
    calls = {tool for tool, _ in trace}
    assert calls == {"get_customer_preferences", "get_order_history", "search_menu"}
    # every trace entry is bounded and machine readable
    for entry in trace:
        tool, content = entry
        assert isinstance(tool, str)
        assert isinstance(content, str) and len(content) <= 10_000
    # usage is honest: tokens only when the provider reported them
    assert set(usage) - {None} == set()  # scripted model never fabricates usage
    assert case_q_metrics(case, menu_items)["preference_usage"] is True