"""M3 dashboard tests: auth, isolation, empty states, honesty."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app
from app.models import ContentItem


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return TestClient(app)


def _user_with_session(client: TestClient, sub: str, name: str):
    db = get_session_local()()
    try:
        user = auth.get_or_create_user(
            db, sub=sub, email=f"{sub}@example.com", name=name, picture=None
        )
        user_id = user.id
        raw = auth.create_session(db, user_id)
    finally:
        db.close()
    client.cookies.set(auth.SESSION_COOKIE, raw)
    return user_id


def _add_item(user_id: int, title: str, status: str, scheduled_at=None):
    db = get_session_local()()
    try:
        db.add(
            ContentItem(
                user_id=user_id,
                title=title,
                status=status,
                scheduled_at=scheduled_at,
            )
        )
        db.commit()
    finally:
        db.close()


def test_dashboard_rejects_unauthenticated(client):
    res = client.get("/api/dashboard")
    assert res.status_code == 401


def test_dashboard_empty_state_is_valid(client):
    _user_with_session(client, "sub-empty", "Empty User")
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    body = res.json()
    assert body["pipeline"] == {
        "idea": 0,
        "draft": 0,
        "approved": 0,
        "scheduled": 0,
        "published": 0,
    }
    assert body["upcoming"] == []
    assert body["performance"]["state"] == "not_connected"
    assert set(body["performance"].keys()) == {"state", "message"}
    assert "impression" not in res.text.lower()
    assert "follower" not in res.text.lower()
    assert body["brief"]["mock"] is True
    assert body["mock"] is True
    assert len(body["recommendations"]) >= 1
    assert all(r["mock"] is True for r in body["recommendations"])


def test_dashboard_scopes_data_to_authenticated_user(client):
    alice = _user_with_session(client, "sub-alice", "Alice")
    _add_item(alice, "Alice draft", "draft")
    _add_item(
        alice,
        "Alice scheduled",
        "scheduled",
        scheduled_at=datetime(2030, 5, 1, 9, 0, tzinfo=timezone.utc),
    )
    db = get_session_local()()
    try:
        bob = auth.get_or_create_user(
            db, sub="sub-bob", email="bob@example.com", name="Bob", picture=None
        )
        db.add(ContentItem(user_id=bob.id, title="Bob secret", status="draft"))
        db.commit()
    finally:
        db.close()

    body = client.get("/api/dashboard").json()
    assert body["pipeline"]["draft"] == 1
    assert body["pipeline"]["scheduled"] == 1
    assert [u["title"] for u in body["upcoming"]] == ["Alice scheduled"]
    assert "Bob secret" not in res_text(client)


def res_text(client: TestClient) -> str:
    return client.get("/api/dashboard").text


def test_dashboard_exposes_no_secrets(client):
    uid = _user_with_session(client, "sub-leak", "Leak Test")
    _add_item(uid, "Some item", "idea")
    text = client.get("/api/dashboard").text.lower()
    for forbidden in (
        "secret",
        "access_token",
        "refresh_token",
        "token_hash",
        "google_subject",
    ):
        assert forbidden not in text
