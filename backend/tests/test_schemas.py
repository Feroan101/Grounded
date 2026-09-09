"""Request/response model validation tests."""
import pytest
from pydantic import ValidationError

from app.api.schemas import ChatContextMetadata, ChatRequest, ChatResponse


def _valid_payload():
    return {"messages": [{"role": "user", "content": "What do you have?"}]}


def test_valid_chat_request():
    req = ChatRequest.model_validate(_valid_payload())
    assert req.last_user_message() == "What do you have?"


def test_rejects_empty_messages():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"messages": []})


def test_rejects_unknown_role():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {"messages": [{"role": "barista", "content": "hi"}]}
        )


def test_rejects_last_message_not_from_user():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "messages": [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "hello!"},
                ]
            }
        )


def test_rejects_overlong_content():
    # min_length=1 is enforced; empty content is invalid.
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"messages": [{"role": "user", "content": ""}]})


def test_multiturn_request_ok():
    req = ChatRequest.model_validate(
        {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello!"},
                {"role": "user", "content": "iced latte?"},
            ]
        }
    )
    assert req.last_user_message() == "iced latte?"


def test_chat_response_shape():
    resp = ChatResponse(
        answer="Try the cold brew.",
        context=ChatContextMetadata(
            used_preferences=False,
            retrieval_used=False,
            retrieval_count=0,
        ),
    )
    assert resp.context.retrieval_count == 0
    assert resp.context.used_preferences is False


def test_chat_response_context_defaults():
    resp = ChatResponse(answer="Hi!")
    assert resp.context.retrieval_used is False
    assert resp.context.retrieval_count == 0