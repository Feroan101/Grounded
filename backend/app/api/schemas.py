"""Strongly-typed public API request/response models.

These types define the contract between the frontend and the backend.
They intentionally do NOT leak internal agent/RAG state.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    used_conversation_history: bool = False
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


# ---------------------------------------------------------------------------
# Customer preferences (users/{uid}/preferences/current)
#
# Field names deliberately mirror the frontend settings UI and the stored
# Firestore document so the two sides stay in sync.
# ---------------------------------------------------------------------------


class CoffeePreferences(BaseModel):
    """The customer's coffee preferences, exactly as stored/serialized."""

    favoriteDrink: str = ""
    temperature: Literal["hot", "iced", "either"] = "either"
    milkPreference: str = ""
    sweetness: str = ""
    strength: str = ""
    caffeinePreference: str = ""
    roastPreference: str = ""
    brewMethod: str = ""
    dietaryPreference: list[str] = Field(default_factory=list)
    allergiesOrIntolerances: str = ""


class AIContextPreferences(BaseModel):
    """How the customer wants Grounded to communicate and personalize."""

    customContext: str = ""
    responseStyle: Literal["short", "balanced", "detailed"] = "balanced"
    tone: Literal["friendly", "casual", "professional", "playful"] = "friendly"
    recommendationStyle: Literal["best", "few", "explain"] = "best"
    usePreferencesInConversations: bool = True


class CoffeePreferencesUpdate(BaseModel):
    """Partial update of coffee preferences (all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    favoriteDrink: str | None = Field(default=None, max_length=200)
    temperature: Literal["hot", "iced", "either"] | None = None
    milkPreference: str | None = Field(default=None, max_length=100)
    sweetness: str | None = Field(default=None, max_length=100)
    strength: str | None = Field(default=None, max_length=100)
    caffeinePreference: str | None = Field(default=None, max_length=100)
    roastPreference: str | None = Field(default=None, max_length=100)
    brewMethod: str | None = Field(default=None, max_length=100)
    dietaryPreference: list[str] | None = None
    allergiesOrIntolerances: str | None = Field(default=None, max_length=300)


class AIContextUpdate(BaseModel):
    """Partial update of AI context settings (all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    customContext: str | None = Field(default=None, max_length=2000)
    responseStyle: Literal["short", "balanced", "detailed"] | None = None
    tone: Literal["friendly", "casual", "professional", "playful"] | None = None
    recommendationStyle: Literal["best", "few", "explain"] | None = None
    usePreferencesInConversations: bool | None = None


class PreferencesUpdate(BaseModel):
    """Request body for PATCH /api/preferences.

    Nested updates are partial: only the provided fields change. Unknown
    fields are rejected so callers (and the agent) can never write arbitrary
    keys or document paths.
    """

    model_config = ConfigDict(extra="forbid")

    coffee: CoffeePreferencesUpdate | None = None
    aiContext: AIContextUpdate | None = None
    conversationHistoryEnabled: bool | None = None

    def has_updates(self) -> bool:
        return (
            self.coffee is not None
            or self.aiContext is not None
            or self.conversationHistoryEnabled is not None
        )


class UserPreferences(BaseModel):
    """Response body for GET/PATCH /api/preferences."""

    coffee: CoffeePreferences
    aiContext: AIContextPreferences
    conversationHistoryEnabled: bool = True
    createdAt: str | None = None
    updatedAt: str | None = None


class ApiErrorResponse(BaseModel):
    """Canonical error envelope returned to the client."""

    detail: str