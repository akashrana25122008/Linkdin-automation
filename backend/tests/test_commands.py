"""Command Center tests: routing, confirmation gates, isolation, honesty."""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.commands import route_command
from app.database import get_session_local, init_db
from app.main import app
from app.models import ContentItem


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


def _draft(client, title="Cmd draft", status="approved", body="Concrete body text here."):
    res = client.post(
        "/api/studio/items", json={"title": title, "body": body, "status": status}
    )
    assert res.status_code == 201
    return res.json()["id"]


def cmd(client, text, **extra):
    return client.post("/api/commands", json={"text": text, **extra})


def test_commands_require_auth(client):
    assert client.post("/api/commands", json={"text": "help"}).status_code == 401


def test_routing_table():
    cases = {
        "Create a LinkedIn post about my latest project.": "CREATE_POST",
        "Give me three post ideas based on my strategy.": "CREATE_IDEAS",
        "Find recent AI topics I can post about.": "RESEARCH",
        "Review my latest draft.": "REVIEW_DRAFT",
        "Make this post shorter.": "REWRITE_DRAFT",
        "Give this post a stronger hook.": "REWRITE_DRAFT",
        "Repurpose my last published post.": "REPURPOSE_POST",
        "Schedule this draft for Friday at 7 PM.": "SCHEDULE_POST",
        "Show me what I have scheduled.": "SHOW_CALENDAR",
        "Show my recent published posts.": "SHOW_PUBLISHED",
        "Publish my latest draft.": "PUBLISH_REFUSED",
        "Delete this draft.": "DELETE_REFUSED",
        "Why did the AI reject this post?": "REVIEW_DRAFT",
        "Turn this rough thought into a post.": "CREATE_FROM_THOUGHT",
        "Create a post from my certificate.": "CREATE_FROM_CERTIFICATE",
        "How is my content doing?": "SHOW_ANALYTICS",
        "Set posting frequency to weekly.": "UPDATE_STRATEGY",
        "Is LinkedIn connected?": "LINKEDIN_STATUS",
        "Help, what can you do?": "HELP",
        "Blah blah nonsense xyz.": "UNKNOWN",
    }
    for text, intent in cases.items():
        assert route_command(text)[0] == intent, text


def test_create_post_missing_topic_asks(client):
    _login(client, "sub-topic")
    body = cmd(client, "Create a post.").json()
    assert body["intent"] == "CREATE_POST"
    assert "action" in body and body["action"]["kind"] == "none"


def test_create_post_generates_with_mock(client):
    _login(client, "sub-create")
    body = cmd(client, 'Create a post about "onboarding checklists".').json()
    assert body["intent"] == "CREATE_POST"
    assert body["mock"] is True
    assert body["action"]["kind"] == "studio_prefill"
    assert "onboarding checklists" in body["action"]["topic"]


def test_review_and_rewrite_use_owned_draft(client):
    _login(client, "sub-review")
    item_id = _draft(client)
    review = cmd(client, "Review my latest draft.").json()
    assert review["intent"] == "REVIEW_DRAFT"
    assert f"/studio?id={item_id}" in review["action"]["href"]
    rewrite = cmd(client, "Make this post shorter.").json()
    assert rewrite["intent"] == "REWRITE_DRAFT"
    assert rewrite["action"]["body"]
    assert rewrite["mock"] is True


def test_repurpose_uses_last_published(client):
    uid = _login(client, "sub-repurpose")
    db = get_session_local()()
    try:
        db.add(ContentItem(user_id=uid, title="Shipped", body="Body here.", status="published"))
        db.commit()
    finally:
        db.close()
    body = cmd(client, "Repurpose my last published post.").json()
    assert body["intent"] == "REPURPOSE_POST"
    assert body["action"]["body"]


def test_schedule_two_step_confirmation(client):
    _login(client, "sub-sched")
    item_id = _draft(client)
    first = cmd(client, "Schedule this draft for Friday at 7 PM.").json()
    assert first["intent"] == "SCHEDULE_POST"
    assert first["needs_confirmation"] is True
    proposal = first["proposal"]
    assert proposal["draft_id"] == item_id
    done = cmd(client, "Schedule this draft for Friday at 7 PM.",
               confirmed=True, proposal=proposal).json()
    assert "Scheduled for" in done["message"]
    assert done["scheduled"]["status"] == "scheduled"


def test_schedule_requires_approval(client):
    _login(client, "sub-unapproved")
    res = client.post(
        "/api/studio/items", json={"title": "Raw", "body": "Body.", "status": "draft"}
    )
    item_id = res.json()["id"]
    body = cmd(client, "Schedule this draft for Friday at 7 PM.").json()
    assert "Approve it" in body["message"]


def test_publish_and_delete_never_execute(client):
    _login(client, "sub-safe")
    _draft(client)
    pub = cmd(client, "Publish my latest draft.").json()
    assert pub["intent"] == "PUBLISH_REFUSED"
    assert "approval" in pub["message"].lower()
    delete = cmd(client, "Delete this draft.").json()
    assert delete["intent"] == "DELETE_REFUSED"
    db = get_session_local()()
    try:
        from app.models import ContentItem as CI

        assert db.query(CI).filter_by(status="published").count() == 0
    finally:
        db.close()


def test_show_endpoints_are_user_scoped(client):
    _login(client, "sub-owner")
    _draft(client, title="Owner draft")
    client.cookies.clear()
    _login(client, "sub-stranger")
    body = cmd(client, "Show my drafts.").json()
    assert body["items"] == []
    pub = cmd(client, "Show my recent published posts.").json()
    assert pub["items"] == []


def test_update_strategy_two_step(client):
    _login(client, "sub-strat")
    first = cmd(client, "Set posting frequency to weekly.").json()
    assert first["needs_confirmation"] is True
    assert first["proposal"] == {"posting_frequency": "weekly"}
    done = cmd(client, "Set posting frequency to weekly.",
               confirmed=True, proposal={"posting_frequency": "weekly"}).json()
    assert "weekly" in done["message"]
    tampered = cmd(client, "Set posting frequency to weekly.",
                   confirmed=True, proposal={"posting_frequency": "daily"}).json()
    assert tampered.get("needs_confirmation") is True


def test_unknown_and_empty_rejected(client):
    _login(client, "sub-unknown")
    assert cmd(client, "Blah blah nonsense xyz.").json()["intent"] == "UNKNOWN"
    assert cmd(client, "   ").status_code == 400
