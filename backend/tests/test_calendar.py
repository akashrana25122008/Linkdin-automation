"""M7 Calendar tests: schedule/reschedule/unschedule, ranges, isolation."""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app

TZ = "Asia/Kolkata"


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


def _future(days: float = 2.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _approved(client: TestClient, title: str) -> int:
    res = client.post(
        "/api/studio/items",
        json={"title": title, "body": f"Body of {title}", "status": "approved"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def _range(days: int = 30) -> str:
    # ISO offsets contain '+', which must be percent-encoded in query strings
    # (a raw '+' decodes to a space). The frontend must encode these too.
    now = datetime.now(timezone.utc)
    start = quote((now - timedelta(days=1)).isoformat(), safe="")
    end = quote((now + timedelta(days=days)).isoformat(), safe="")
    return f"start={start}&end={end}"


def test_calendar_requires_auth(client):
    assert client.get("/api/studio/scheduled?start=x&end=y").status_code == 401
    assert (
        client.post("/api/studio/items/1/schedule", json={}).status_code == 401
    )


def test_user_sees_own_scheduled_content(client):
    _login(client, "sub-cal")
    item_id = _approved(client, "Talk")
    res = client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": _future(), "timezone": TZ},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "scheduled"
    assert body["scheduled_tz"] == TZ
    assert body["scheduled_at"].endswith("+00:00")

    listed = client.get(f"/api/studio/scheduled?{_range()}").json()["items"]
    assert [i["id"] for i in listed] == [item_id]


def test_cross_user_schedule_isolation(client):
    _login(client, "sub-owner")
    item_id = _approved(client, "Private")
    client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": _future(), "timezone": TZ},
    )
    client.cookies.clear()
    _login(client, "sub-stranger")
    assert client.get(f"/api/studio/scheduled?{_range()}").json()["items"] == []
    assert (
        client.post(
            f"/api/studio/items/{item_id}/schedule",
            json={"scheduled_at": _future(), "timezone": TZ},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/studio/items/{item_id}/reschedule",
            json={"scheduled_at": _future(), "timezone": TZ},
        ).status_code
        == 404
    )
    assert (
        client.post(f"/api/studio/items/{item_id}/unschedule").status_code == 404
    )


def test_unapproved_draft_cannot_be_scheduled(client):
    _login(client, "sub-draft")
    res = client.post("/api/studio/items", json={"title": "Raw", "status": "draft"})
    item_id = res.json()["id"]
    bad = client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": _future(), "timezone": TZ},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "approval_required"


def test_malformed_and_invalid_timezone_rejected(client):
    _login(client, "sub-bad")
    item_id = _approved(client, "Bad input")
    base = f"/api/studio/items/{item_id}/schedule"
    assert client.post(base, json={}).status_code == 400
    assert (
        client.post(
            base, json={"scheduled_at": "not-a-date", "timezone": TZ}
        ).status_code
        == 400
    )
    assert (
        client.post(
            base, json={"scheduled_at": _future(), "timezone": "Mars/Olympus"}
        ).status_code
        == 400
    )
    naive = (datetime.now(timezone.utc) + timedelta(days=2)).replace(tzinfo=None)
    assert (
        client.post(
            base, json={"scheduled_at": naive.isoformat(), "timezone": TZ}
        ).status_code
        == 400
    )


def test_past_schedule_rejected(client):
    _login(client, "sub-past")
    item_id = _approved(client, "Too late")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    res = client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": past, "timezone": TZ},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "past_time"


def test_schedule_persists_with_utc_conversion(client):
    _login(client, "sub-tz")
    item_id = _approved(client, "TZ check")
    # 12:00 at +05:30 == 06:30 UTC.
    res = client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": "2030-06-01T12:00:00+05:30", "timezone": TZ},
    )
    assert res.status_code == 200
    assert res.json()["scheduled_at"] == "2030-06-01T06:30:00+00:00"


def test_reschedule_updates_same_item(client):
    _login(client, "sub-re")
    item_id = _approved(client, "Movable")
    client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": _future(2), "timezone": TZ},
    )
    res = client.post(
        f"/api/studio/items/{item_id}/reschedule",
        json={"scheduled_at": _future(9), "timezone": "America/New_York"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "scheduled"
    assert res.json()["scheduled_tz"] == "America/New_York"
    db = get_session_local()()
    try:
        from app.models import ContentItem

        assert db.query(ContentItem).count() == 1
    finally:
        db.close()


def test_reschedule_requires_scheduled_state(client):
    _login(client, "sub-rebad")
    item_id = _approved(client, "Not scheduled")
    res = client.post(
        f"/api/studio/items/{item_id}/reschedule",
        json={"scheduled_at": _future(), "timezone": TZ},
    )
    assert res.status_code == 400


def test_unschedule_restores_approved_without_deleting(client):
    _login(client, "sub-un")
    item_id = _approved(client, "Unscheduled soon")
    client.post(
        f"/api/studio/items/{item_id}/schedule",
        json={"scheduled_at": _future(), "timezone": TZ},
    )
    res = client.post(f"/api/studio/items/{item_id}/unschedule")
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
    assert res.json()["scheduled_at"] is None
    assert client.get(f"/api/studio/items/{item_id}").status_code == 200
    assert client.get(f"/api/studio/scheduled?{_range()}").json()["items"] == []


def test_range_query_is_bounded(client):
    _login(client, "sub-range")
    near = _approved(client, "Near")
    far = _approved(client, "Far")
    client.post(
        f"/api/studio/items/{near}/schedule",
        json={"scheduled_at": _future(2), "timezone": TZ},
    )
    client.post(
        f"/api/studio/items/{far}/schedule",
        json={"scheduled_at": _future(60), "timezone": TZ},
    )
    items = client.get(f"/api/studio/scheduled?{_range(30)}").json()["items"]
    assert [i["title"] for i in items] == ["Near"]
    now = datetime.now(timezone.utc)
    wide = (
        f"start={quote((now - timedelta(days=1)).isoformat(), safe='')}"
        f"&end={quote((now + timedelta(days=100)).isoformat(), safe='')}"
    )
    wide_res = client.get(f"/api/studio/scheduled?{wide}")
    assert wide_res.status_code == 400
    assert wide_res.json()["detail"] == "range_too_large"
