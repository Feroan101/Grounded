"""Fixture services injected for deterministic evaluation.

These are stand-ins for the external/network-backed services the production
tools call *at call time* (via ``get_*_service()`` in the tool modules). They
must behave exactly like the real services' public interface while recording
which UID each call was scoped to, so isolation is provable.

The menu is handled separately: the real ``MenuService`` filtering logic is
kept intact and pointed at the bundled fixture snapshot (or live Firestore).
"""
from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal

from app.services.conversation_history_service import ConversationRecord
from app.services.currency_service import ConversionResult, CurrencyService
from app.services.order_history_service import OrderRecord

from evals import config


# --------------------------------------------------------------------------- #
# Preferences
# --------------------------------------------------------------------------- #

class FakePreferencesService:
    """Stores one preferences document for the eval UID and records access."""

    def __init__(self, document: dict, *, uid_whitelist: set[str]):
        self._doc = deepcopy(document or {})
        self._uid_whitelist = set(uid_whitelist)
        self.seen_uids: set[str] = set()
        self.updates: list[tuple[str, dict]] = []

    def get_preferences(self, uid: str) -> dict:
        self.seen_uids.add(uid)
        return deepcopy(self._doc)

    def update_preferences(self, uid: str, updates: dict) -> None:
        self.seen_uids.add(uid)
        self.updates.append((uid, deepcopy(updates)))
        if "coffee" in updates and isinstance(updates["coffee"], dict):
            self._doc.setdefault("coffee", {}).update(updates["coffee"])
        if "aiContext" in updates and isinstance(updates["aiContext"], dict):
            self._doc.setdefault("aiContext", {}).update(updates["aiContext"])

    def assert_isolated(self, uid: str) -> list[str]:
        return self._violations(set(uid for uid, _ in self.updates) | self.seen_uids)


class FakeConversationHistoryService:
    def __init__(self, records: list[dict]):
        self.records = [deepcopy(r) for r in (records or [])]
        self.seen_uids: set[str] = set()
        self.exclude_ids: set[str] = set()

    def get_history(self, uid: str, *, exclude_id: str | None = None) -> list[ConversationRecord]:
        self.seen_uids.add(uid)
        if exclude_id:
            self.exclude_ids.add(exclude_id)
        return [ConversationRecord(r.get("title"), r.get("date"), r.get("messages") or [])
                for r in self.records]


class FakeOrderHistoryService:
    def __init__(self, records: list[dict]):
        self.records = [deepcopy(r) for r in (records or [])]
        self.seen_uids: set[str] = set()

    def get_history(self, uid: str) -> list[OrderRecord]:
        self.seen_uids.add(uid)
        return [OrderRecord(r.get("date"), r.get("items") or [], r.get("total")) for r in self.records]


def _violations(seen: set[str], allowed: set[str]) -> list[str]:
    offenders = {u for u in seen if u not in allowed}
    if not offenders:
        return []
    return [f"service reached UID(s) {sorted(offenders)}; allowed {sorted(allowed)}"]


def assert_fixture_isolation(uid: str, services: dict) -> list[str]:
    """Return a list of isolation violations across the recorded fixtures."""
    allowed = {uid}
    violations: list[str] = []
    pref_svc = services.get("preferences")
    if pref_svc is not None:
        violations += _violations(pref_svc.seen_uids, allowed)
        violations += _violations({u for u, _ in pref_svc.updates}, allowed)
    hist_svc = services.get("history")
    if hist_svc is not None:
        violations += _violations(hist_svc.seen_uids, allowed)
    orders_svc = services.get("orders")
    if orders_svc is not None:
        violations += _violations(orders_svc.seen_uids, allowed)
    return violations


# --------------------------------------------------------------------------- #
# Currency (fixed deterministic rates)
# --------------------------------------------------------------------------- #

class FixedRateCurrencyService(CurrencyService):
    """Real validation logic + fixed rates so numeric checks are exact."""

    def __init__(self, rates: dict[tuple[str, str], str]):
        self._rates = {(src.upper(), tgt.upper()): Decimal(rate) for (src, tgt), rate in rates.items()}

    def convert(self, amount, from_currency: str, to_currency: str) -> ConversionResult:
        base = self._normalise_code(from_currency, "from_currency")
        quote = self._normalise_code(to_currency, "to_currency")
        dec_amount = self._parse_amount(amount)
        if base == quote:
            rate, rate_date = Decimal("1"), "N/A"
        else:
            rate = self._rates.get((base, quote))
            if rate is None:
                from app.errors import ValidationError

                raise ValidationError(
                    f"No deterministic rate configured for {base}->{quote}."
                )
            rate_date = "2026-08-25"
        converted = (dec_amount * rate).quantize(Decimal("0.01"))
        return ConversionResult(
            original_amount=dec_amount,
            source_currency=base,
            target_currency=quote,
            rate=rate,
            converted_amount=converted,
            rate_date=rate_date,
            provider="Deterministic eval fixture",
        )


# --------------------------------------------------------------------------- #
# Menu source
# --------------------------------------------------------------------------- #

def load_menu_fixture() -> list[dict]:
    with open(config.MENU_FIXTURE_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [i for i in data if isinstance(i, dict)]


def load_menu_from_firestore() -> list[dict]:
    from app.repositories.menu import list_menu_items

    return list_menu_items()


def build_menu_lookup(items: list[dict]) -> dict[str, dict]:
    return {item.get("id"): item for item in items if item.get("id")}


def patch_menu_service(menu_service, items: list[dict]):
    """Point the real ``MenuService``'s repo access at an in-memory item list.

    ``MenuService`` reads through module-level ``list_menu_items`` /
    ``get_menu_item``, so patching them keeps the entire production filtering
    pipeline (hybrid/structured search, hard constraints) intact while removing
    the Firestore dependency for deterministic runs.
    """
    by_id = build_menu_lookup(items)
    from app.repositories import menu as menu_repo

    menu_repo.list_menu_items = lambda category=None: _fixture_list(items, by_id, category)
    menu_repo.get_menu_item = lambda menu_id: by_id.get(menu_id)
    menu_service.list_menu_items = menu_repo.list_menu_items
    menu_service.get_menu_item = menu_repo.get_menu_item


def _fixture_list(items: list[dict], by_id: dict, category: str | None) -> list[dict]:
    if category is None:
        return list(items)
    return [i for i in items if (i.get("category") or "") == category]


def make_fixture_services(case_position: str, case_fixtures: dict | None) -> dict:
    """Build fake services from a case's ``fixtures`` dict.

    Returns ``{"preferences": ..., "orders": ..., "history": ...}`` for the
    keys present. ``preferences_to_update`` seeds the update target used by
    ``save_preference``.
    """
    fixtures = case_fixtures or {}
    services: dict = {}
    uid = config.DEFAULT_UID
    if "preferences" in fixtures:
        doc = fixtures["preferences"]
        if "preferences_to_update" in fixtures:
            doc = deepcopy(fixtures["preferences_to_update"])
        services["preferences"] = FakePreferencesService(doc, uid_whitelist={uid})
    if "orders" in fixtures:
        services["orders"] = FakeOrderHistoryService(fixtures["orders"])
    if "history" in fixtures:
        services["history"] = FakeConversationHistoryService(fixtures["history"])
    return services