"""M10 LinkedIn publishing tests. Fake tokens only; LinkedIn never called."""

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import auth
from app import publishing as publishing_module
from app.config import Settings, get_settings
from app.database import get_session_local, init_db
from app.linkedin_oauth import encrypt_token
from app.main import app
from app.models import ContentItem, LinkedInAccount

LIVE_KEY = Fernet.generate_key().decode()


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def live(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        linkedin_mode="live",
        linkedin_client_id="test-client-id",
        linkedin_client_secret="test-client-secret",
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


def _approved(client: TestClient, title: str, body: str = "Publishable body text.") -> int:
    res = client.post(
        "/api/studio/items",
        json={"title": title, "body": body, "status": "approved"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def _live_account(user_id: int, scopes=("w_member_social",), mock=False):
    settings = Settings(linkedin_mode="live", linkedin_token_key=LIVE_KEY)
    db = get_session_local()()
    try:
        import json

        db.add(
            LinkedInAccount(
                user_id=user_id,
                linkedin_member_id="li-member-1",
                linkedin_name="Linked Member",
                access_token_encrypted=encrypt_token(settings, "fake-test-token")
                if not mock
                else "",
                scopes=json.dumps(list(scopes)),
                is_mock=mock,
            )
        )
        db.commit()
    finally:
        db.close()


class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = httpx.Headers(headers or {})


def test_publish_requires_auth(client):
    assert client.post("/api/studio/items/1/publish").status_code == 401


def test_unapproved_rejected_and_foreign_forbidden(client):
    _login(client, "sub-gate")
    draft = client.post(
        "/api/studio/items", json={"title": "Raw", "status": "draft"}
    ).json()["id"]
    assert client.post(f"/api/studio/items/{draft}/publish").status_code == 409
    idea = client.post(
        "/api/studio/items", json={"title": "Idea", "status": "idea"}
    ).json()["id"]
    assert client.post(f"/api/studio/items/{idea}/publish").status_code == 409

    owned = _approved(client, "Mine")
    client.cookies.clear()
    _login(client, "sub-stranger")
    assert client.post(f"/api/studio/items/{owned}/publish").status_code == 404
    assert client.post("/api/studio/items/999999/publish").status_code == 404


def test_invalid_content_rejected(client):
    _login(client, "sub-content")
    empty = _approved(client, "Empty", body="   ")
    assert client.post(f"/api/studio/items/{empty}/publish").status_code == 422


def test_no_connection_rejected_in_live_mode(live):
    _login(live, "sub-noconn")
    item_id = _approved(live, "No account")
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 409
    assert res.json()["detail"] == "linkedin_not_connected"


def test_missing_scope_rejected_without_http_call(live, monkeypatch):
    uid = _login(live, "sub-noscope")
    _live_account(uid, scopes=("openid", "profile", "email"))
    item_id = _approved(live, "No scope")
    calls = []
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: calls.append((a, k)) or FakeResponse(201)
    )
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 409
    assert res.json()["detail"] == "missing_scope"
    assert calls == []


def test_mock_publish_never_calls_linkedin(client, monkeypatch):
    _login(client, "sub-mock")
    item_id = _approved(client, "Mock me")
    calls = []
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: calls.append((a, k)) or FakeResponse(201)
    )
    res = client.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 200
    body = res.json()
    assert body["mock"] is True
    assert body["status"] == "published"
    assert body["linkedin_post_id"] == f"mock:linkedin-post:{item_id}"
    assert body["published_at"]
    assert calls == []
    for forbidden in ("access_token", "client_secret", "encryption_key"):
        assert forbidden not in res.text.lower()


def test_mock_account_in_live_mode_stays_mock(live, monkeypatch):
    uid = _login(live, "sub-mocklive")
    _live_account(uid, mock=True)
    item_id = _approved(live, "Mock row")
    calls = []
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: calls.append((a, k)) or FakeResponse(201)
    )
    body = live.post(f"/api/studio/items/{item_id}/publish").json()
    assert body["mock"] is True
    assert body["linkedin_post_id"].startswith("mock:")
    assert calls == []


