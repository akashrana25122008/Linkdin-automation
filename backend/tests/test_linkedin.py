"""M9 LinkedIn OAuth tests. Fake test-only credentials; LinkedIn never called."""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import auth
from app.config import Settings, get_settings
from app.database import get_session_local, init_db
from app.main import app
from app.models import LinkedInAccount, LinkedInOAuthState


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    yield TestClient(app)
    app.dependency_overrides.clear()


LIVE_KEY = Fernet.generate_key().decode()


@pytest.fixture()
def live(client):
    """Override settings with deterministic fake live configuration."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        linkedin_mode="live",
        linkedin_client_id="test-client-id",
        linkedin_client_secret="test-client-secret",
        linkedin_redirect_uri="http://localhost:8000/api/linkedin/callback",
        linkedin_scopes="openid profile email",
        linkedin_token_key=LIVE_KEY,
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


def _fake_linkedin(monkeypatch, member="li-member-1", fail_exchange=False):
    calls = {"post": 0, "get": 0}

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, data=None, timeout=None):
        calls["post"] += 1
        if fail_exchange:
            return FakeResponse(400, {"error": "invalid_grant"})
        return FakeResponse(
            200, {"access_token": "test-access-token-1", "expires_in": 3600}
        )

    def fake_get(url, headers=None, timeout=None):
        calls["get"] += 1
        return FakeResponse(
            200, {"sub": member, "name": "Linked Member", "email": "li@example.com"}
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)
    return calls


def _connect_state(client: TestClient) -> str:
    res = client.get("/api/linkedin/connect", follow_redirects=False)
    assert res.status_code in (302, 307)
    query = parse_qs(urlparse(res.headers["location"]).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["test-client-id"]
    assert "test-client-secret" not in res.headers["location"]
    assert query["state"][0]
    return query["state"][0]


def _callback(client: TestClient, **params) -> str:
    res = client.get("/api/linkedin/callback", params=params, follow_redirects=False)
    assert res.status_code in (302, 307)
    return res.headers["location"]


def test_auth_required(client):
    assert client.get("/api/linkedin/status").status_code == 401
    assert client.get("/api/linkedin/connect").status_code == 401
    assert client.delete("/api/linkedin/connection").status_code == 401


def test_unconfigured_live_mode_is_honest(client):
    _login(client, "sub-unconf")
    app.dependency_overrides[get_settings] = lambda: Settings(linkedin_mode="live")
    try:
        res = client.get("/api/linkedin/connect", follow_redirects=False)
        assert res.status_code == 501
        assert res.json()["detail"] == "linkedin_not_configured"
        body = client.get("/api/linkedin/status").json()
        assert body == {
            "connected": False,
            "mode": "live",
            "mock": False,
            "configured": False,
        }
    finally:
        app.dependency_overrides.clear()


def test_state_generated_and_unpredictable(live):
    _login(live, "sub-state")
    first = _connect_state(live)
    second = _connect_state(live)
    assert first and second and first != second


def test_state_bound_to_user(live):
    _login(live, "sub-a")
    state = _connect_state(live)
    live.cookies.clear()
    _login(live, "sub-b")
    location = _callback(live, code="x", state=state)
    assert location.endswith("?linkedin=state")


def test_expired_invalid_reused_state_rejected(live, monkeypatch):
    _login(live, "sub-exp")
    state = _connect_state(live)
    db = get_session_local()()
    try:
        row = db.query(LinkedInOAuthState).one()
        row.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()
    finally:
        db.close()
    assert _callback(live, code="x", state=state).endswith("?linkedin=state")
    assert _callback(live, code="x", state="bogus").endswith("?linkedin=state")

    _fake_linkedin(monkeypatch, fail_exchange=True)
    fresh = _connect_state(live)
    assert _callback(live, code="x", state=fresh).endswith("?linkedin=error")
    assert _callback(live, code="x", state=fresh).endswith("?linkedin=state")


def test_cancelled_and_missing_code(live):
    _login(live, "sub-cancel")
    assert _callback(live, error="access_denied").endswith("?linkedin=cancelled")
    state = _connect_state(live)
    assert _callback(live, state=state).endswith("?linkedin=error")
    db = get_session_local()()
    try:
        assert db.query(LinkedInAccount).count() == 0
    finally:
        db.close()


def test_full_flow_stores_encrypted_connection(live, monkeypatch):
    uid = _login(live, "sub-full")
    calls = _fake_linkedin(monkeypatch)
    location = _callback(live, code="auth-code", state=_connect_state(live))
    assert location.endswith("?linkedin=connected")
    assert calls == {"post": 1, "get": 1}

    db = get_session_local()()
    try:
        account = db.query(LinkedInAccount).filter_by(user_id=uid).one()
        assert account.linkedin_member_id == "li-member-1"
        assert account.access_token_encrypted
        assert "test-access-token-1" not in account.access_token_encrypted
        decrypted = Fernet(LIVE_KEY).decrypt(
            account.access_token_encrypted.encode()
        ).decode()
        assert decrypted == "test-access-token-1"
    finally:
        db.close()

    body = live.get("/api/linkedin/status").json()
    assert body["connected"] is True
    assert body["member_name"] == "Linked Member"
    assert body["member_id"] == "li-member-1"
    assert body["mock"] is False
    text = live.get("/api/linkedin/status").text.lower()
    for forbidden in ("test-access-token-1", "test-client-secret", "access_token"):
        assert forbidden not in text


def test_exchange_failure_creates_nothing(live, monkeypatch):
    _login(live, "sub-fail")
    _fake_linkedin(monkeypatch, fail_exchange=True)
    location = _callback(live, code="bad-code", state=_connect_state(live))
    assert location.endswith("?linkedin=error")
    db = get_session_local()()
    try:
        assert db.query(LinkedInAccount).count() == 0
    finally:
        db.close()


def test_cross_user_isolation(live, monkeypatch):
    _fake_linkedin(monkeypatch)
    _login(live, "sub-owner")
    _callback(live, code="c", state=_connect_state(live))
    live.cookies.clear()
    _login(live, "sub-stranger")
    assert live.get("/api/linkedin/status").json()["connected"] is False
    assert live.delete("/api/linkedin/connection").status_code == 404
    live.cookies.clear()
    _login(live, "sub-owner")
    assert live.get("/api/linkedin/status").json()["connected"] is True


def test_reconnect_updates_same_row(live, monkeypatch):
    uid = _login(live, "sub-re")
    _fake_linkedin(monkeypatch)
    _callback(live, code="c1", state=_connect_state(live))
    db = get_session_local()()
    try:
        first_id = db.query(LinkedInAccount).filter_by(user_id=uid).one().id
    finally:
        db.close()
    _callback(live, code="c2", state=_connect_state(live))
    db = get_session_local()()
    try:
        rows = db.query(LinkedInAccount).filter_by(user_id=uid).all()
        assert len(rows) == 1 and rows[0].id == first_id
    finally:
        db.close()


def test_disconnect_clears_connection(live, monkeypatch):
    _login(live, "sub-disc")
    _fake_linkedin(monkeypatch)
    _callback(live, code="c", state=_connect_state(live))
    assert live.delete("/api/linkedin/connection").json() == {"status": "ok"}
    assert live.get("/api/linkedin/status").json()["connected"] is False
    assert live.delete("/api/linkedin/connection").status_code == 404


def test_mock_mode_never_calls_linkedin(client, monkeypatch):
    _login(client, "sub-mock")
    calls = _fake_linkedin(monkeypatch)
    body = client.get("/api/linkedin/status").json()
    assert body == {"connected": False, "mode": "mock", "mock": True, "configured": False}
    res = client.get("/api/linkedin/connect", follow_redirects=False)
    assert res.status_code == 409
    assert res.json()["detail"] == "linkedin_mock_mode"
    mock = client.post("/api/linkedin/mock/connect").json()
    assert mock["connected"] is True and mock["mock"] is True
    assert mock["member_name"] == "Mock Member"
    assert "access_token" not in client.get("/api/linkedin/status").text
    assert client.delete("/api/linkedin/connection").json() == {"status": "ok"}
    assert client.get("/api/linkedin/status").json()["connected"] is False
    assert calls == {"post": 0, "get": 0}
