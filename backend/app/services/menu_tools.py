"""Menu search tool exposed to the Gemini model.

Thin LangChain ``@tool`` wrapper around ``MenuService``. The service remains
the single source of truth for menu search/filtering — this module only
defines the model-facing interface (name, description, argument schema) and
the readable result format.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from app.services.menu_service import get_menu_service

_DISPLAY_LIMIT = 8


@tool
def search_menu(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    dietary: Optional[str] = None,
    caffeine: Optional[str] = None,
    temperature: Optional[str] = None,
    sweetness: Optional[str] = None,
    available: bool = True,
    flavor: Optional[str] = None,
) -> str:
    """Search the coffee shop menu for drinks and food items.

    Use this tool for ANY question about the menu: product names, prices,
    ingredients, sizes, milk options, dietary options (vegan, vegetarian,
    dairy-free), caffeine level, temperature (hot or cold), sweetness, flavors,
    and availability. Results are read from the shop's real menu database —
    report only what this tool returns and never invent menu facts.
    """
    items = get_menu_service().search(
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

    if not items:
        return (
            "No menu items match the search criteria. The current menu does "
            "not contain an item with those filters. Do not claim the item "
            "exists or invent prices, ingredients, or availability — tell the "
            "customer it is not on the menu."
        )

    lines = []
    for index, item in enumerate(items[:_DISPLAY_LIMIT], start=1):
        lines.append(_format_item(index, item))

    if len(items) > _DISPLAY_LIMIT:
        lines.append(
            f"{len(items)} items match; showing the first {_DISPLAY_LIMIT}. "
            "Narrow the search for more specific results."
        )

    return "\n".join(lines)


def _format_item(index: int, item: dict) -> str:
    dietary = ", ".join(item.get("dietary") or []) or "none"
    availability = "available" if item.get("available", True) else "unavailable"
    return (
        f"{index}. {item.get('name', 'Unknown')} ({item.get('category', '')})"
        f" | price {item.get('price')}"
        f" | size {item.get('size', '')}"
        f" | caffeine: {item.get('caffeine', '')}"
        f" | temp: {item.get('temperature', '')}"
        f" | sweetness: {item.get('sweetness', '')}"
        f" | dietary: {dietary}"
        f" | {availability}"
        f" | {item.get('description', '')}"
    )


MENU_TOOLS = [search_menu]