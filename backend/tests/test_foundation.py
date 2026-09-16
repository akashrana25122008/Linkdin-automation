"""Provider, security-boundary, and database tests."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import ai as ai_module
from app import linkedin as linkedin_module
from app import research as research_module
from app import security
from app.config import Settings
from app.database import get_session_local, init_db
from app.models import User


def test_config_public_summary_never_leaks_secrets():
    summary = Settings().public_summary()
    assert "mock_mode" in summary
    for key in summary:
        assert "secret" not in key.lower()
        assert "token" not in key.lower()
        assert "api_key" not in key.lower()


def test_mock_ai_works_without_credentials():
    provider = ai_module.get_ai_provider("mock")
    result = provider.generate("test topic")
    assert result["mock"] is True
    assert result["provider"] == "mock"


def test_unknown_ai_provider_fails_honestly():
    with pytest.raises(ValueError, match="NOT CONFIGURED"):
        ai_module.get_ai_provider("groq")


def test_mock_research_is_labeled_mock():
    provider = research_module.get_research_provider("mock")
    items = provider.search("python")
    assert len(items) >= 1
    assert all(item["mock"] is True for item in items)


def test_mock_linkedin_never_publishes():
    client = linkedin_module.get_linkedin_client("mock")
    assert client.status().mode == "mock"
    with pytest.raises(RuntimeError, match="never publishes"):
        client.publish("hello")


def test_auth_boundary_rejects_without_session():
    init_db("sqlite:///:memory:")
    db = get_session_local()()
    try:
        request = Request({"type": "http", "headers": []})
        with pytest.raises(HTTPException) as exc:
            security.get_current_user(request, db)
        assert exc.value.status_code == 401
    finally:
        db.close()


def test_user_model_roundtrip_in_memory():
    init_db("sqlite:///:memory:")
    session = get_session_local()()
    try:
        session.add(User(email="a@example.com", name="A"))
        session.commit()
        found = session.query(User).filter_by(email="a@example.com").one()
        assert found.name == "A"
        assert found.id is not None
    finally:
        session.close()
