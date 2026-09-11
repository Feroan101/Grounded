"""Evaluation runner.

Orchestrates patching, the real production call, deterministic evaluation, and
reporting.  The runner deliberately reuses the production ``ChatService``,
``MenuService`` filtering, and all real tools — only the model and the
external data providers are swapped for deterministic fixtures.
"""
from __future__ import annotations

import contextlib
import statistics
import time
from unittest.mock import patch

import app.services.chat_service as chat_service_mod
import app.services.currency_tools as currency_tools_mod
import app.services.menu_service as menu_service_mod
import app.services.preference_tools as preference_tools_mod
import app.services.conversation_history_tools as conversation_history_tools_mod
import app.services.order_history_tools as order_history_tools_mod

from evals import config
from evals.config import FIXED_CURRENCY_RATES, DEFAULT_UID
from evals.dataset import CATEGORIES, Case, build_cases
from evals.evaluators import evaluate_case
from evals.fixtures import (
    FakeConversationHistoryService,
    FakeOrderHistoryService,
    FakePreferencesService,
    FixedRateCurrencyService,
    build_menu_lookup,
    load_menu_fixture,
    load_menu_from_firestore,
    patch_menu_service,
)
from evals.metrics import RunSummary, aggregate_case_metrics, compute_summary
from evals.mock_llm import ScriptedLLM
from evals.report import write_results


def run(
    *,
    include_categories: list[str] | None = None,
    include_cases: list[str] | None = None,
    mode: str = "deterministic",
    menu_source: str = "firestore",
) -> RunSummary:
    """Build the dataset, evaluate, print a summary, write results, return."""
    all_cases = build_cases()
    cases = _filter_cases(all_cases, include_categories, include_cases)
    items = load_menu_fixture() if menu_source != "firestore" else load_menu_from_firestore()
    if menu_source != "firestore":
        patch_menu_service(menu_service_mod, items)
    menu_by_id = build_menu_lookup(items)
    from evals.evaluators import normalize_name

    menu_by_name = {normalize_name(i.get("name", "")): i for i in items if i.get("name")}
    results: list[dict] = []
    print(f"\nRunning {len(cases)} case(s) [{mode}] menu_source={menu_source}...")
    for i, case in enumerate(cases, start=1):
        print(f"  {i:>3}/{len(cases)}  {case.id:<28}  {case.category:<22}", end="", flush=True)
        case_result = _run_case(case, mode, menu_by_name)
        verdict = "FAIL" if case_result.get("fail") else "PASS"
        if case.expect_fail:
            verdict = "AUDIT_OK" if case_result.get("fail") else "AUDIT_BROKEN"
        print(verdict)
        results.append(case_result)
    summary = compute_summary(results)
    write_results(summary, results, mode, menu_source, len(cases), [c.id for c in cases])
    return summary


# --------------------------------------------------------------------------- #
# Case execution
# --------------------------------------------------------------------------- #

@contextlib.contextmanager
def _setup_patches(case: Case, mode: str, menu_by_name: dict[str, dict]):
    """Yields ``{"llm": llm, "fixed_currency": fcsvc, ...}`` for the case."""
    llm = ScriptedLLM(case)
    fixed_currency = FixedRateCurrencyService(FIXED_CURRENCY_RATES)
    services: dict = {}

    prefs_doc = (case.fixtures or {}).get("preferences") or None
    orders = (case.fixtures or {}).get("orders") or None
    history = (case.fixtures or {}).get("history") or None

    pref_svc = FakePreferencesService(prefs_doc or {}, uid_whitelist={DEFAULT_UID})
    order_svc = FakeOrderHistoryService(orders or [])
    hist_svc = FakeConversationHistoryService(history or [])
    services["preferences"] = pref_svc
    services["orders"] = order_svc
    services["history"] = hist_svc

    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(chat_service_mod, "get_llm", lambda: llm))
        stack.enter_context(patch.object(preference_tools_mod, "get_preferences_service", lambda: pref_svc))
        stack.enter_context(patch.object(conversation_history_tools_mod, "get_preferences_service", lambda: pref_svc))
        stack.enter_context(patch.object(conversation_history_tools_mod, "get_conversation_history_service", lambda: hist_svc))
        stack.enter_context(patch.object(order_history_tools_mod, "get_order_history_service", lambda: order_svc))
        stack.enter_context(patch.object(currency_tools_mod, "get_currency_service", lambda: fixed_currency))
        if mode == "deterministic":
            # Avoid any dependence on ambient Qdrant/embedding configuration in
            # deterministic runs: the structured/search fallback is the
            # validated path. Live mode keeps the real configuration.
            stack.enter_context(patch.object(menu_service_mod, "is_semantic_menu_configured", lambda: False))
        yield {"llm": llm, "fixed_currency": fixed_currency, "services": services}


def _run_case(case: Case, mode: str, menu_by_name: dict[str, dict]) -> dict:
    start = time.perf_counter()
    error: str | None = None
    result_answer = ""
    run_trace = []
    services: dict = {}
    uid = DEFAULT_UID
    used_preferences = used_conversation_history = used_order_history = False
    latency_ms = 0
    try:
        with _setup_patches(case, mode, menu_by_name) as ctx:
            services = ctx["services"]
            svc = chat_service_mod.get_chat_service()
            req = chat_service_mod.ChatRequest(
                messages=[{"role": "user", "content": case.question}],
                conversation_id="eval-conv",
            )
            res = svc.process(req, {"uid": uid})
            result_answer = res.answer
            run_trace = res.trace
            latency_ms = res.latency_ms
            used_preferences = getattr(res.context, "used_preferences", False)
            used_conversation_history = getattr(res.context, "used_conversation_history", False)
            used_order_history = getattr(res.context, "used_order_history", False)
            if res.error:
                error = res.error
    except Exception as exc:  # noqa: BLE001 — safety net for the harness
        error = str(exc)
        latency_ms = round((time.perf_counter() - start) * 1000)

    metrics_eval = evaluate_case(
        case,
        type("Run", (), {"trace": run_trace, "answer": result_answer, "error": error, "ok": not error, "services": services, "uid": uid, "used_preferences": used_preferences, "used_conversation_history": used_conversation_history, "used_order_history": used_order_history, "latency_ms": latency_ms})(),
        menu_by_name,
    )
    metrics = aggregate_case_metrics(metrics_eval["metrics"])
    failed = any(v is False for v in metrics.values())
    return {
        "case": case,
        "metrics": metrics,
        "reasons": metrics_eval["reasons"],
        "answer": result_answer,
        "latency_ms": latency_ms,
        "trace": run_trace,
        "fail": failed,
        "error": error,
        "services": services,
        "used_preferences": used_preferences,
        "used_conversation_history": used_conversation_history,
        "used_order_history": used_order_history,
        "pass": not failed,
    }


# --------------------------------------------------------------------------- #
# Dataset filtering
# --------------------------------------------------------------------------- #

def _filter_cases(
    cases: list[Case],
    categories: list[str] | None,
    ids: list[str] | None,
) -> list[Case]:
    result = cases
    if categories:
        cat_set = {c.lower() for c in categories}
        result = [c for c in result if c.category.lower() in cat_set]
    if ids:
        id_set = set(ids)
        result = [c for c in result if c.id in id_set]
    return result