"""Currency conversion tool exposed to the Gemini model.

Thin LangChain ``@tool`` wrapper around ``CurrencyService``. The service
remains the single source of truth for conversion logic — this module only
defines the model-facing interface (name, description, argument schema).
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.services.currency_service import get_currency_service


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between two ISO-4217 currencies.

    Returns the latest published exchange rate from the Frankfurter API for
    the given amount. The rate is a published daily reference rate — it is
    not a live forex trading price and does not reflect inflation, GDP, or any
    other economic indicator.
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