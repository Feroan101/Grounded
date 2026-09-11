"""Conversation-history service.

Read-only, user-scoped retrieval of the customer's past conversations for the
agent. The repository reads the array-based schema the frontend actually writes
(``users/{uid}/conversations/{id}`` with ``title``, ``messages``, ``createdAt``);
this service bounds what the model is shown: a small number of conversations,
only the most recent messages per conversation, and truncated message content.

History is never loaded by default — the agent calls ``get_conversation_history``
only when a request genuinely depends on earlier chats. No LLM summarization
happens here (latency and token cost), nothing is ever written, and malformed
records are ignored safely. The UID must always come from a verified Firebase
token, never from the client.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.config import (
    CONVERSATION_HISTORY_MAX_CHARS,
    CONVERSATION_HISTORY_MAX_CONVERSATIONS,
    CONVERSATION_HISTORY_MAX_MESSAGES,
)
from app.errors import ProviderError
from app.repositories import conversations as conversations_repo

logger = logging.getLogger(__name__)


@dataclass
class ConversationRecord:
    """One bounded, model-readable past conversation."""

    title: str | None
    date: str | None
    messages: list[dict]


def _truncate(content: str, max_chars: int) -> str:
    """Truncate a message so the model context stays compact."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rstrip() + "..."


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


def _normalize_messages(
    messages, max_messages: int, max_chars: int
) -> list[dict]:
    """Return bounded, valid ``{role, content}`` messages (newest slice last).

    Malformed entries are ignored, consecutive duplicates are dropped, and only
    ``user``/``assistant`` roles with non-empty text are kept.
    """
    if not isinstance(messages, list):
        return []
    cleaned: list[dict] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        content = _truncate(content.strip(), max_chars)
        if cleaned and cleaned[-1]["role"] == role and cleaned[-1]["content"] == content:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned[-max_messages:]


class ConversationHistoryService:
    """Reads and bounds the customer's recent past conversations."""

    def get_history(
        self,
        uid: str,
        *,
        exclude_id: str | None = None,
        max_conversations: int = CONVERSATION_HISTORY_MAX_CONVERSATIONS,
        max_messages: int = CONVERSATION_HISTORY_MAX_MESSAGES,
        max_chars: int = CONVERSATION_HISTORY_MAX_CHARS,
    ) -> list[ConversationRecord]:
        """Return the most recent conversations for ``uid``, bounded.

        ``exclude_id`` drops the current conversation (already fully present in
        the chat request) so the model is not shown the same messages twice.
        """
        try:
            docs = conversations_repo.get_recent_conversations(uid)
        except Exception as exc:  # noqa: BLE001 — wrap upstream failures
            logger.warning("Conversation history lookup failed for uid: %s", exc)
            raise ProviderError(
                "Conversation history is temporarily unavailable."
            ) from exc

        records: list[ConversationRecord] = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if exclude_id and doc.get("id") == exclude_id:
                continue
            messages = _normalize_messages(doc.get("messages"), max_messages, max_chars)
            if not messages:
                continue
            title = doc.get("title")
            if not isinstance(title, str) or not title.strip():
                title = None
            records.append(
                ConversationRecord(
                    title=title,
                    date=_date_str(doc.get("createdAt")),
                    messages=messages,
                )
            )
            if len(records) >= max_conversations:
                break

        return records


_conversation_history_service = ConversationHistoryService()


def get_conversation_history_service() -> ConversationHistoryService:
    return _conversation_history_service