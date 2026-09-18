"""Groq provider tests. Fake key only; the real Groq API is never called."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ai as ai_module
from app import auth
from app.config import Settings, get_settings
from app.database import get_session_local, init_db
from app.main import app

FAKE_KEY = "test-groq-key-DO-NOT-USE"


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def groq(client):
    """Settings override selecting Groq with a fake key."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="groq",
        groq_api_key=FAKE_KEY,
        groq_model="openai/gpt-oss-20b",
        frontend_url="http://localhost:5173",
    )
    return client


def _login(client: TestClient, sub: str) -> int:
    db = get_session_local()()
    try:
        user = auth.get_or_create_user(
            db, sub=sub, email=f"{sub}@example.com", name=sub, picture=None
        )
        user_id = user.id
        raw = auth.create_session(db, user_id)
    finally:
        db.close()
    client.cookies.set(auth.SESSION_COOKIE, raw)
    return user_id


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _ok(text="Hello from Groq."):
    return FakeResponse(200, {"choices": [{"message": {"content": text}}]})


def test_request_shape_and_extraction(groq, monkeypatch):
    _login(groq, "sub-shape")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return _ok()

    monkeypatch.setattr(httpx, "post", fake_post)
    res = groq.post(
        "/api/studio/ai",
        json={"action": "generate", "topic": "caching", "content_type": "technical"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mock"] is False
    assert body["text"] == "Hello from Groq."
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert seen["headers"]["Content-Type"] == "application/json"
    assert seen["json"]["model"] == "openai/gpt-oss-20b"
    assert seen["json"]["messages"][0]["role"] == "user"
    assert "caching" in seen["json"]["messages"][0]["content"]
    assert seen["timeout"] == 20


def test_missing_key_is_honest_501(client):
    _login(client, "sub-nokey")
    app.dependency_overrides[get_settings] = lambda: Settings(ai_provider="groq")
    try:
        res = client.post(
            "/api/studio/ai",
            json={"action": "generate", "topic": "caching", "content_type": "technical"},
        )
        assert res.status_code == 501
        assert res.json()["detail"] == "ai_provider_not_configured"
    finally:
        app.dependency_overrides.clear()


def test_http_errors_map_to_502(groq, monkeypatch):
    _login(groq, "sub-httperr")
    for code, detail in (
        (400, "groq_upstream_400"),
        (401, "groq_upstream_401"),
        (429, "groq_upstream_429"),
        (500, "groq_upstream_500"),
    ):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(code, {}))
        res = groq.post(
            "/api/studio/ai",
            json={"action": "generate", "topic": "caching", "content_type": "technical"},
        )
        assert res.status_code == 502
        assert res.json()["detail"] == detail
        assert "mock" not in res.text


def test_timeout_maps_to_502(groq, monkeypatch):
    _login(groq, "sub-timeout")

    def boom(*a, **k):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx, "post", boom)
    res = groq.post(
        "/api/studio/ai",
        json={"action": "generate", "topic": "caching", "content_type": "technical"},
    )
    assert res.status_code == 502
    assert res.json()["detail"] == "groq_unreachable"


def test_malformed_and_empty_responses_rejected(groq, monkeypatch):
    _login(groq, "sub-malformed")
    cases = [
        (FakeResponse(200, {"nope": []}), "groq_malformed_response"),
        (FakeResponse(200, {"choices": []}), "groq_malformed_response"),
        (
            FakeResponse(200, {"choices": [{"message": {"content": "   "}}]}),
            "groq_empty_response",
        ),
        (
            FakeResponse(200, {"choices": [{"message": {}}]}),
            "groq_malformed_response",
        ),
    ]
    for fake, detail in cases:
        def fake_post(*a, _f=fake, **k):
            return _f

        monkeypatch.setattr(httpx, "post", fake_post)
        res = groq.post(
            "/api/studio/ai",
            json={"action": "generate", "topic": "caching", "content_type": "technical"},
        )
        assert res.status_code == 502
        assert res.json()["detail"] == detail


def test_unknown_provider_still_honest_501(client):
    _login(client, "sub-unknown")
    app.dependency_overrides[get_settings] = lambda: Settings(ai_provider="weird")
    try:
        res = client.post(
            "/api/studio/ai",
            json={"action": "generate", "topic": "caching", "content_type": "technical"},
        )
        assert res.status_code == 501
        assert res.json()["detail"] == "ai_provider_not_configured"
    finally:
        app.dependency_overrides.clear()


def test_no_secret_leakage_in_groq_paths(groq, monkeypatch):
    _login(groq, "sub-leak")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(403, {"error": {"message": "bad key detail"}}))
    ok = groq.post(
        "/api/studio/ai",
        json={"action": "generate", "topic": "caching", "content_type": "technical"},
    )
    text = ok.text.lower()
    assert FAKE_KEY.lower() not in text
    assert "bad key detail" not in text


def test_mock_unchanged_and_default():
    provider = ai_module.get_ai_provider("mock")
    assert provider.name == "mock"
    out = provider.generate("anything")
    assert out["mock"] is True and out["provider"] == "mock"
    assert ai_module.get_ai_provider().name == "mock"
    try:
        ai_module.get_ai_provider("groq")
        raise AssertionError("expected ValueError without a key")
    except ValueError:
        pass
