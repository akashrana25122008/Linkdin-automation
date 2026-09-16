"""M8 Strategy tests: persistence, validation, isolation, context source."""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app import strategy as strategy_module
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


FULL = {
    "display_name": "Ada Dev",
    "headline": "Backend engineer",
    "bio": "I build APIs.",
    "skills": ["Python", "FastAPI"],
    "projects": ["LinkedIn AI"],
    "technologies": ["React"],
    "interests": ["AI", "OSS"],
    "target_audience": "developers",
    "professional_goals": ["credibility"],
    "content_goals": ["educate"],
    "preferred_topics": ["APIs"],
    "forbidden_topics": ["politics"],
    "writing_style": "Clear and concrete.",
    "content_types": ["technical", "tutorial"],
    "posting_frequency": "weekly",
    "preferred_days": ["mon", "wed"],
    "preferred_times": ["09:00", "18:30"],
    "timezone": "Asia/Kolkata",
}


def test_strategy_requires_auth(client):
    assert client.get("/api/strategy").status_code == 401
    assert client.put("/api/strategy", json={}).status_code == 401


def test_first_time_user_gets_empty_strategy(client):
    _login(client, "sub-new")
    body = client.get("/api/strategy").json()
    assert body["display_name"] == ""
    assert body["skills"] == []
    assert body["preferred_days"] == []


def test_save_and_reload_persists(client):
    _login(client, "sub-saver")
    saved = client.put("/api/strategy", json=FULL)
    assert saved.status_code == 200
    assert saved.json()["headline"] == "Backend engineer"
    reloaded = client.get("/api/strategy").json()
    assert reloaded == saved.json()
    assert reloaded["preferred_times"] == ["09:00", "18:30"]
    assert reloaded["timezone"] == "Asia/Kolkata"


def test_partial_save_allowed(client):
    _login(client, "sub-partial")
    res = client.put("/api/strategy", json={"bio": "Just a bio."})
    assert res.status_code == 200
    assert res.json()["bio"] == "Just a bio."
    assert res.json()["skills"] == []


def test_cross_user_isolation(client):
    _login(client, "sub-owner")
    client.put("/api/strategy", json={"bio": "Owner bio"})
    before = client.get("/api/strategy").json()
    assert before["bio"] == "Owner bio"

    client.cookies.clear()
    _login(client, "sub-stranger")
    fresh = client.get("/api/strategy").json()
    assert fresh["bio"] == ""
    client.put("/api/strategy", json={"bio": "Stranger bio"})

    client.cookies.clear()
    _login(client, "sub-owner")
    assert client.get("/api/strategy").json()["bio"] == "Owner bio"


def test_invalid_values_rejected(client):
    _login(client, "sub-valid")
    assert (
        client.put("/api/strategy", json={"timezone": "Mars/Olympus"}).status_code
        == 400
    )
    assert (
        client.put("/api/strategy", json={"posting_frequency": "hourly"}).status_code
        == 400
    )
    assert (
        client.put("/api/strategy", json={"preferred_days": ["funday"]}).status_code
        == 400
    )
    assert (
        client.put(
            "/api/strategy", json={"content_types": ["viral_hacks"]}
        ).status_code
        == 400
    )
    assert (
        client.put("/api/strategy", json={"preferred_times": ["25:00"]}).status_code
        == 400
    )
    assert (
        client.put("/api/strategy", json={"bio": "x" * 2001}).status_code == 400
    )
    assert (
        client.put("/api/strategy", json={"skills": ["x" * 121]}).status_code == 400
    )
    # Valid save still works after rejections.
    assert client.put("/api/strategy", json={"bio": "ok"}).status_code == 200


def test_context_source_helpers():
    from app.models import UserStrategy

    assert strategy_module.strategy_context_text({}) == ""
    text = strategy_module.strategy_context_text(
        {"display_name": "Ada", "skills": ["Python"], "bio": ""}
    )
    assert "Ada" in text
    assert "Python" in text
    assert "Bio" not in text
    assert UserStrategy.__tablename__ == "user_strategies"
