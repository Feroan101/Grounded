"""Health endpoint tests — the health endpoint must NOT require auth."""
from starlette.testclient import TestClient

from app.main import app


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["environment"] in {"development", "production"}


def test_health_no_auth_required():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "Authorization" not in resp.request.headers