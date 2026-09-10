"""Menu search service backing the ``search_menu`` tool.

Owns the filtering rules for menu searches and reads item data from Firestore
through the menu repository. The tool (in ``menu_tools.py``) is a thin wrapper
around this service, mirroring the currency-conversion layering.

Search is hybrid: when semantic menu retrieval is configured, a natural-language
query is embedded and used to surface candidate menu IDs from the vector store.
Those candidates are re-validated against the canonical Firestore documents and
hard structured filters are applied. If Qdrant/embeddings are unavailable or
produce no matches, the existing structured/keyword search is used instead.
"""
from __future__ import annotations

import logging

from app.config import MENU_SEMANTIC_TOP_K, is_semantic_menu_configured
from app.errors import ProviderError
from app.rag.menu import search_semantic_menu_ids
from app.repositories.menu import get_menu_item, list_menu_items

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
        """Return menu items matching all supplied filters.

        Structured constraints are always hard constraints: a semantically
        similar item that violates a filter is never returned. ``available``
        defaults to ``True`` so sold-out items are only returned when explicitly
        requested.
        """
        items, _ = self._search(
            query=query,
            category=category,
            max_price=max_price,
            dietary=dietary,
            caffeine=caffeine,
            temperature=temperature,
            sweetness=sweetness,
            available=available,
            flavor=flavor,
        )
        return items

    def _search(
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
    ) -> tuple[list[dict], dict]:
        """Run hybrid search. Returns ``(items, diagnostics)``.

        Diagnostics expose how the search behaved (semantic used / fallback
        reason / candidate counts) so fallback behavior is observable in tests.
        """
        diagnostics: dict = {
            "semantic_used": False,
            "fallback_reason": None,
            "candidate_count": 0,
            "missing_from_firestore": 0,
        }

        if is_semantic_menu_configured() and query:
            semantic_items, semantic_diag = self._semantic_search(
                query=query,
                category=category,
                max_price=max_price,
                dietary=dietary,
                caffeine=caffeine,
                temperature=temperature,
                sweetness=sweetness,
                available=available,
                flavor=flavor,
            )
            diagnostics.update(semantic_diag)
            if semantic_items is None:
                diagnostics["fallback_reason"] = "provider_failed"
            elif semantic_items:
                diagnostics["semantic_used"] = True
                return semantic_items, diagnostics
            else:
                diagnostics["semantic_used"] = True
                diagnostics["fallback_reason"] = "no_semantic_matches"

        items = self._structured_search(
            query=query,
            category=category,
            max_price=max_price,
            dietary=dietary,
            caffeine=caffeine,
            temperature=temperature,
            sweetness=sweetness,
            available=available,
            flavor=flavor,
        )
        return items, diagnostics

    def _semantic_search(
        self,
        *,
        query: str,
        category: str | None = None,
        max_price: float | int | None = None,
        dietary: str | None = None,
        caffeine: str | None = None,
        temperature: str | None = None,
        sweetness: str | None = None,
        available: bool = True,
        flavor: str | None = None,
    ) -> tuple[list[dict] | None, dict]:
        """Semantic candidate search followed by hard structured filtering.

        Returns ``(None, diag)`` when the semantic providers failed — the caller
        then falls back to structured search. Returns ``([], diag)`` on a
        successful search with no matches.
        """
        diag = {"candidate_count": 0, "missing_from_firestore": 0}
        try:
            candidate_ids = search_semantic_menu_ids(
                query, top_k=MENU_SEMANTIC_TOP_K
            )
        except Exception as exc:  # noqa: BLE001 — providers failing is expected
            logger.warning(
                "Semantic menu search failed (%s); using structured fallback.", exc
            )
            return None, {**diag, "reason": "provider_error"}

        diag["candidate_count"] = len(candidate_ids)
        if not candidate_ids:
            return [], diag

        results: list[dict] = []
        for menu_id in candidate_ids:
            try:
                item = get_menu_item(menu_id)
            except Exception as exc:  # noqa: BLE001 — wrap upstream failures
                logger.warning("Menu lookup failed for '%s': %s", menu_id, exc)
                raise ProviderError("The menu is temporarily unavailable.") from exc

            if item is None:
                diag["missing_from_firestore"] += 1
                continue  # stale vector — the canonical document no longer exists
            if self._matches(
                item,
                category=category,
                max_price=max_price,
                dietary=dietary,
                caffeine=caffeine,
                temperature=temperature,
                sweetness=sweetness,
                available=available,
                flavor=flavor,
            ):
                results.append(item)

        return results, diag

    def _structured_search(
        self,
        *,
        query: str | None,
        category: str | None = None,
        max_price: float | int | None = None,
        dietary: str | None = None,
        caffeine: str | None = None,
        temperature: str | None = None,
        sweetness: str | None = None,
        available: bool = True,
        flavor: str | None = None,
    ) -> list[dict]:
        try:
            items = list_menu_items(category=category)
        except Exception as exc:  # noqa: BLE001 — wrap upstream failures
            logger.warning("Menu lookup failed: %s", exc)
            raise ProviderError("The menu is temporarily unavailable.") from exc

        results = []
        for item in items:
            if not self._matches(
                item,
                category=category,
                max_price=max_price,
                dietary=dietary,
                caffeine=caffeine,
                temperature=temperature,
                sweetness=sweetness,
                available=available,
                flavor=flavor,
            ):
                continue
            if not _text_match(item, query):
                continue
            results.append(item)

        results.sort(key=lambda item: _lower(item.get("name", item.get("id", ""))))
        return results

    @staticmethod
    def _matches(
        item: dict,
        *,
        category: str | None,
        max_price: float | int | None,
        dietary: str | None,
        caffeine: str | None,
        temperature: str | None,
        sweetness: str | None,
        available: bool,
        flavor: str | None,
    ) -> bool:
        """All structured constraints. Hard: every one must be satisfied."""
        item_available = item.get("available", True)
        if available is True and item_available is not True:
            return False
        if available is False and item_available is not False:
            return False

        if max_price is not None:
            try:
                if float(item.get("price")) > float(max_price):
                    return False
            except (TypeError, ValueError):
                # A malformed price can never satisfy a price bound.
                return False

        if not _value_match(item.get("category"), category):
            return False
        if not _value_match(item.get("caffeine"), caffeine):
            return False
        if not _value_match(item.get("temperature"), temperature):
            return False
        if not _value_match(item.get("sweetness"), sweetness):
            return False
        if not _list_contains(item.get("dietary"), dietary):
            return False
        if not _flavor_match(item, flavor):
            return False
        return True


_menu_service = MenuService()


def get_menu_service() -> MenuService:
    return _menu_service