"""Deterministic evaluators.

Each case produces a set of metric verdicts (``True``/``False`` plus a human
reason). Verdicts are bucketed into scoring categories (see ``metrics.py``).

Everything here inspects the *real* run: the executed tool trace recorded by
the chat service, the final answer, and the fixture services' call logs. The
LLM judge (live mode) lives separately and yields the same metric names it can
judge.
"""
from __future__ import annotations

import re

from evals.dataset import Case
from evals.fixtures import assert_fixture_isolation

NO_RESULT_MARKERS = (
    "couldn't find",
    "not on the menu",
    "don't carry",
    "nothing matching",
)


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip()


def extract_menu_claims(answer: str) -> list[tuple[str, str]]:
    """Extract ``(name, price)`` claims like ``the Cafe Latte, priced at 250``."""
    claims: list[tuple[str, str]] = []
    pattern = re.compile(
        r"the\s+([A-Z][A-Za-z'& ]*?)\s*,?\s+priced at\s+(\d+)"
    )
    for m in pattern.finditer(answer or ""):
        claims.append((normalize_name(m.group(1)), m.group(2)))
    return claims


def _search_names(results: list[str]) -> set[str]:
    names: set[str] = set()
    for content in results:
        for m in re.finditer(r"(?:^|\n)\d+\.\s+(.+?)\s+\(", content or ""):
            names.add(normalize_name(m.group(1)))
    return names


