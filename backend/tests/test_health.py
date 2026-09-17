"""M0 foundation tests: health, config safety, mocks, boundaries."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, create_app

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


def test_docs_gating(monkeypatch):
    import app.main as main_module

    # Development default: docs available.
    dev = TestClient(create_app())
    assert dev.get("/docs").status_code == 200
    assert dev.get("/health").status_code == 200

    # Production default: docs disabled, API unaffected.
    monkeypatch.setattr(
        main_module, "get_settings", lambda: Settings(app_env="production")
    )
    prod = TestClient(create_app())
    assert prod.get("/docs").status_code == 404
    assert prod.get("/redoc").status_code == 404
    assert prod.get("/openapi.json").status_code == 404
    assert prod.get("/health").status_code == 200

    # Explicit override wins over the environment default.
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(app_env="production", docs_enabled=True),
    )
    assert TestClient(create_app()).get("/docs").status_code == 200
