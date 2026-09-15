"""M5 Research Agent tests: search, save/ignore isolation, angles, honesty."""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app import research_api as research_api_module
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


def test_research_requires_auth(client):
    assert client.post("/api/research/search", json={"query": "x"}).status_code == 401
    assert client.get("/api/research/items").status_code == 401
    assert client.post("/api/research/items", json={"title": "x"}).status_code == 401
    assert client.post("/api/research/angle", json={"topic": "x"}).status_code == 401


def test_mock_search_returns_structured_labeled_results(client):
    _login(client, "sub-search")
    res = client.post("/api/research/search", json={"query": "AI coding agents"})
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "AI coding agents"
    assert body["mock"] is True
    assert body["scoring"]["method"] == "heuristic"
    assert len(body["results"]) >= 1
    required = {
        "title",
        "summary",
        "source_name",
        "source_url",
        "topic",
        "relevance_score",
        "freshness_score",
        "linkedin_angle",
        "mock",
    }
    for item in body["results"]:
        assert required.issubset(item.keys())
        assert item["mock"] is True
        assert "AI coding agents" in item["title"]


def test_mock_results_contain_no_fake_sources(client):
    _login(client, "sub-honest")
    body = client.post(
        "/api/research/search", json={"query": "developer tools"}
    ).json()
    combined = " ".join(
        f"{r['title']} {r['summary']} {r['source_name']} {r['source_url']}"
        for r in body["results"]
    ).lower()
    for fake in ("bbc", "reuters", "techcrunch", "http", "www.", ".com"):
        assert fake not in combined
    assert all(r["published_at"] is None for r in body["results"])


def test_query_validation(client):
    _login(client, "sub-query")
    assert client.post("/api/research/search", json={}).status_code == 400
    assert client.post("/api/research/search", json={"query": "  "}).status_code == 400
    assert (
        client.post("/api/research/search", json={"query": "x" * 201}).status_code
        == 400
    )


def test_save_and_read_own_research(client):
    _login(client, "sub-saver")
    saved = client.post(
        "/api/research/items",
        json={
            "title": "Saved signal",
            "summary": "Worth a post.",
            "source_name": "mock-development",
            "source_url": "",
            "topic": "agents",
            "relevance_score": 0.8,
            "freshness_score": 0.6,
            "linkedin_angle": "Educational explanation.",
        },
    )
    assert saved.status_code == 201
    assert saved.json()["status"] == "saved"

    listed = client.get("/api/research/items").json()["items"]
    assert [i["title"] for i in listed] == ["Saved signal"]

    single = client.get(f"/api/research/items/{saved.json()['id']}")
    assert single.status_code == 200
    assert single.json()["linkedin_angle"] == "Educational explanation."


def test_cross_user_research_isolated(client):
    _login(client, "sub-owner")
    item_id = client.post(
        "/api/research/items", json={"title": "Owner only"}
    ).json()["id"]

    client.cookies.clear()
    _login(client, "sub-stranger")
    assert client.get("/api/research/items").json()["items"] == []
    assert client.get(f"/api/research/items/{item_id}").status_code == 404
    assert client.post(f"/api/research/items/{item_id}/ignore").status_code == 404


def test_ignore_moves_item_out_of_saved(client):
    _login(client, "sub-ignorer")
    item_id = client.post(
        "/api/research/items", json={"title": "Skip me"}
    ).json()["id"]
    ignored = client.post(f"/api/research/items/{item_id}/ignore")
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"
    assert client.get("/api/research/items").json()["items"] == []
    assert (
        client.get("/api/research/items?item_status=ignored").json()["items"][0][
            "title"
        ]
        == "Skip me"
    )


def test_angle_works_in_mock_mode(client):
    _login(client, "sub-angle")
    res = client.post(
        "/api/research/angle",
        json={"topic": "browser agents", "title": "Signal", "summary": "Agents browse."},
    )
    assert res.status_code == 200
    assert res.json()["mock"] is True
    assert res.json()["angle"]
    assert client.post("/api/research/angle", json={}).status_code == 400


def test_provider_failure_is_honest(client, monkeypatch):
    _login(client, "sub-broken")

    def _broken(_name="mock"):
        raise ValueError("nope")

    monkeypatch.setattr(
        research_api_module.research_module, "get_research_provider", _broken
    )
    res = client.post("/api/research/search", json={"query": "anything"})
    assert res.status_code == 501
    assert res.json()["detail"] == "research_provider_not_configured"


def test_no_publishing_or_analytics_claims(client):
    _login(client, "sub-claims")
    search = client.post("/api/research/search", json={"query": "tools"}).json()
    angle = client.post("/api/research/angle", json={"topic": "tools"}).json()
    combined = (str(search) + str(angle)).lower()
    for claim in (
        "successfully published",
        "post id",
        "impressions",
        "verified fact",
    ):
        assert claim not in combined
