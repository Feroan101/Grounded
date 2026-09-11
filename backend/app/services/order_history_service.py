"""Order-history service.

Read-only, user-scoped retrieval of the customer's past orders for the agent.
The repository reads the existing order schema ``users/{uid}/orders`` documents
with ``items: [{name, qty}], total, createdAt``. This service bounds what the
model is shown: a small number of orders, a bounded number of line items per
order, and truncated item names. Only fields useful for answering historical
order questions are kept — no internal document IDs, no unrelated metadata.

Order history never reaches Gemini automatically; the agent calls
``get_order_history`` only when a request genuinely depends on past orders. No
LLM summarization, no writes, and malformed records are ignored safely. The UID
must always come from a verified Firebase token.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.config import (
    ORDER_HISTORY_MAX_CHARS,
    ORDER_HISTORY_MAX_ITEMS,
    ORDER_HISTORY_MAX_ORDERS,
)
from app.errors import ProviderError
from app.repositories import orders as orders_repo

logger = logging.getLogger(__name__)


@dataclass
class OrderRecord:
    """One bounded, model-readable past order."""

    date: str | None
    items: list[dict]
    total: str | None


def _date_str(value) -> str | None:
    """Best-effort ``YYYY-MM-DD`` from a Firestore timestamp value."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    date = getattr(value, "date", None)
    if callable(date):
        try:
            return date().isoformat()
        except Exception:  # noqa: BLE001 — timestamps are best-effort
            return None
    return None


def _truncate(content: str, max_chars: int) -> str:
    """Truncate an item name so the model context stays compact."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "..."


def _normalize_items(items, max_items: int, max_chars: int) -> list[dict]:
    """Return bounded ``{name, qty}`` line items from a stored ``items`` list."""
    if not isinstance(items, list):
        return []
    cleaned: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        entry: dict = {"name": _truncate(name.strip(), max_chars)}
        qty = item.get("qty")
        if isinstance(qty, (int, float)) and not isinstance(qty, bool):
            try:
                qty_int = int(Decimal(str(qty)).to_integral_value())
            except (InvalidOperation, ValueError, TypeError):
                qty_int = None
            if qty_int is not None and qty_int >= 1:
                entry["qty"] = qty_int
        cleaned.append(entry)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _normalize_total(total) -> str | None:
    """Format a stored numeric total without inventing a currency symbol."""
    if total is None:
        return None
    if isinstance(total, bool):
        return None
    try:
        value = Decimal(str(total))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if value != value.to_integral_value():
        return str(value)
    return str(value.to_integral_value())


class OrderHistoryService:
    """Reads and bounds the customer's recent past orders."""

    def get_history(
        self,
        uid: str,
        *,
        max_orders: int = ORDER_HISTORY_MAX_ORDERS,
        max_items: int = ORDER_HISTORY_MAX_ITEMS,
        max_chars: int = ORDER_HISTORY_MAX_CHARS,
    ) -> list[OrderRecord]:
        """Return the most recent orders for ``uid``, bounded."""
        try:
            docs = orders_repo.get_order_history(uid)
        except Exception as exc:  # noqa: BLE001 — wrap upstream failures
            logger.warning("Order history lookup failed for uid: %s", exc)
            raise ProviderError("Order history is temporarily unavailable.") from exc

        records: list[OrderRecord] = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            items = _normalize_items(doc.get("items"), max_items, max_chars)
            if not items:
                continue
            records.append(
                OrderRecord(
                    date=_date_str(doc.get("createdAt")),
                    items=items,
                    total=_normalize_total(doc.get("total")),
                )
            )
            if len(records) >= max_orders:
                break

        return records


_order_history_service = OrderHistoryService()


def get_order_history_service() -> OrderHistoryService:
    return _order_history_service