"""M0 foundation tests: health, config safety, mocks, boundaries."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_without_secrets():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True
    joined = " ".join(body.keys()).lower()
    assert "secret" not in joined
    assert "token" not in joined


def test_api_health_alias():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_status_flags_are_honest():
    res = client.get("/api/status")
    assert res.status_code == 200
    body = res.json()
    assert body["google_auth"] == "NOT CONFIGURED"
    assert body["linkedin_publishing"] == "NOT CONFIGURED"
    assert body["ai"] == "MOCK"
    assert body["research"] == "MOCK"
