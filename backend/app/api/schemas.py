"""Strongly-typed public API request/response models.

These types define the contract between the frontend and the backend.
They intentionally do NOT leak internal agent/RAG state.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import (
    RETRIEVAL_TOP_K,
)


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Request body for POST /api/chat.

    ``messages`` carries the full conversation so the backend can build
    conversation-level context itself without touching Firestore conversation
    persistence (which remains owned by the frontend).
    """

    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Conversation messages, oldest to newest.",
    )
    conversation_id: str | None = Field(default=None, max_length=128)
    preferences: dict | None = Field(default=None)

    @field_validator("messages")
    @classmethod
    def _must_end_with_user(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        if messages[-1].role != "user":
            raise ValueError(
                "The last message in the conversation must be from the user."
            )
        return messages

    def last_user_message(self) -> str:
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return ""


class ChatContextMetadata(BaseModel):
    """Non-sensitive metadata returned with a chat response.

    Kept deliberately small. Exposes what the frontend may want to render
    (e.g. which preferences influenced the answer) without leaking internal
    agent reasoning or retrieved chunks.
    """

    used_preferences: bool = False
    retrieval_used: bool = False
    retrieval_count: int = 0


class ChatResponse(BaseModel):
    """Response body for POST /api/chat."""

    answer: str = Field(..., min_length=1)
    context: ChatContextMetadata = Field(default_factory=ChatContextMetadata)


class ChatConfig(BaseModel):
    """Read-only chat configuration exposed to the frontend.

    Used by the frontend to understand what the backend supports.
    """

    retrieval_top_k: int = RETRIEVAL_TOP_K
    supported: bool = True


class ApiErrorResponse(BaseModel):
    """Canonical error envelope returned to the client."""

    detail: str