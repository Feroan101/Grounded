"""Score aggregation.

A run produces per-case metric verdicts; this module buckets them into the
nine scoring categories, computes per-category and overall scores, and flips
the security gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Metric -> scoring category (stable order).
SCORING_CATEGORIES = [
    ("Retrieval", ["retrieval_relevance", "retrieval_recall"]),
    ("Constraints", ["constraint_adherence", "excluded_items_absent", "retrieval_relevance"]),
    ("Tool selection", ["tool_selection"]),
    ("Groundedness", ["groundedness"]),
    ("Faithfulness", ["faithfulness"]),
    ("Answer correctness", ["answer_correctness"]),
    ("Personalization", ["preference_usage"]),
    ("No-result handling", ["no_result_correctness"]),
    ("Security", ["security_isolation"]),
]

_KEYS = [key for _, keys in SCORING_CATEGORIES for key in keys]


@dataclass
class CategoryScore:
    name: str
    passed: int = 0
    total: int = 0

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "total": self.total,
            "score": round(self.score * 100, 1),
        }


@dataclass
class RunSummary:
    cases_total: int = 0
    passed: int = 0
    failed: int = 0
    audit_expected_fail: int = 0
    audit_unexpected: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    categories: dict[str, CategoryScore] = field(default_factory=dict)
    security_gate: str = "PASSED"
    overall: float = 0.0


def aggregate_case_metrics(metrics: dict[str, bool]) -> dict[str, bool]:
    """Only keep metric keys the scoring categories understand."""
    return {k: v for k, v in metrics.items() if k in _KEYS}


def _case_violations(metrics: dict[str, bool], category_key: str) -> list[str]:
    keys = dict(SCORING_CATEGORIES)[category_key]
    return [key for key in keys if key in metrics and metrics[key] is False]


def compute_summary(results: list[dict]) -> RunSummary:
    """Collapse evaluated case results into a summary.

    ``results`` is a list of dicts shaped by the runner:
    ``{"case", "metrics", "reasons", "pass", "error", "latency_ms", ...}``.
    """
    summary = RunSummary()
    categories = {name: CategoryScore(name) for name, _ in SCORING_CATEGORIES}
    performance_names = [name for name, _ in SCORING_CATEGORIES if name != "Security"]
    performance_raw: list[float] = []

    for result in results:
        case = result["case"]
        summary.cases_total += 1
        failed_metrics = {k: v for k, v in result["metrics"].items() if v is False}

        if case.expect_fail:
            summary.audit_expected_fail += 1
            # An audit case that failed to fail means the harness is broken.
            if not failed_metrics:
                summary.audit_unexpected.append(case.id)
                summary.failed += 1
        else:
            if failed_metrics:
                summary.failed += 1
                summary.failures.append(format_failure(result))

        for name, keys in SCORING_CATEGORIES:
            present = [k for k in keys if k in result["metrics"]]
            if not present:
                continue
            cat = categories[name]
            for key in keys:
                if key in result["metrics"]:
                    cat.total += 1
                    if result["metrics"][key]:
                        cat.passed += 1

    summary.categories = categories
    # Security gate
    security = categories["Security"]
    if security.total and security.passed < security.total:
        summary.security_gate = "FAILED"

    # Overall: mean of the non-security performance categories (each scorer).
    for name in performance_names:
        cat = categories[name]
        if cat.total:
            performance_raw.append(cat.score)
    summary.overall = (sum(performance_raw) / len(performance_raw) * 100) if performance_raw else 0.0
    summary.passed = summary.cases_total - summary.failed
    return summary


def format_failure(result: dict) -> dict:
    case = result["case"]
    reasons = result.get("reasons") or []
    if result.get("error"):
        reasons = reasons + [result["error"]]
    return {
        "id": case.id,
        "category": case.category,
        "question": case.question,
        "expected": f"tools={case.expected_tools} items={case.expected_item_names}",
        "actual": result.get("answer") or "",
        "reasons": reasons[:5],
    }


def category_payload(summary: RunSummary) -> list[dict]:
    return [cat.as_dict() for cat in summary.categories.values()]