"""Customer preferences service.

Owns the read/update contract for customer preferences stored in Firestore at
``users/{uid}/preferences/current`` (user-scoped). Both the API layer and the
agent tools go through this service so safe defaults, field validation, and
controlled error handling live in one place.

The UID is always supplied by the caller and must come from a verified
Firebase token — never from the client.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from google.cloud import firestore

from app.errors import ProviderError, ValidationError
from app.repositories import preferences as preferences_repo

logger = logging.getLogger(__name__)

# Mirrors the frontend settings defaults so the backend never returns an
# incomplete preference document.
DEFAULT_COFFEE = {
    "favoriteDrink": "",
    "temperature": "either",
    "milkPreference": "",
    "sweetness": "",
    "strength": "",
    "caffeinePreference": "",
    "roastPreference": "",
    "brewMethod": "",
    "dietaryPreference": [],
    "allergiesOrIntolerances": "",
}

DEFAULT_AI_CONTEXT = {
    "customContext": "",
    "responseStyle": "balanced",
    "tone": "friendly",
    "recommendationStyle": "best",
    "usePreferencesInConversations": True,
}

COFFEE_KEYS = set(DEFAULT_COFFEE)
AICONTEXT_KEYS = set(DEFAULT_AI_CONTEXT)
TOP_LEVEL_KEYS = {"coffee", "aiContext", "conversationHistoryEnabled"}

# Values grounded agents may save. ``conversationHistoryEnabled`` and memories
# are deliberately excluded — the agent must never change those.
AGENT_FIELDS = COFFEE_KEYS | AICONTEXT_KEYS

_SIMPLE_CHOICES = {
    "temperature": {"hot", "iced", "either"},
    "sweetness": {"none", "less", "regular", "extra"},
    "strength": {"light", "medium", "strong"},
    "caffeinePreference": {"regular", "decaf", "either"},
    "roastPreference": {"light", "medium", "dark"},
    "brewMethod": {"espresso", "pour-over", "french-press", "cold-brew"},
    "responseStyle": {"short", "balanced", "detailed"},
    "tone": {"friendly", "casual", "professional", "playful"},
    "recommendationStyle": {"best", "few", "explain"},
}

_DIETARY_CANONICAL = {
    "vegan": "Vegan",
    "dairy-free": "Dairy-free",
    "sugar-free": "Sugar-free",
    "gluten-free": "Gluten-free",
}

_TEXT_LIMITS = {
    "favoriteDrink": 200,
    "allergiesOrIntolerances": 300,
    "customContext": 2000,
    "milkPreference": 100,
}

def parse_agent_preference(field: str, value: str) -> dict:
    """Validate one leaf preference field from the agent and build an update.

    Returns a partial-update dict like ``{"coffee": {"temperature": "hot"}}``.
    Raises ``ValidationError`` for unknown fields or invalid values so the
    agent can be told exactly what is wrong without touching Firestore.
    """
    if field not in AGENT_FIELDS:
        allowed = ", ".join(sorted(AGENT_FIELDS))
        raise ValidationError(
            f"'{field}' is not a stored preference field. Allowed fields: {allowed}."
        )

    value = (value or "").strip()
    if not value:
        raise ValidationError("Provide a non-empty value to save.")

    if field == "usePreferencesInConversations":
        lowered = value.lower()
        if lowered in {"true", "yes", "on", "1"}:
            parsed: object = True
        elif lowered in {"false", "no", "off", "0"}:
            parsed = False
        else:
            raise ValidationError("usePreferencesInConversations must be true or false.")
    elif field == "dietaryPreference":
        parsed = _parse_dietary(value)
    elif field in _SIMPLE_CHOICES:
        lowered = value.lower()
        if lowered not in _SIMPLE_CHOICES[field]:
            choices = ", ".join(sorted(_SIMPLE_CHOICES[field]))
            raise ValidationError(f"'{value}' is not a supported value for '{field}'. Choose: {choices}.")
        parsed = lowered
    else:
        limit = _TEXT_LIMITS.get(field, 100)
        if len(value) > limit:
            raise ValidationError(f"{field} must be {limit} characters or fewer.")
        parsed = value

    section = "coffee" if field in COFFEE_KEYS else "aiContext"
    return {section: {field: parsed}}


def _parse_dietary(value: str) -> list[str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValidationError("Provide at least one dietary preference.")
    canonical: list[str] = []
    for part in parts:
        key = part.strip().lower()
        if key not in _DIETARY_CANONICAL:
            choices = ", ".join(sorted(_DIETARY_CANONICAL.values()))
            raise ValidationError(
                f"'{part}' is not a supported dietary preference. Choose: {choices}."
            )
        canonical.append(_DIETARY_CANONICAL[key])
    return canonical


def _iso(value) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.isoformat()
    return None


class PreferencesService:
    """Read and update a customer's preferences in Firestore."""

    def get_preferences(self, uid: str) -> dict:
        """Return the customer's preferences with safe defaults filled in."""
        try:
            raw = preferences_repo.get_preferences(uid)
        except Exception:
            logger.exception("Failed to read preferences")
            raise ProviderError("Preferences are temporarily unavailable.") from None
        return self._normalize(self._merged(raw))

    def update_preferences(self, uid: str, updates: dict) -> dict:
        """Merge a validated partial update and return the new full state.

        ``updates`` may contain partial ``coffee`` / ``aiContext`` dicts and/or
        ``conversationHistoryEnabled``. Unknown fields are rejected.
        """
        updates = self._validated_updates(updates)

        try:
            raw = preferences_repo.get_preferences(uid) or {}
        except Exception:
            logger.exception("Failed to read preferences before update")
            raise ProviderError("Preferences are temporarily unavailable.") from None

        existing_coffee = {**DEFAULT_COFFEE, **(raw.get("coffee") or {})}
        existing_ai = {**DEFAULT_AI_CONTEXT, **(raw.get("aiContext") or {})}
        new_coffee = {**existing_coffee, **(updates.get("coffee") or {})}
        new_ai = {**existing_ai, **(updates.get("aiContext") or {})}
        if "conversationHistoryEnabled" in updates:
            conversation_history_enabled = bool(updates["conversationHistoryEnabled"])
        else:
            conversation_history_enabled = raw.get("conversationHistoryEnabled", True)

        now = datetime.now(timezone.utc)
        payload: dict = {
            **raw,  # preserve any unknown top-level data
            "coffee": new_coffee,
            "aiContext": new_ai,
            "conversationHistoryEnabled": conversation_history_enabled,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
        if not raw:
            payload["createdAt"] = firestore.SERVER_TIMESTAMP

        try:
            preferences_repo.update_preferences(uid, payload)
        except Exception:
            logger.exception("Failed to write preferences")
            raise ProviderError("Preferences are temporarily unavailable.") from None

        projected = {
            **payload,
            "createdAt": (raw or {}).get("createdAt", now),
            "updatedAt": now,
        }
        return self._normalize(self._merged(projected))

    @staticmethod
    def _validated_updates(updates: dict) -> dict:
        updates = dict(updates or {})
        unknown = set(updates) - TOP_LEVEL_KEYS
        if unknown:
            raise ValidationError(
                f"Unknown preference field(s): {', '.join(sorted(unknown))}."
            )
        result: dict = {}
        for section, allowed in (("coffee", COFFEE_KEYS), ("aiContext", AICONTEXT_KEYS)):
            if section not in updates or updates[section] is None:
                continue
            partial = dict(updates[section])
            bad = set(partial) - allowed
            if bad:
                raise ValidationError(
                    f"Unknown preference field(s) under '{section}': {', '.join(sorted(bad))}."
                )
            result[section] = partial
        if updates.get("conversationHistoryEnabled") is not None:
            result["conversationHistoryEnabled"] = bool(
                updates["conversationHistoryEnabled"]
            )
        return result

    @staticmethod
    def _merged(raw: dict | None) -> dict:
        raw = raw or {}
        coffee = raw.get("coffee") or {}
        ai = raw.get("aiContext") or {}
        return {
            "coffee": {**DEFAULT_COFFEE, **coffee},
            "aiContext": {**DEFAULT_AI_CONTEXT, **ai},
            "conversationHistoryEnabled": raw.get("conversationHistoryEnabled", True),
            "createdAt": raw.get("createdAt"),
            "updatedAt": raw.get("updatedAt"),
        }

    @staticmethod
    def _normalize(merged: dict) -> dict:
        coffee = merged.get("coffee") or {}
        temperature = coffee.get("temperature")
        if temperature not in _SIMPLE_CHOICES["temperature"]:
            temperature = DEFAULT_COFFEE["temperature"]
        dietary = coffee.get("dietaryPreference")
        if not isinstance(dietary, list):
            dietary = []
        coffee_out = {**DEFAULT_COFFEE, **coffee, "temperature": temperature}
        coffee_out["dietaryPreference"] = [str(d) for d in dietary]

        ai = merged.get("aiContext") or {}
        response_style = ai.get("responseStyle")
        if response_style not in _SIMPLE_CHOICES["responseStyle"]:
            response_style = DEFAULT_AI_CONTEXT["responseStyle"]
        tone = ai.get("tone")
        if tone not in _SIMPLE_CHOICES["tone"]:
            tone = DEFAULT_AI_CONTEXT["tone"]
        recommendation_style = ai.get("recommendationStyle")
        if recommendation_style not in _SIMPLE_CHOICES["recommendationStyle"]:
            recommendation_style = DEFAULT_AI_CONTEXT["recommendationStyle"]
        ai_out = {**DEFAULT_AI_CONTEXT, **ai}
        ai_out["responseStyle"] = response_style
        ai_out["tone"] = tone
        ai_out["recommendationStyle"] = recommendation_style
        ai_out["usePreferencesInConversations"] = bool(
            ai_out["usePreferencesInConversations"]
        )

        enabled = merged.get("conversationHistoryEnabled")
        if not isinstance(enabled, bool):
            enabled = True

        return {
            "coffee": coffee_out,
            "aiContext": ai_out,
            "conversationHistoryEnabled": enabled,
            "createdAt": _iso(merged.get("createdAt")),
            "updatedAt": _iso(merged.get("updatedAt")),
        }


_preferences_service = PreferencesService()


def get_preferences_service() -> PreferencesService:
    return _preferences_service