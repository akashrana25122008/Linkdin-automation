"""M6 Drafts workspace tests: list isolation, status, duplicate, delete."""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return TestClient(app)


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


def _create(client: TestClient, title: str, status: str = "draft") -> dict:
    res = client.post(
        "/api/studio/items",
        json={"title": title, "body": f"Body of {title}", "status": status},
    )
    assert res.status_code == 201
    return res.json()


def test_list_requires_auth(client):
    assert client.get("/api/studio/items").status_code == 401


def test_list_returns_own_content_newest_first(client):
    _login(client, "sub-lister")
    assert client.get("/api/studio/items").json()["items"] == []
    _create(client, "First")
    _create(client, "Second", status="approved")
    items = client.get("/api/studio/items").json()["items"]
    # Timestamps have second granularity, so assert membership, not order.
    assert {i["title"] for i in items} == {"First", "Second"}
    second = next(i for i in items if i["title"] == "Second")
    second = next(i for i in items if i["title"] == "Second")
    assert second["preview"] == "Body of Second"
    assert second["created_at"]


def test_list_hides_other_users_content(client):
    _login(client, "sub-alice")
    _create(client, "Alice private")
    client.cookies.clear()
    _login(client, "sub-bob")
    assert client.get("/api/studio/items").json()["items"] == []


def test_open_own_and_foreign_content(client):
    _login(client, "sub-owner")
    item_id = _create(client, "Mine")["id"]
    assert client.get(f"/api/studio/items/{item_id}").status_code == 200
    client.cookies.clear()
    _login(client, "sub-stranger")
    assert client.get(f"/api/studio/items/{item_id}").status_code == 404


def test_update_supported_status_and_reject_invalid(client):
    _login(client, "sub-status")
    item_id = _create(client, "Status flow", status="idea")["id"]
    res = client.patch(f"/api/studio/items/{item_id}", json={"status": "approved"})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
    for bad in ("published", "scheduled", "nope"):
        assert (
            client.patch(f"/api/studio/items/{item_id}", json={"status": bad}).status_code
            == 400
        )


def test_cannot_update_foreign_content(client):
    _login(client, "sub-owner")
    item_id = _create(client, "Mine")["id"]
    client.cookies.clear()
    _login(client, "sub-stranger")
    assert (
        client.patch(f"/api/studio/items/{item_id}", json={"title": "Hijack"}).status_code
        == 404
    )


def test_duplicate_creates_new_owned_copy(client):
    uid = _login(client, "sub-duper")
    original = _create(client, "Original")
    res = client.post(f"/api/studio/items/{original['id']}/duplicate")
    assert res.status_code == 201
    copy = res.json()
    assert copy["id"] != original["id"]
    assert copy["title"] == "Original Copy"
    assert copy["body"] == "Body of Original"
    assert copy["status"] == "draft"
    db = get_session_local()()
    try:
        from app.models import ContentItem

        row = db.query(ContentItem).filter_by(id=copy["id"]).one()
        assert row.user_id == uid
        assert db.query(ContentItem).filter_by(id=original["id"]).one() is not None
    finally:
        db.close()


def test_duplicate_of_published_starts_as_draft(client):
    """A copy must never inherit an unearned published/scheduled state."""
    _login(client, "sub-pubdup")
    item_id = _create(client, "Shipped", status="approved")["id"]
    published = client.post(f"/api/studio/items/{item_id}/publish").json()
    assert published["status"] == "published"
    copy = client.post(f"/api/studio/items/{item_id}/duplicate").json()
    assert copy["status"] == "draft"
    assert copy["linkedin_post_id"] is None
    assert copy["published_at"] is None
    # The copy is ordinary new work: it can be approved and published.
    client.patch(f"/api/studio/items/{copy['id']}", json={"status": "approved"})
    republished = client.post(f"/api/studio/items/{copy['id']}/publish").json()
    assert republished["status"] == "published"


def test_cannot_duplicate_foreign_content(client):
    _login(client, "sub-owner")
    item_id = _create(client, "Mine")["id"]
    client.cookies.clear()
    _login(client, "sub-stranger")
    assert client.post(f"/api/studio/items/{item_id}/duplicate").status_code == 404


def test_delete_own_content_and_it_disappears(client):
    _login(client, "sub-deleter")
    item_id = _create(client, "Doomed")["id"]
    assert client.delete(f"/api/studio/items/{item_id}").status_code == 200
    assert client.get(f"/api/studio/items/{item_id}").status_code == 404
    assert client.get("/api/studio/items").json()["items"] == []


def test_cannot_delete_foreign_content(client):
    _login(client, "sub-owner")
    item_id = _create(client, "Mine")["id"]
    client.cookies.clear()
    _login(client, "sub-stranger")
    assert client.delete(f"/api/studio/items/{item_id}").status_code == 404
    client.cookies.clear()
    _login(client, "sub-owner")
    assert client.get(f"/api/studio/items/{item_id}").status_code == 200
