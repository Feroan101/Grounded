"""Report writer.

Produces ``latest.json``, appends to ``evaluation_history.json``, renders a
readable PNG bar chart of per-category scores, and prints a terminal summary.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from evals import config
from evals.metrics import RunSummary, category_payload, format_failure
from evals.pngchart import render_bar_chart

_CSV_LABELS = {
    "Retrieval": "RETRIEVAL",
    "Constraints": "CONSTRAINTS",
    "Tool selection": "TOOL SELECTION",
    "Groundedness": "GROUNDEDNESS",
    "Faithfulness": "FAITHFULNESS",
    "Answer correctness": "ANSWER CORRECTNESS",
    "Personalization": "PERSONALIZATION",
    "No-result handling": "NO-RESULT",
    "Security": "SECURITY",
}


def write_results(
    summary: RunSummary,
    run_results: list[dict],
    mode: str,
    menu_source: str,
    cases_total: int,
    case_ids: list[str],
) -> None:
    """Write ``latest.json``, append to history, render bar chart, print to stdout."""
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    latest = {
        "eval_version": config.EVAL_VERSION,
        "timestamp": now,
        "mode": mode,
        "menu_source": menu_source,
        "counts": {"cases": cases_total, "passed": summary.passed, "failed": summary.failed, "audits": summary.audit_expected_fail},
        "overall_score": round(summary.overall, 1),
        "security_gate": summary.security_gate,
        "categories": category_payload(summary),
        "failures": summary.failures,
        "audit_unexpected_fail": summary.audit_unexpected,
    }
    _write_json(config.RESULTS_DIR / "latest.json", latest)
    _append_history(config.RESULTS_DIR / "evaluation_history.json", latest)
    chart_items = [
        (_CSV_LABELS.get(cat["name"], cat["name"].upper()), cat["score"])
        for cat in category_payload(summary)
    ]
    render_bar_chart(
        config.RESULTS_DIR / "evaluation_latest.png",
        chart_items,
        "GROUNDING & AGENT RAG REPORT",
        f"{cases_total} cases  |  {mode}  |  {menu_source}",
        footer="Score = per-category pass rate (deterministic)",
    )
    _print_summary(summary, latest, run_results)


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)


def _append_history(path: Path, entry: dict) -> None:
    history: list[dict] = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            history = []
    history.append(entry)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=1, ensure_ascii=False)


def _print_summary(summary: RunSummary, latest: dict, run_results: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("GROUNDED EVALUATION REPORT")
    print("=" * 72)
    print(f"  Cases: {summary.cases_total}  |  Passed: {summary.passed}  |  Failed: {summary.failed}  |  Audits: {summary.audit_expected_fail}")
    print(f"  Overall score: {summary.overall:.1f}%  |  Security gate: {summary.security_gate}")
    if summary.audit_unexpected:
        print(f"  AUDIT UNEXPECTED PASS: {summary.audit_unexpected}")
    print("-" * 72)
    for cat in category_payload(summary):
        print(f"  {cat['name']:<22}  {cat['score']:5.1f}%  ({cat['passed']}/{cat['total']})")
    if summary.failures:
        print("-" * 72)
        print("FAILURES:")
        for i, failure in enumerate(summary.failures, start=1):
            reasons = "; ".join(str(r) for r in (failure.get("reasons") or [])[:3])
            print(f"  {i}. [{failure['id']}] {failure['category']}: {failure['question'][:60]}")
            if reasons:
                print(f"     -> {reasons[:160]}")
    print("=" * 72 + "\n")