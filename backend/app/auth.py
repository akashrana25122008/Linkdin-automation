"""Google OAuth + server-side sessions (M1).

- OAuth state validated via short-lived HTTP-only cookie (CSRF protection).
- ID tokens verified against Google on the backend (httpx, no new deps).
- Sessions: raw token in HTTP-only cookie, SHA-256 hash in DB, 7-day expiry.
- Without Google credentials every OAuth route fails honestly; app still starts.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Session as SessionModel
from app.models import User

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

SESSION_COOKIE = "li_ai_session"
OAUTH_STATE_COOKIE = "li_ai_oauth_state"
SESSION_TTL = timedelta(days=7)

NOT_CONFIGURED = "google_oauth_not_configured"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def build_authorize_url(settings: Settings, state: str) -> str:
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    )
    return f"{GOOGLE_AUTHORIZE_URL}?{params}"


def get_or_create_user(
    db: DbSession,
    *,
    sub: str,
    email: str | None,
    name: str | None,
    picture: str | None,
) -> User:
    user = db.query(User).filter_by(google_subject_id=sub).one_or_none()
    if user is None:
        user = User(google_subject_id=sub, email=email, name=name,
                    profile_picture=picture)
        db.add(user)
    else:
        user.email = email
        user.name = name
        user.profile_picture = picture
    db.commit()
    db.refresh(user)
    return user


def create_session(db: DbSession, user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        SessionModel(
            token_hash=_hash_token(raw),
            user_id=user_id,
            expires_at=_utcnow() + SESSION_TTL,
        )
    )
    db.commit()
    return raw


def get_session_user(db: DbSession, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    session = (
        db.query(SessionModel)
        .filter_by(token_hash=_hash_token(raw_token))
        .one_or_none()
    )
    if session is None or _as_aware(session.expires_at) < _utcnow():
        return None
    return db.query(User).filter_by(id=session.user_id).one_or_none()


def revoke_session(db: DbSession, raw_token: str | None) -> None:
    if not raw_token:
        return
    db.query(SessionModel).filter_by(token_hash=_hash_token(raw_token)).delete()
    db.commit()


def exchange_code(settings: Settings, code: str) -> str:
    """Trade an authorization code for an ID token. Never logs the payload."""
    try:
        res = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="exchange_failed",
        ) from exc
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="exchange_failed"
        )
    id_token = res.json().get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="exchange_failed"
        )
    return id_token


def verify_id_token(settings: Settings, id_token: str) -> dict:
    """Validate the ID token with Google; enforce audience + subject."""
    try:
        res = httpx.get(
            GOOGLE_TOKENINFO_URL, params={"id_token": id_token}, timeout=15
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="invalid_token",
        ) from exc
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"
        )
    claims = res.json()
    if claims.get("aud") != settings.google_client_id or not claims.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"
        )
    return claims


def _cookie_flags(settings: Settings) -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.app_env == "production",
        "path": "/",
    }


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_picture": user.profile_picture,
    }


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/google/status")
def google_status(settings: Settings = Depends(get_settings)) -> dict:
    if settings.google_configured:
        return {"google_oauth": "READY"}
    return {"google_oauth": "NOT CONFIGURED"}


@router.get("/google/login")
def google_login(
    response: Response, settings: Settings = Depends(get_settings)
):
    if not settings.google_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_CONFIGURED
        )
    state = secrets.token_urlsafe(32)
    redirect = RedirectResponse(build_authorize_url(settings, state))
    redirect.set_cookie(
        OAUTH_STATE_COOKIE, state, max_age=600, **_cookie_flags(settings)
    )
    return redirect


@router.get("/google/callback")
def google_callback(
    request: Request, settings: Settings = Depends(get_settings),
    db: DbSession = Depends(get_db),
):
    params = request.query_params
    if params.get("error"):
        return RedirectResponse(f"{settings.frontend_url}/login?error=cancelled")
    if (
        not settings.google_configured
        or not params.get("code")
        or not params.get("state")
        or params.get("state") != request.cookies.get(OAUTH_STATE_COOKIE)
    ):
        return RedirectResponse(f"{settings.frontend_url}/login?error=state")
    try:
        id_token = exchange_code(settings, params["code"])
        claims = verify_id_token(settings, id_token)
        user = get_or_create_user(
            db,
            sub=claims["sub"],
            email=claims.get("email"),
            name=claims.get("name"),
            picture=claims.get("picture"),
        )
        redirect = RedirectResponse(f"{settings.frontend_url}/login?login=success")
        redirect.set_cookie(
            SESSION_COOKIE,
            create_session(db, user.id),
            max_age=int(SESSION_TTL.total_seconds()),
            **_cookie_flags(settings),
        )
        redirect.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        return redirect
    except HTTPException as exc:
        code = "auth_failed" if exc.detail == "invalid_token" else str(exc.detail)
        return RedirectResponse(f"{settings.frontend_url}/login?error={code}")


@router.get("/me")
def me(request: Request, db: DbSession = Depends(get_db)) -> dict:
    user = get_session_user(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated"
        )
    return user_public(user)


@router.post("/logout")
def logout(
    request: Request, response: Response, db: DbSession = Depends(get_db)
) -> dict:
    revoke_session(db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}
