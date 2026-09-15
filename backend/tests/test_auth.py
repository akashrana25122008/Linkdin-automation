"""M1 authentication tests. Real Google OAuth needs credentials: NOT VERIFIED."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app
from app.models import Session as SessionModel
from app.models import User


@pytest.fixture()
def client(tmp_path):
    # File-backed temp DB: shared across the TestClient request thread,
    # unlike :memory: (which gives every connection its own empty database).
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return TestClient(app)


def _db():
    return get_session_local()()


def _login(client: TestClient, user_id: int) -> str:
    db = _db()
    try:
        raw = auth.create_session(db, user_id)
    finally:
        db.close()
    client.cookies.set(auth.SESSION_COOKIE, raw)
    return raw


def _make_user(**overrides) -> User:
    db = _db()
    try:
        return auth.get_or_create_user(
            db,
            sub=overrides.get("sub", "google-sub-1"),
            email=overrides.get("email", "user@example.com"),
            name=overrides.get("name", "Test User"),
            picture=overrides.get("picture", "https://example.com/pic.png"),
        )
    finally:
        db.close()


def test_me_unauthenticated_is_401(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.json()["detail"] == "unauthenticated"


def test_google_status_honest_without_credentials(client):
    res = client.get("/api/auth/google/status")
    assert res.status_code == 200
    assert res.json() == {"google_oauth": "NOT CONFIGURED"}


def test_login_start_without_credentials_is_honest(client):
    res = client.get("/api/auth/google/login")
    assert res.status_code == 501
    assert res.json()["detail"] == "google_oauth_not_configured"


def test_user_created_then_found(client):
    first = _make_user()
    second = _make_user(name="Renamed User")
    assert first.id == second.id
    db = _db()
    try:
        assert db.query(User).count() == 1
        assert db.query(User).one().name == "Renamed User"
    finally:
        db.close()


def test_authenticated_me_returns_public_profile_only(client):
    user = _make_user()
    _login(client, user.id)
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == "user@example.com"
    assert body["name"] == "Test User"
    assert "google_subject_id" not in body
    assert "token" not in " ".join(body.keys()).lower()
    assert "secret" not in res.text.lower()


def test_tampered_session_cookie_is_401(client):
    _make_user()
    client.cookies.set(auth.SESSION_COOKIE, "forged-token-value")
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session_is_401(client):
    user = _make_user()
    raw = _login(client, user.id)
    db = _db()
    try:
        session = (
            db.query(SessionModel)
            .filter_by(token_hash=auth._hash_token(raw))
            .one()
        )
        session.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_invalidates_session(client):
    user = _make_user()
    _login(client, user.id)
    assert client.get("/api/auth/me").status_code == 200
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert client.get("/api/auth/me").status_code == 401
    db = _db()
    try:
        assert db.query(SessionModel).count() == 0
    finally:
        db.close()


def test_callback_state_mismatch_redirects_to_error(client):
    res = client.get(
        "/api/auth/google/callback?code=x&state=wrong",
        follow_redirects=False,
    )
    assert res.status_code in (302, 307)
    assert res.headers["location"].endswith("/login?error=state")


def test_callback_cancelled_login_redirects(client):
    res = client.get(
        "/api/auth/google/callback?error=access_denied",
        follow_redirects=False,
    )
    assert res.status_code in (302, 307)
    assert res.headers["location"].endswith("/login?error=cancelled")


def test_authorize_url_has_client_id_but_no_secret():
    from app.config import Settings

    url = auth.build_authorize_url(
        Settings(
            google_client_id="public-id",
            google_client_secret="super-secret",
            google_redirect_uri="http://localhost:8000/api/auth/google/callback",
        ),
        "state-123",
    )
    assert "client_id=public-id" in url
    assert "super-secret" not in url
    assert "state=state-123" in url
