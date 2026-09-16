"""M13 security audit regression tests.

F1: CORS preflight must allow every method the frontend uses, or browsers
    silently block mutations (verified: PATCH/PUT/DELETE returned 400).
F2: Mock connect must never overwrite a real encrypted LinkedIn credential
    when the deployment mode flips to mock.
"""

from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app
from app.models import LinkedInAccount

FRONTEND_ORIGIN = "http://localhost:5173"


def _client(tmp_path) -> TestClient:
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


def test_cors_preflight_allows_mutation_methods(tmp_path):
    client = _client(tmp_path)
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        res = client.options(
            "/api/studio/items",
            headers={
                "Origin": FRONTEND_ORIGIN,
                "Access-Control-Request-Method": method,
            },
        )
        assert res.status_code == 200, method
        assert method in res.headers.get("access-control-allow-methods", ""), method


def test_mock_connect_refuses_to_overwrite_real_account(tmp_path):
    client = _client(tmp_path)
    uid = _login(client, "sub-guard")
    db = get_session_local()()
    try:
        db.add(
            LinkedInAccount(
                user_id=uid,
                linkedin_member_id="li-real",
                linkedin_name="Real Member",
                access_token_encrypted="encrypted-blob",
                scopes='["openid"]',
                is_mock=False,
            )
        )
        db.commit()
    finally:
        db.close()
    res = client.post("/api/linkedin/mock/connect")
    assert res.status_code == 409
    assert res.json()["detail"] == "real_account_exists"
    db = get_session_local()()
    try:
        row = db.query(LinkedInAccount).filter_by(user_id=uid).one()
        assert row.linkedin_member_id == "li-real"
        assert row.access_token_encrypted == "encrypted-blob"
        assert row.is_mock is False
    finally:
        db.close()
