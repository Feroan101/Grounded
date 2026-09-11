"""Conversation-history tool exposed to the Gemini model.

Built **per request** and closes over the authenticated UID (from a verified
Firebase token), mirroring the preference tools. The model controls only
*whether* history is consulted, never which user or which Firestore document is
read — there is no way to reach an arbitrary path. Retrieval honors the
customer's ``conversationHistoryEnabled`` preference; when it is disabled (or
cannot be determined) history is never read and a safe empty result is returned.
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.errors import ProviderError
from app.services.conversation_history_service import get_conversation_history_service
from app.services.preferences_service import get_preferences_service

_UNAVAILABLE = (
    "Conversation history is currently unavailable. Do not guess what the "
    "customer said or ordered before."
)


def _format_record(record) -> str:
    header = (
        f'Past conversation: "{record.title}"'
        if record.title
        else "Past conversation"
    )
    if record.date:
        header += f" (from {record.date})"
    lines = [header]
    lines.extend(f"{msg['role'].capitalize()}: {msg['content']}" for msg in record.messages)
    return "\n".join(lines)


def build_conversation_history_tools(
    uid: str, exclude_conversation_id: str | None = None
) -> list:
    """Build the conversation-history tools for one authenticated customer."""

    @tool
    def get_conversation_history() -> str:
        """Read this customer's recent past conversations.

        Use ONLY when the customer's question genuinely depends on an earlier
        chat (for example 'what did I order last time?'). It returns a small,
        recent slice of past conversations. Base any claims about past
        conversations only on what this tool returns — never claim to remember
        earlier chats when the tool returns nothing.
        """
        try:
            prefs = get_preferences_service().get_preferences(uid)
        except ProviderError:
            return _UNAVAILABLE

        if not prefs.get("conversationHistoryEnabled", True):
            return (
                "This customer has conversation history turned off. Do not "
                "refer to past conversations or claim to remember them."
            )

        try:
            records = get_conversation_history_service().get_history(
                uid, exclude_id=exclude_conversation_id
            )
        except ProviderError:
            return _UNAVAILABLE

        if not records:
            return (
                "This customer has no recent past conversations on record. "
                "Answer from the current conversation and the menu."
            )

        return "Recent past conversations with this customer:\n\n" + "\n\n".join(
            _format_record(record) for record in records
        )

    return [get_conversation_history]