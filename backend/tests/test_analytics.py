"""M11 Analytics tests: real application data only, never engagement metrics."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app
from app.models import ContentItem

FORBIDDEN_KEYS = {
    "impressions",
    "impression",
    "reactions",
    "comments",
    "shares",
    "engagement_rate",
    "reach",
    "ctr",
    "followers",
    "likes",
}


def _assert_no_metric_values(payload) -> None:
    """No fabricated engagement numbers anywhere in the structure."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key.lower() not in FORBIDDEN_KEYS, key
            _assert_no_metric_values(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_no_metric_values(value)


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


def _seed(user_id: int, title: str, status: str, days_ago=None, content_type="technical"):
    db = get_session_local()()
    try:
        published = None
        if status == "published":
            published = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                days=days_ago if days_ago is not None else 0
            )
        db.add(
            ContentItem(
                user_id=user_id,
                title=title,
                body=f"Body of {title}",
                content_type=content_type,
                status=status,
                linkedin_post_id=f"real-post-{title}" if status == "published" else None,
                published_at=published,
            )
        )
        db.commit()
    finally:
        db.close()


def test_analytics_requires_auth(client):
    assert client.get("/api/analytics/overview").status_code == 401
    assert client.get("/api/analytics/posts").status_code == 401


def test_empty_analytics_is_valid(client):
    _login(client, "sub-empty")
    for path in ("/api/analytics/overview", "/api/analytics/posts"):
        res = client.get(path)
        assert res.status_code == 200
        assert res.json()["source"] == "APPLICATION_DATA"
        _assert_no_metric_values(res.json())
    body = client.get("/api/analytics/overview").json()
    assert body["published_in_range"] == 0
    assert body["status_counts"] == {}
    assert body["by_content_type"] == {}
    assert sum(b["count"] for b in body["weekly_activity"]) == 0
    assert body["linkedin"]["engagement"]["state"] == "unavailable"
    assert client.get("/api/analytics/posts").json()["items"] == []


def test_counts_come_from_real_rows(client):
    uid = _login(client, "sub-counts")
    _seed(uid, "new-1", "published", days_ago=1)
    _seed(uid, "new-2", "published", days_ago=2, content_type="tutorial")
    _seed(uid, "old", "published", days_ago=60)
    _seed(uid, "sched-1", "scheduled")
    _seed(uid, "sched-2", "scheduled")
    _seed(uid, "failed-1", "failed")
    _seed(uid, "draft-1", "draft")

    body = client.get("/api/analytics/overview?days=30").json()
    assert body["status_counts"] == {
        "published": 3,
        "scheduled": 2,
        "failed": 1,
        "draft": 1,
    }
    assert body["published_in_range"] == 2
    assert body["posts_per_week"] == round(2 / (30 / 7), 1)
    assert body["by_content_type"] == {"technical": 1, "tutorial": 1}
    assert sum(b["count"] for b in body["weekly_activity"]) == 2

    week = client.get("/api/analytics/overview?days=7").json()
    assert week["published_in_range"] == 2
    assert len(week["weekly_activity"]) == 7

    everything = client.get("/api/analytics/overview?days=all").json()
    assert everything["published_in_range"] == 3
    assert everything["posts_per_week"] is None


def test_posts_history_and_filters(client):
    uid = _login(client, "sub-history")
    _seed(uid, "pub", "published", days_ago=1)
    _seed(uid, "sched", "scheduled")
    posts = client.get("/api/analytics/posts").json()["items"]
    assert {p["status"] for p in posts} == {"published", "scheduled"}
    assert posts[0]["linkedin_post_id"] == "real-post-pub"
    assert posts[0]["published_at"]

    only_pub = client.get("/api/analytics/posts?post_status=published").json()
    assert [p["title"] for p in only_pub["items"]] == ["pub"]
    assert only_pub["engagement"] == "unavailable"

    assert client.get("/api/analytics/posts?post_status=bogus").status_code == 400
    assert client.get("/api/analytics/overview?days=forever").status_code == 400


def test_user_isolation(client):
    alice = _login(client, "sub-alice")
    _seed(alice, "Alice post", "published", days_ago=1)
    client.cookies.clear()
    _login(client, "sub-bob")
    assert client.get("/api/analytics/overview").json()["published_in_range"] == 0
    assert client.get("/api/analytics/posts").json()["items"] == []


def test_strategy_timezone_respected(client):
    from app.models import UserStrategy

    uid = _login(client, "sub-tz")
    _seed(uid, "TZ post", "published", days_ago=1)
    db = get_session_local()()
    try:
        db.add(UserStrategy(user_id=uid, timezone="Asia/Kolkata"))
        db.commit()
    finally:
        db.close()
    body = client.get("/api/analytics/overview").json()
    assert body["timezone"] == "Asia/Kolkata"
