"""Chat API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.schemas import ChatConfig, ChatRequest, ChatResponse
from app.auth import get_current_user
from app.services.chat_service import get_chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Send a conversation to the Grounded agent.

    Authentication is mandatory. The user's identity comes from the verified
    Firebase token — never from the request body.
    """
    service = get_chat_service()
    result = service.process(request, user)

    if not result.ok:
        from fastapi import HTTPException

        raise HTTPException(status_code=result.status_code, detail=result.error)

    return ChatResponse(answer=result.answer, context=result.context)


@router.get("/chat/config", response_model=ChatConfig)
def chat_config(
    user: dict = Depends(get_current_user),
) -> ChatConfig:
    """Read-only chat configuration (explicitly authenticated)."""
    return ChatConfig()