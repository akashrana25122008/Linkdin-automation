"""M12 Learning tests: honesty gates, determinism, isolation, AI limits."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import ai as ai_module
from app import auth
from app.database import get_session_local, init_db
from app.main import app
from app.models import ContentItem, UserStrategy

METRIC_KEYS = {
    "impressions",
    "reactions",
    "comments",
    "shares",
    "engagement_rate",
    "reach",
    "ctr",
    "followers",
}


def _walk(obj) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            assert key.lower() not in METRIC_KEYS, key
            _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            _walk(value)


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


def _publish(user_id: int, title: str, content_type: str, days_ago: int = 1):
    db = get_session_local()()
    try:
        db.add(
            ContentItem(
                user_id=user_id,
                title=title,
                body=f"Body of {title}",
                content_type=content_type,
                status="published",
                linkedin_post_id=f"post-{title}",
                published_at=datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(days=days_ago),
            )
        )
        db.commit()
    finally:
        db.close()


def _strategy(user_id: int, **fields):
    import json

    db = get_session_local()()
    try:
        row = UserStrategy(user_id=user_id)
        for key, value in fields.items():
            setattr(
                row, key, json.dumps(value) if isinstance(value, list) else value
            )
        db.add(row)
        db.commit()
    finally:
        db.close()


def test_learning_requires_auth(client):
    assert client.get("/api/learning/insights").status_code == 401


def test_empty_state_is_honest(client):
    _login(client, "sub-empty")
    body = client.get("/api/learning/insights").json()
    assert body["state"] == "INSUFFICIENT_DATA"
    assert body["insights"] == []
    assert body["recommendations"] == []
    assert body["coverage"]["published_total"] == 0
    assert "hasn't started yet" in body["message"]
    assert body["ai_summary"] is None
    _walk(body)


def test_insufficient_data_blocks_patterns(client):
    user_id = _login(client, "sub-few")
    _publish(user_id, "one", "technical")
    _publish(user_id, "two", "technical")
    body = client.get("/api/learning/insights").json()
    assert body["state"] == "INSUFFICIENT_DATA"
    assert body["coverage"]["published_total"] == 2
    assert "2 published posts" in body["message"]
    assert body["insights"] == []
    _walk(body)


def test_deterministic_patterns_and_alignment(client):
    uid = _login(client, "sub-patterns")
    for i in range(7):
        _publish(uid, f"tech-{i}", "technical")
    _publish(uid, "tut-0", "tutorial")
    _strategy(
        uid,
        posting_frequency="weekly",
        content_types=["tutorial", "opinion"],
    )
    body = client.get("/api/learning/insights").json()
    assert body["state"] == "SUPPORTED_PATTERN"
    assert body["coverage"]["published_total"] == 8

    by_type = {i["type"]: i for i in body["insights"]}
    assert "7 technical" in by_type["content_distribution"]["evidence"]
    assert "1 tutorial" in by_type["content_distribution"]["evidence"]

    variety = by_type["content_variety"]
    assert "7 of your last 8" in variety["evidence"]
    assert variety["confidence"] == "SUPPORTED_PATTERN"
    assert variety["source"] == "APPLICATION_DATA"

    freq = by_type["frequency_alignment"]
    assert "8 posts" in freq["evidence"] and "about 4" in freq["evidence"]
    assert "meeting your posting target" in freq["recommendation"]

    titles = [i["title"] for i in body["strategy_alignment"]]
    assert any("opinion" in t for t in titles)
    assert not any("technical" in t for t in titles)
    opinion = next(i for i in body["strategy_alignment"] if "opinion" in i["title"])
    assert "None of your last 8" in opinion["evidence"]

    assert body["learning_context"]["recent_content"]
    assert "tutorial" in body["learning_context"]["strategy_priorities"]
    assert body["ai_summary"] is not None
    assert body["ai_summary"]["mock"] is True
    _walk(body)


def test_no_performance_learning_without_metrics(client):
    uid = _login(client, "sub-noperf")
    for i in range(6):
        _publish(uid, f"p-{i}", "technical")
    body = client.get("/api/learning/insights").json()
    assert body["coverage"]["performance_learning"] == "not_available"
    assert "not available" in body["performance_note"].lower()
    _walk(body)


def test_strategy_scoping(client):
    alice = _login(client, "sub-alice")
    for i in range(5):
        _publish(alice, f"a-{i}", "technical")
    _strategy(alice, content_types=["storytelling"])
    client.cookies.clear()
    bob = _login(client, "sub-bob")
    for i in range(5):
        _publish(bob, f"b-{i}", "technical")
    _strategy(bob, content_types=["tutorial"])
    client.cookies.clear()
    _login(client, "sub-alice")
    alice_body = client.get("/api/learning/insights").json()
    assert any("storytelling" in i["title"] for i in alice_body["strategy_alignment"])
    assert not any("tutorial" in i["title"] for i in alice_body["strategy_alignment"])


def test_ai_absent_when_provider_unconfigured(client, monkeypatch):
    uid = _login(client, "sub-noai")
    for i in range(5):
        _publish(uid, f"n-{i}", "technical")

    def _broken(_name="mock"):
        raise ValueError("nope")

    monkeypatch.setattr(ai_module, "get_ai_provider", _broken)
    body = client.get("/api/learning/insights").json()
    assert body["ai_summary"] is None
    assert body["state"] == "EARLY_SIGNAL"
    assert len(body["insights"]) > 0
