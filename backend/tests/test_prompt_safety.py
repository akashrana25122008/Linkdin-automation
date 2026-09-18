"""Personal-fact safety + prompt-accuracy regression tests.

Tests assert on the constructed prompt/instructions and deterministic
behavior. No live provider calls, no real credentials, no network.
"""

import pytest
from fastapi.testclient import TestClient

from app import ai as ai_module
from app import auth
from app.database import get_session_local, init_db
from app.main import app
from app.prompts import SAFETY_RULES

TOPIC = "What I learned while building an AI-powered LinkedIn personal brand automation system"


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


class CaptureProvider:
    name = "capture"

    def __init__(self):
        self.prompt = ""

    def generate(self, prompt: str) -> dict:
        self.prompt = prompt
        return {"provider": "capture", "mock": False, "text": "ok"}


@pytest.fixture()
def capture(monkeypatch):
    provider = CaptureProvider()
    monkeypatch.setattr(
        ai_module, "get_ai_provider", lambda _name="mock", **kwargs: provider
    )
    return provider


def _generate(client, topic=TOPIC, content_type="personal_learning"):
    return client.post(
        "/api/studio/ai",
        json={"action": "generate", "topic": topic, "content_type": content_type},
    )


def test_no_fabricated_education_in_prompt(client, capture):
    """A. Topic about building an AI system must not imply student status.

    The Safety rules block itself names prohibited categories, so the
    assertion scopes to the task portion of the prompt.
    """
    _login(client, "sub-plain")
    assert _generate(client).status_code == 200
    task_part = capture.prompt.split("Safety rules")[0].lower()
    for invented in (
        "first-year", "first year", "student", "freshman",
        "college", "university", "cse",
    ):
        assert invented not in task_part
    assert TOPIC in capture.prompt


def test_topic_distinguished_from_verified_facts(client, capture):
    """B. Topic is labeled guidance; verified facts come only from context."""
    _login(client, "sub-distinguish")
    _generate(client)
    assert "Topic:" in capture.prompt
    assert "guidance only" in capture.prompt
    assert "not evidence" in capture.prompt


def test_supported_profile_facts_reach_prompt(client, capture):
    """C. Explicitly stored facts (Python, FastAPI) may be used."""
    _login(client, "sub-supported")
    res = client.put("/api/strategy", json={"technologies": ["Python", "FastAPI"]})
    assert res.status_code == 200
    _generate(client)
    assert "Python" in capture.prompt
    assert "FastAPI" in capture.prompt


def test_unsupported_facts_prohibited_not_present(client, capture):
    """D. Missing college/job/achievement details must be barred, not filled."""
    _login(client, "sub-unsupported")
    _generate(client)
    assert "Never invent" in capture.prompt
    for category in ("college", "job title", "achievements", "metrics"):
        assert category in capture.prompt
    lowered = capture.prompt.lower()
    for invented_value in ("stanford", "google", "10 years", "cto"):
        assert invented_value not in lowered


def test_no_prompt_or_secret_leakage(client, capture):
    """E. Safety block exposes no credentials, keys, or internals."""
    _login(client, "sub-leakcheck")
    _generate(client)
    lowered = capture.prompt.lower()
    for secret in ("sk-", "gsk_", "bearer", "api_key", "client_secret", "secret"):
        assert secret not in lowered
    assert "Safety rules" in capture.prompt


def test_user_isolation_of_personal_context(client, capture):
    """H. One user's profile facts cannot enter another user's prompt."""
    _login(client, "sub-owner")
    client.put("/api/strategy", json={"technologies": ["Rust", "WASM"]})
    _generate(client)
    assert "Rust" in capture.prompt
    client.cookies.clear()
    _login(client, "sub-stranger")
    _generate(client)
    assert "Rust" not in capture.prompt
    assert "WASM" not in capture.prompt


def test_groq_contract_untouched():
    """G. Groq request contract and factory behavior are unchanged."""
    import inspect

    from app.ai import GroqAIProvider, get_ai_provider

    sig = inspect.signature(GroqAIProvider.__init__)
    assert list(sig.parameters) == ["self", "api_key", "model"]
    provider = GroqAIProvider(api_key="test-key", model="openai/gpt-oss-20b")
    assert provider.name == "groq"
    assert get_ai_provider("mock").name == "mock"
    try:
        get_ai_provider("groq")
        raise AssertionError("expected ValueError without a key")
    except ValueError:
        pass


def test_safety_rules_static_and_credential_free():
    assert "guidance only" in SAFETY_RULES
    lowered = SAFETY_RULES.lower()
    for secret in ("sk-", "gsk_", "bearer", "api_key", "client_secret"):
        assert secret not in lowered