def _search_name_price(results: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for content in results:
        for m in re.finditer(
            r"(?:^|\n)\d+\.\s+(.+?)\s+\(.+?\)\s+\|\s+price\s+(\S+)", content or ""
        ):
            mapping[normalize_name(m.group(1))] = m.group(2)
    return mapping


def _conversion_amounts(results: list[str]) -> list[str]:
    """Extract only the converted amount from ``convert_currency`` output.

    The tool line is ``100 USD = 8300.00 INR (exchange rate: 1 USD = 83.0 ...)``.
    We only assert the *converted amount* (8300.00) lands in the answer; the
    reference rate need not be repeated.
    """
    amounts = []
    for content in results:
        m = re.match(r"[\d.]+ [A-Z]{3} = ([\d.]+) [A-Z]{3}", content or "")
        if m:
            amounts.append(m.group(1))
    return amounts


def _contains_no_result(answer: str) -> bool:
    lowered = (answer or "").lower()
    return any(marker in lowered for marker in NO_RESULT_MARKERS)


def _resolve_item(name: str, menu_by_name: dict[str, dict]) -> dict | None:
    exact = menu_by_name.get(name)
    if exact is not None:
        return exact
    lowered = {normalize_name(k).lower(): v for k, v in menu_by_name.items()}
    return lowered.get(name.lower())


def _check_constraints(item: dict, constraints: dict) -> list[str]:
    """Check the recommended item satisfies the case's hard/negative constraints."""
    problems: list[str] = []
    for key, value in (constraints or {}).items():
        if key == "max_price":
            try:
                if not (float(item.get("price", 0)) <= float(value)):
                    problems.append(f"price {item.get('price')} > max_price {value}")
            except (TypeError, ValueError):
                problems.append(f"unparseable item price {item.get('price')}")
        elif key == "sweetness_in":
            if item.get("sweetness") not in value:
                problems.append(
                    f"sweetness {item.get('sweetness')} not in allowed {value}"
                )
        elif key == "dietary":
            if value not in (item.get("dietary") or []):
                problems.append(f"dietary '{value}' absent from {item.get('dietary')}")
        elif key == "dietary_in":
            if not any(v in (item.get("dietary") or []) for v in value):
                problems.append(f"no dietary from {value} present in {item.get('dietary')}")
        else:
            if str(item.get(key)) != str(value):
                problems.append(f"{key}={item.get(key)} but expected {value}")
    return problems


def evaluate_case(case: Case, run, menu_by_name: dict[str, dict]) -> dict:
    """Return ``{"metrics": {...,}, "reasons": [...]}`` for one case run."""
    trace = run.trace or []
    answer = run.answer or ""
    called = {step.get("tool") for step in trace}
    search_results = [step.get("result") for step in trace if step.get("tool") == "search_menu"]
    search_names = _search_names(search_results)
    search_name_price = _search_name_price(search_results)

    metrics: dict[str, bool] = {}
    reasons: list[str] = []

    # ── tool selection -------------------------------------------------- #
    missing = [t for t in case.expected_tools if t not in called]
    metrics["tool_selection"] = not missing
    if missing:
        reasons.append(f"expected tool(s) {missing} never called; called {sorted(called)}")

    # ── retrieval relevance / recall ------------------------------------ #
    expected_items = set(normalize_name(n) for n in case.expected_item_names)
    found_items = expected_items & search_names
    if expected_items:
        metrics["retrieval_relevance"] = bool(found_items)
        recall = len(found_items) / len(expected_items)
        if recall < 1.0:
            missing_items = sorted(expected_items - found_items)
            reasons.append(f"retrieval missed {missing_items}; got {sorted(search_names) or 'no results'}")
    else:
        metrics["retrieval_relevance"] = None
        recall = None
    # recall is reported raw via its own key (float or None)
    metrics["retrieval_recall"] = recall if recall is not None else None

    # ── excluded / negative constraints ---------------------------------- #
    excluded = set(normalize_name(n) for n in case.excluded_item_names)
    if excluded:
        leaked = sorted(excluded & search_names)
        metrics["excluded_items_absent"] = not leaked
        if leaked:
            reasons.append(f"excluded item(s) surfaced in results: {leaked}")
    else:
        metrics["excluded_items_absent"] = None

    # ── ground claims ---------------------------------------------------- #
    claims = extract_menu_claims(answer)
    grounded = True
    for name, price in claims:
        if name not in search_name_price:
            grounded = False
            reasons.append(f"claim '{name}' not present in any search_menu result")
            continue
        if search_name_price.get(name) != price:
            grounded = False
            reasons.append(
                f"claim price {price} for '{name}' differs from menu price {search_name_price.get(name)}"
            )
    metrics["groundedness"] = grounded if claims else None

    # ── faithfulness: no number/claim contradicts a tool result ---------- #
    faithful = True
    if claims:
        for name, price in claims:
            if search_name_price.get(name) != price:
                faithful = False
                reasons.append(
                    f"price claim {price} for '{name}' is not backed by any tool result"
                )
    # currency checks
    if any(step.get("tool") == "convert_currency" for step in trace):
        conv_results = [step.get("result") for step in trace if step.get("tool") == "convert_currency"]
        known_amounts = _conversion_amounts(conv_results)
        for amount in known_amounts:
            if amount not in answer:
                faithful = False
                reasons.append(
                    f"answer omits conversion result {amount} that the currency tool returned"
                )
    metrics["faithfulness"] = faithful

    # ── no-result handling ------------------------------------------------ #
    if case.expected_no_result or case.category in ("no_result",):
        no_result_ok = _contains_no_result(answer) and not claims
        metrics["no_result_correctness"] = no_result_ok
        if not no_result_ok:
            reasons.append(
                f"expected an honest no-result answer, got claim(s)={claims}, "
                f"no-result markers={_contains_no_result(answer)}"
            )
    else:
        metrics["no_result_correctness"] = None

    # ── answer correctness -------------------------------------------------- #
    correct = True
    if not run.ok:
        correct = False
        reasons.append(f"run failed: {run.error or 'unknown error'}")
    elif not answer.strip():
        correct = False
        reasons.append("answer was empty")
    elif case.expected_no_result:
        correct = no_result_ok
    elif case.expected_refusal:
        correct = bool(answer.strip())  # a refusal is a valid answer
    elif case.expected_item_names:
        # any extracted claim must resolve to a real menu item
        resolved_ok = False
        for name, _ in claims:
            if _resolve_item(name, menu_by_name) is not None:
                resolved_ok = True
                break
        if not resolved_ok:
            correct = False
            reasons.append(f"answer held no resolvable menu item (claims={claims})")
    metrics["answer_correctness"] = correct

    # ── personalization --------------------------------------------------- #
    if case.category == "preferences" or case.expected_personalization_used:
        fixture_vals = _preference_values(case)
        answer_low = answer.lower()
        if case.expected_personalization_used:
            referenced = any(v and v.lower() in answer_low for v in fixture_vals)
            used = bool(getattr(run, "used_preferences", False))
            metrics["preference_usage"] = bool(used and referenced)
            if not used or not referenced:
                reasons.append(
                    f"personalization expected but used={used}, "
                    f"preference value in answer={referenced} (values={fixture_vals})"
                )
        else:
            leaked = [v for v in fixture_vals if v and v.lower() in answer_low]
            metrics["preference_usage"] = not leaked
            if leaked:
                reasons.append(f"switched-off preferences leaked into answer: {leaked}")
    else:
        metrics["preference_usage"] = None

    # ── security isolation ------------------------------------------------ #
    if case.category == "security":
        violations = assert_fixture_isolation(run.uid, run.services or {})
        metrics["security_isolation"] = not violations
        if violations:
            reasons.append("; ".join(violations))
    else:
        metrics["security_isolation"] = None

    filtered = {k: v for k, v in metrics.items() if v is not None}
    return {"metrics": filtered, "reasons": reasons}


def _preference_values(case: Case) -> list[str]:
    """Stored preference values that must (not) appear in the answer."""
    fixtures = case.fixtures or {}
    doc = fixtures.get("preferences") or {}
    values: list[str] = []
    coffee = doc.get("coffee") or {}
    for key in ("favoriteDrink", "milkPreference", "sweetness"):
        value = coffee.get(key)
        if value:
            values.append(str(value))
    temperature = coffee.get("temperature")
    # "either" is the schema default, not an actual stated preference.
    if temperature and temperature != "either":
        values.append(str(temperature))
    return values