"""Customer preference tools exposed to the Gemini model.

The menu and currency tools are module-level singletons; preference tools are
different. They are built **per request** and close over the authenticated
UID, so the model can never choose which user to read or write, and there is
no way to reach an arbitrary Firestore path. Only stable, customer-stated
preferences are accepted via ``save_preference``.
"""
from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from app.errors import ValidationError
from app.services.preferences_service import get_preferences_service, parse_agent_preference

AgentPreferenceField = Literal[
    "allergiesOrIntolerances",
    "brewMethod",
    "caffeinePreference",
    "customContext",
    "dietaryPreference",
    "favoriteDrink",
    "milkPreference",
    "recommendationStyle",
    "responseStyle",
    "roastPreference",
    "strength",
    "sweetness",
    "temperature",
    "tone",
    "usePreferencesInConversations",
]

_LABELS = {
    "favoriteDrink": "Favorite drink",
    "temperature": "Preferred temperature",
    "milkPreference": "Milk preference",
    "sweetness": "Sweetness",
    "strength": "Strength",
    "caffeinePreference": "Caffeine preference",
    "roastPreference": "Roast preference",
    "brewMethod": "Brew method",
    "dietaryPreference": "Dietary preferences",
    "allergiesOrIntolerances": "Allergies/intolerances",
    "customContext": "Personal context",
    "responseStyle": "Response style",
    "tone": "Tone",
    "recommendationStyle": "Recommendation style",
    "usePreferencesInConversations": "Use preferences in conversations",
}

_AI_DEFAULTS = {
    "responseStyle": "balanced",
    "tone": "friendly",
    "recommendationStyle": "best",
}


def build_preference_tools(uid: str) -> list:
    """Build the preference tools for one authenticated customer."""

    @tool
    def get_customer_preferences() -> str:
        """Read the customer's stored preferences.

        Call this before giving a personalized recommendation or when the
        customer mentions tastes, milk, sweetness, temperature, favorites, or
        things they avoid. It returns only what the shop actually knows about
        this customer — never invent preferences the customer has not stated.
        """
        prefs = get_preferences_service().get_preferences(uid)

        if not prefs["aiContext"]["usePreferencesInConversations"]:
            return (
                "The customer has switched off preference personalization. Do "
                "not use stored preferences to tailor answers — just talk "
                "normally and answer from the menu."
            )

        coffee = prefs["coffee"]
        lines = []
        if coffee.get("favoriteDrink"):
            lines.append(f"Favorite drink: {coffee['favoriteDrink']}")
        if coffee.get("temperature") and coffee["temperature"] != "either":
            lines.append(f"Preferred temperature: {coffee['temperature']}")
        if coffee.get("milkPreference"):
            lines.append(f"Milk preference: {coffee['milkPreference']}")
        if coffee.get("sweetness"):
            lines.append(f"Sweetness: {coffee['sweetness']}")
        if coffee.get("strength"):
            lines.append(f"Strength: {coffee['strength']}")
        if coffee.get("caffeinePreference"):
            lines.append(f"Caffeine: {coffee['caffeinePreference']}")
        if coffee.get("roastPreference"):
            lines.append(f"Roast preference: {coffee['roastPreference']}")
        if coffee.get("brewMethod"):
            lines.append(f"Brew method: {coffee['brewMethod']}")
        if coffee.get("dietaryPreference"):
            lines.append(f"Dietary: {', '.join(coffee['dietaryPreference'])}")
        if coffee.get("allergiesOrIntolerances"):
            lines.append(f"Allergies/intolerances: {coffee['allergiesOrIntolerances']}")

        ai = prefs["aiContext"]
        if ai.get("customContext"):
            lines.append(f"Personal context: {ai['customContext']}")
        for field, default in _AI_DEFAULTS.items():
            value = ai.get(field)
            if value and value != default:
                lines.append(f"{_LABELS[field]}: {value}")

        if not lines:
            return (
                "The customer has no stored preferences yet. Recommend from "
                "the menu and the customer's current request."
            )
        return (
            "Stored customer preferences:\n- "
            + "\n- ".join(lines)
            + "\nTrivia: base recommendations on these and on real menu data "
            "only — never guess preferences the customer has not stated."
        )

    @tool
    def save_preference(field: AgentPreferenceField, value: str) -> str:
        """Save a stable preference the customer explicitly stated.

        Save ONLY when the customer clearly expresses a lasting preference
        (for example "I prefer oat milk", "I don't like very sweet drinks",
        "I usually order iced"). Never save moods, how someone feels right
        now, one-off requests, or anything the customer did not say. If the
        customer just wants something different today, do NOT save it.
        """
        try:
            updates = parse_agent_preference(field, value)
        except ValidationError as exc:
            return (
                f"Could not save that preference: {exc.message} Ask the "
                "customer for a supported value, or skip saving."
            )
        get_preferences_service().update_preferences(uid, updates)
        stored_value = updates["coffee"].get(field) if "coffee" in updates else updates["aiContext"].get(field)
        if isinstance(stored_value, list):
            stored_value = ", ".join(str(v) for v in stored_value)
        return f"Saved preference: {_LABELS[field]} = {stored_value}."

    return [get_customer_preferences, save_preference]