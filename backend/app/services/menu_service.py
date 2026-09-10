"""Menu search service backing the ``search_menu`` tool.

Owns the filtering rules for menu searches and reads item data from Firestore
through the menu repository. The tool (in ``menu_tools.py``) is a thin wrapper
around this service, mirroring the currency-conversion layering.
"""
from __future__ import annotations

import logging

from app.errors import ProviderError
from app.repositories.menu import list_menu_items

logger = logging.getLogger(__name__)


def _lower(value: str | None) -> str:
    return (value or "").strip().lower()


def _value_match(item_value: str | None, filter_value: str | None) -> bool:
    """Exact, case-insensitive scalar match. ``None``/empty filter is ignored."""
    if not _lower(filter_value):
        return True
    return _lower(item_value) == _lower(filter_value)


def _list_contains(item_values, filter_value: str | None) -> bool:
    """``filter_value`` must equal one entry of the item's list (ignored if empty)."""
    if not _lower(filter_value):
        return True
    needle = _lower(filter_value)
    return any(_lower(value) == needle for value in (item_values or []))


def _flavor_match(item: dict, flavor: str | None) -> bool:
    if not _lower(flavor):
        return True
    return _list_contains(item.get("flavor_profile"), flavor) or _list_contains(
        item.get("tags"), flavor
    )


def _text_match(item: dict, query: str | None) -> bool:
    """Free-text search across name, description, ingredients, tags, flavors."""
    query_lower = _lower(query)
    if not query_lower:
        return True
    haystack = [_lower(item.get("name", "")), _lower(item.get("description", ""))]
    for field in ("ingredients", "tags", "flavor_profile"):
        haystack.extend(_lower(value) for value in (item.get(field) or []))
    return query_lower in " | ".join(haystack)


class MenuService:
    """Reads and filters menu items from Firestore."""

    def search(
        self,
        *,
        query: str | None = None,
        category: str | None = None,
        max_price: float | int | None = None,
        dietary: str | None = None,
        caffeine: str | None = None,
        temperature: str | None = None,
        sweetness: str | None = None,
        available: bool = True,
        flavor: str | None = None,
    ) -> list[dict]:
        """Return menu items matching all supplied filters, sorted by name.

        Every filter is independent; unmatched filters simply exclude items.
        ``available`` defaults to ``True`` so sold-out items are only returned
        when explicitly requested.
        """
        try:
            items = list_menu_items(category=category)
        except Exception as exc:  # noqa: BLE001 — wrap upstream failures
            logger.warning("Menu lookup failed: %s", exc)
            raise ProviderError("The menu is temporarily unavailable.") from exc

        results = []
        for item in items:
            item_available = item.get("available", True)
            if available is True and item_available is not True:
                continue
            if available is False and item_available is not False:
                continue

            if max_price is not None:
                try:
                    if float(item.get("price")) > float(max_price):
                        continue
                except (TypeError, ValueError):
                    # A malformed price can never satisfy a price bound.
                    continue

            if not _value_match(item.get("category"), category):
                continue
            if not _value_match(item.get("caffeine"), caffeine):
                continue
            if not _value_match(item.get("temperature"), temperature):
                continue
            if not _value_match(item.get("sweetness"), sweetness):
                continue
            if not _list_contains(item.get("dietary"), dietary):
                continue
            if not _flavor_match(item, flavor):
                continue
            if not _text_match(item, query):
                continue

            results.append(item)

        results.sort(key=lambda item: _lower(item.get("name", item.get("id", ""))))
        return results


_menu_service = MenuService()


def get_menu_service() -> MenuService:
    return _menu_service