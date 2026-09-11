"""Order-history tool exposed to the Gemini model.

Built **per request** and closes over the authenticated UID (from a verified
Firebase token), mirroring the preference and conversation-history tools. The
model controls only *whether* the customer's past orders are consulted, never
which user or which collection is read — there is no user or path argument, so
an arbitrary Firestore query is impossible. Retrieval is opt-in: the tool is
invoked only when a request genuinely depends on past orders.
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.errors import ProviderError
from app.services.order_history_service import get_order_history_service

_UNAVAILABLE = (
    "Order history is currently unavailable. Do not claim the customer "
    "ordered anything you cannot see."
)


def _format_record(record) -> str:
    lines = ["Order" + (f" from {record.date}" if record.date else "")]
    for item in record.items:
        name = item.get("name", "Unknown")
        qty = item.get("qty")
        lines.append(f"- {name}" + (f" x{qty}" if qty else ""))
    if record.total is not None:
        lines.append(f"Total: {record.total}")
    return "\n".join(lines)


def build_order_history_tools(uid: str) -> list:
    """Build the order-history tools for one authenticated customer."""

    @tool
    def get_order_history() -> str:
        """Return this customer's recent past orders.

        Use ONLY when the customer's question genuinely depends on earlier
        purchases (for example 'what did I order last time?'). It returns a
        small, recent slice of past orders. Base any claims about what the
        customer ordered strictly on what this tool returns — never claim an
        order was placed when the tool returns nothing.
        """
        try:
            records = get_order_history_service().get_history(uid)
        except ProviderError:
            return _UNAVAILABLE

        if not records:
            return (
                "This customer has no past orders on record. Do not claim the "
                "customer has ordered before."
            )

        return (
            "Recent orders for this customer:\n\n"
            + "\n\n".join(_format_record(record) for record in records)
            + "\nNote: only what was ordered before is shown — never treat an "
            "old order as proof an item is currently on the menu or "
            "available."
        )

    return [get_order_history]