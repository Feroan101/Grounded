"""Customer preferences API endpoints.

Both endpoints require a verified Firebase token; the UID comes from the
token (``get_current_user``), never from the request body. Access is scoped to
the authenticated user's own preferences document.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import PreferencesUpdate, UserPreferences
from app.auth import get_current_user
from app.services import preferences_service

router = APIRouter(prefix="/api", tags=["preferences"])


@router.get("/preferences", response_model=UserPreferences)
def get_preferences(user: dict = Depends(get_current_user)) -> UserPreferences:
    """Return the authenticated user's preferences (with safe defaults)."""
    return UserPreferences.model_validate(
        preferences_service.get_preferences_service().get_preferences(user["uid"])
    )


@router.patch("/preferences", response_model=UserPreferences)
def update_preferences(
    payload: PreferencesUpdate,
    user: dict = Depends(get_current_user),
) -> UserPreferences:
    """Partially update the authenticated user's preferences."""
    if not payload.has_updates():
        raise HTTPException(
            status_code=422,
            detail="Provide at least one preference field to update.",
        )
    updates = payload.model_dump(exclude_none=True)
    result = preferences_service.get_preferences_service().update_preferences(
        user["uid"], updates
    )
    return UserPreferences.model_validate(result)