def test_real_publish_uses_server_token_and_captures_id(live, monkeypatch):
    uid = _login(live, "sub-real")
    _live_account(uid)
    item_id = _approved(live, "Real thing", body="Approved text to publish.")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        seen["json"] = json
        return FakeResponse(201, {"X-RestLi-Id": "urn:li:share:12345"})

    monkeypatch.setattr(httpx, "post", fake_post)
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 200
    body = res.json()
    assert body["mock"] is False
    assert body["status"] == "published"
    assert body["linkedin_post_id"] == "urn:li:share:12345"
    assert seen["url"] == "https://api.linkedin.com/v2/ugcPosts"
    assert seen["headers"]["Authorization"] == "Bearer fake-test-token"
    assert seen["headers"]["X-Restli-Protocol-Version"] == "2.0.0"
    assert seen["json"]["author"] == "urn:li:person:li-member-1"
    assert (
        seen["json"]["specificContent"]["com.linkedin.ugc.ShareContent"][
            "shareCommentary"
        ]["text"]
        == "Approved text to publish."
    )
    assert "fake-test-token" not in res.text
    assert "test-client-secret" not in res.text


def test_upstream_and_rate_limit_failures(live, monkeypatch):
    uid = _login(live, "sub-fail")
    _live_account(uid)
    for code, detail in (
        (403, "linkedin_upstream_403"),
        (429, "linkedin_rate_limited"),
        (500, "linkedin_upstream_500"),
    ):
        item_id = _approved(live, f"Fail {code}")
        monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(code))
        res = live.post(f"/api/studio/items/{item_id}/publish")
        assert res.status_code == 502
        assert res.json()["detail"] == detail
        db = get_session_local()()
        try:
            row = db.query(ContentItem).filter_by(id=item_id).one()
            assert row.status == "failed"
            assert row.publish_error == detail
            assert row.linkedin_post_id is None
        finally:
            db.close()


def test_timeout_leaves_status_untouched(live, monkeypatch):
    uid = _login(live, "sub-timeout")
    _live_account(uid)
    item_id = _approved(live, "Ambiguous")

    def boom(*a, **k):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx, "post", boom)
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 502
    assert res.json()["detail"] == "linkedin_timeout_unknown"
    db = get_session_local()()
    try:
        row = db.query(ContentItem).filter_by(id=item_id).one()
        assert row.status == "approved"
        assert row.publish_error == "linkedin_timeout_unknown"
    finally:
        db.close()


def test_missing_post_id_not_marked_published(live, monkeypatch):
    uid = _login(live, "sub-noid")
    _live_account(uid)
    item_id = _approved(live, "No header")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(201, {}))
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 502
    db = get_session_local()()
    try:
        row = db.query(ContentItem).filter_by(id=item_id).one()
        assert row.status != "published"
    finally:
        db.close()


def test_retry_after_publish_blocked(live, monkeypatch):
    uid = _login(live, "sub-retry")
    _live_account(uid)
    item_id = _approved(live, "Once")
    calls = []
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **k: calls.append(1) or FakeResponse(201, {"X-RestLi-Id": "urn:li:share:1"}),
    )
    assert live.post(f"/api/studio/items/{item_id}/publish").status_code == 200
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 409
    assert res.json()["detail"] == "already_published"
    assert len(calls) == 1


def test_failed_can_retry_and_succeed(live, monkeypatch):
    uid = _login(live, "sub-retryfail")
    _live_account(uid)
    item_id = _approved(live, "Second chance")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(500))
    assert live.post(f"/api/studio/items/{item_id}/publish").status_code == 502
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: FakeResponse(201, {"X-RestLi-Id": "urn:li:share:9"})
    )
    res = live.post(f"/api/studio/items/{item_id}/publish")
    assert res.status_code == 200
    assert res.json()["linkedin_post_id"] == "urn:li:share:9"
