"""Currency conversion tool exposed to the Gemini model.

Thin LangChain ``@tool`` wrapper around ``CurrencyService``. The service
remains the single source of truth for conversion logic — this module only
defines the model-facing interface (name, description, argument schema).
"""
from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

from app.services.currency_service import get_currency_service


@tool
def convert_currency(
    amount: Annotated[
        float,
        "The monetary amount to convert (a positive number, e.g. 190 or 12.5).",
    ],
    from_currency: Annotated[
        str,
        "Source currency: an ISO-4217 code (INR, USD, EUR) or a common "
        "symbol/name (₹, $, rupees, dollars, euros).",
    ],
    to_currency: Annotated[
        str,
        "Target currency: an ISO-4217 code (USD, INR, EUR) or a common "
        "symbol/name ($, ₹, dollars, rupees, euros).",
    ],
) -> str:
    """Convert an amount between two currencies using the Frankfurter reference rate.

    Use this whenever the customer asks how much an amount is worth in another
    currency, or when they want a menu price converted (call search_menu first
    to get the item's price, then pass that price here). Returns the latest
    published exchange rate from the Frankfurter API for the given amount — the
    rate is a published daily reference rate, not a live forex trading price and
    not a statement about a country's economy. Never compute the rate yourself;
    always report this tool's result.
    """
    result = get_currency_service().convert(
        amount=amount,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    return (
        f"{result.original_amount} {result.source_currency} = "
        f"{result.converted_amount} {result.target_currency} "
        f"(exchange rate: 1 {result.source_currency} = {result.rate} "
        f"{result.target_currency}, rate date: {result.rate_date}, "
        f"source: {result.provider})"
    )


CURRENCY_TOOLS = [convert_currency]