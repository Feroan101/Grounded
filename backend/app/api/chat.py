"""Chat API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatConfig, ChatRequest, ChatResponse
from app.auth import get_current_user
from app.services.chat_service import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

_STREAM_MEDIA_TYPE = "text/event-stream"
_KEEPALIVE_SECONDS = 15.0


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    request_obj: Request,
    user: dict = Depends(get_current_user),
):
    """Send a conversation to the Grounded agent.

    Authentication is mandatory. The user's identity comes from the verified
    Firebase token — never from the request body.

    Responds with the usual JSON ``ChatResponse`` unless the client asks for
    ``text/event-stream``, in which case the response is streamed as a series
    of SSE events (``tool``, ``generating``, ``done``, ``error``) that reflect
    the agent's real progress without exposing internals.
    """
    service = get_chat_service()

    if _wants_stream(request_obj.headers.get("accept")):
        return StreamingResponse(
            _chat_event_stream(service, request, user),
            media_type=_STREAM_MEDIA_TYPE,
            headers={
                "Cache-Control": "no-cache, no-transform, no-store",
                "X-Accel-Buffering": "no",
            },
        )

    result = service.process(request, user)

    if not result.ok:
        raise HTTPException(status_code=result.status_code, detail=result.error)

    return ChatResponse(answer=result.answer, context=result.context)


async def _chat_event_stream(service, request: ChatRequest, user: dict):
    """Yield SSE events for a chat run.

    The agent runs in a daemon thread (Gemini is blocking) and reports
    lightweight progress events through an asyncio queue, so the event loop is
    never blocked. Events streamed to the client:

    - ``{"type": "tool", "name": "<tool>"}`` before a tool executes
    - ``{"type": "generating"}`` before each follow-up model round
    - ``{"type": "done", "answer": ..., "context": {...}}`` on success
    - ``{"type": "error", "message": ...}`` on failure (sanitized)

    A ``: ping`` comment is emitted every 15s while the run is quiet so
    proxies do not close an idle connection.
    """
    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(kind: str, payload: dict) -> None:
        # Called from the worker thread.
        loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

    def on_event(kind: str, name: str | None = None) -> None:
        if kind == "tool":
            emit("tool", {"name": name or "unknown"})
        else:
            emit("generating", {})

    def run_blocking() -> None:
        try:
            result = service.process(request, user, on_event=on_event)
        except Exception:  # noqa: BLE001 — defensive; never stream internals
            logger.exception("SSE chat run failed")
            emit("error", {"message": "Something went wrong while preparing the response."})
            return
        if not result.ok:
            emit("error", {"message": _safe_error_message(result)})
            return
        context = getattr(result.context, "model_dump", lambda: {})()

        emit(
            "done",
            {
                "answer": result.answer,
                "context": context,
            },
        )

    threading.Thread(target=run_blocking, daemon=True).start()

    while True:
        try:
            kind, payload = await asyncio.wait_for(queue.get(), _KEEPALIVE_SECONDS)
        except asyncio.TimeoutError:
            yield ": ping\n\n"
            continue
        yield f"data: {json.dumps({'type': kind, **payload})}\n\n"
        if kind in ("done", "error"):
            break


def _wants_stream(accept: str | None) -> bool:
    return bool(accept and _STREAM_MEDIA_TYPE in accept.lower())


def _safe_error_message(result) -> str:
    """Return a user-safe message without leaking provider/API internals."""
    if getattr(result, "status_code", None) == 503:
        return "Grounded is still warming up. Please try again in a moment."
    return result.error or "Something went wrong while preparing the response."


@router.get("/chat/config", response_model=ChatConfig)
def chat_config(
    user: dict = Depends(get_current_user),
) -> ChatConfig:
    """Read-only chat configuration (explicitly authenticated)."""
    return ChatConfig()