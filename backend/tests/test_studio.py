"""M4 Content Studio tests: CRUD isolation, AI actions, review honesty."""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app import studio as studio_module
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


GOOD_POST = (
    "I shipped our onboarding checklist after three failed attempts at "
    "manual QA.\n\n"
    "The lesson: every repeated bug became one checklist row, and support "
    "tickets dropped 30% in a month.\n\n"
    "What is one process you fixed with a checklist? Comment below.\n\n"
    "#engineering #process #learning"
)


def test_create_requires_auth(client):
    res = client.post("/api/studio/items", json={"title": "x"})
    assert res.status_code == 401


def test_authenticated_create_and_read_own(client):
    _login(client, "sub-author")
    created = client.post(
        "/api/studio/items",
        json={"title": "My post", "body": GOOD_POST, "content_type": "technical"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "My post"
    assert body["body"] == GOOD_POST
    assert body["status"] == "draft"

    fetched = client.get(f"/api/studio/items/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["body"] == GOOD_POST


def test_cannot_read_or_update_another_users_item(client):
    _login(client, "sub-owner")
    item_id = client.post(
        "/api/studio/items", json={"title": "Private"}
    ).json()["id"]

    client.cookies.clear()
    _login(client, "sub-intruder")
    assert client.get(f"/api/studio/items/{item_id}").status_code == 404
    assert (
        client.patch(
            f"/api/studio/items/{item_id}", json={"title": "Hijacked"}
        ).status_code
        == 404
    )


def test_update_own_item_and_validation(client):
    _login(client, "sub-editor")
    item_id = client.post(
        "/api/studio/items", json={"title": "Before"}
    ).json()["id"]
    updated = client.patch(
        f"/api/studio/items/{item_id}",
        json={"title": "After", "body": GOOD_POST, "status": "approved"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "After"
    assert updated.json()["status"] == "approved"

    assert (
        client.patch(
            f"/api/studio/items/{item_id}", json={"content_type": "nope"}
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/studio/items/{item_id}", json={"status": "published"}
        ).status_code
        == 400
    )


def test_ai_endpoints_require_auth(client):
    assert client.post("/api/studio/ai", json={"action": "generate"}).status_code == 401
    assert client.post("/api/studio/review", json={"content": "x"}).status_code == 401


def test_generate_uses_mock_provider(client):
    _login(client, "sub-gen")
    res = client.post(
        "/api/studio/ai",
        json={"action": "generate", "topic": "onboarding checklists"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mock"] is True
    assert "onboarding checklists" in body["text"]


def test_rewrite_action_works_in_mock_mode(client):
    _login(client, "sub-rewrite")
    res = client.post(
        "/api/studio/ai", json={"action": "shorten", "content": GOOD_POST}
    )
    assert res.status_code == 200
    assert res.json()["mock"] is True
    assert res.json()["text"]

    alts = client.post(
        "/api/studio/ai", json={"action": "alternatives", "content": GOOD_POST}
    )
    assert alts.status_code == 200
    assert len(alts.json()["texts"]) == 3


def test_empty_ai_input_rejected(client):
    _login(client, "sub-empty")
    assert (
        client.post("/api/studio/ai", json={"action": "generate"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/studio/ai", json={"action": "shorten", "content": "  "}
        ).status_code
        == 400
    )
    assert (
        client.post("/api/studio/review", json={"content": "  "}).status_code
        == 400
    )
    assert (
        client.post("/api/studio/ai", json={"action": "bogus"}).status_code
        == 400
    )


def test_review_returns_honest_heuristic_result(client):
    _login(client, "sub-review")
    res = client.post("/api/studio/review", json={"content": GOOD_POST})
    assert res.status_code == 200
    body = res.json()
    assert body["method"] == "heuristic"
    assert body["mock"] is True
    assert 20 <= body["score"] <= 98
    assert len(body["dimensions"]) == 9
    assert "No external fact-checking was performed" in body["factual_note"]
    assert "verif" not in body["summary"].lower()


def test_provider_failure_returns_501(client, monkeypatch):
    _login(client, "sub-fail")

    def _broken(_name="mock"):
        raise ValueError("nope")

    monkeypatch.setattr(studio_module.ai_module, "get_ai_provider", _broken)
    res = client.post(
        "/api/studio/ai",
        json={"action": "generate", "topic": "anything"},
    )
    assert res.status_code == 501
    assert res.json()["detail"] == "ai_provider_not_configured"


def test_no_linkedin_publishing_claims(client):
    _login(client, "sub-honest")
    gen = client.post(
        "/api/studio/ai", json={"action": "generate", "topic": "testing"}
    ).json()
    review = client.post(
        "/api/studio/review", json={"content": GOOD_POST}
    ).json()
    combined = (str(gen) + str(review)).lower()
    for claim in (
        "successfully published",
        "published to linkedin",
        "linkedin post id",
        "impressions",
    ):
        assert claim not in combined
    assert "no external fact-checking was performed" in combined
