"""Authentication dependency boundary tests.

These verify that:
  - requests without a token are rejected with 401
  - malformed tokens are rejected with 401
  - a verified token yields the UID derived from the token (never the client)
"""
from starlette.testclient import TestClient

from app.main import app
from app.token_verifier import verify_firebase_token


def _client():
    return TestClient(app)


def test_chat_requires_auth():
    client = _client()
    resp = client.post(
        "/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert resp.status_code == 401


def test_chat_rejects_malformed_header():
    client = _client()
    resp = client.post(
        "/api/chat",
        headers={"Authorization": "Basic abc"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_chat_rejects_bad_token():
    client = _client()
    resp = client.post(
        "/api/chat",
        headers={"Authorization": "Bearer not.a.real.token"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    # Real verification against Google's JWKS should reject this.
    assert resp.status_code == 401


def test_chat_config_requires_auth():
    client = _client()
    resp = client.get("/api/chat/config")
    assert resp.status_code == 401


def test_verifier_derives_uid_from_sub(monkeypatch):
    """The dependency must derive the UID from the verified token's `sub`."""
    fake_payload = {"sub": "uid-123", "email": "a@b.com"}

    import google.oauth2.id_token as id_token

    monkeypatch.setattr(
        id_token, "verify_token", lambda *a, **k: dict(fake_payload)
    )
    decoded = verify_firebase_token("fake-token")
    assert decoded["uid"] == "uid-123"
    assert decoded["email"] == "a@b.com"