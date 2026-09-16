"""M9 LinkedIn OAuth member authorization (no publishing).

- Google session answers who owns the app account; LinkedIn OAuth answers
  which member account they authorize. The two are never mixed.
- OAuth states are DB-backed: bound to the session user, 10-minute expiry,
  single-use. Tokens are Fernet-encrypted at rest, server-side only.
- Mock mode never contacts LinkedIn and stores no real credentials.
"""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from app.auth import SESSION_COOKIE, get_session_user
from app.config import Settings, get_settings
from app.database import get_db
from app.models import LinkedInAccount, LinkedInOAuthState, User
from app.security import get_current_user

router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])

LINKEDIN_AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

STATE_TTL = timedelta(minutes=10)

NOT_CONFIGURED = "linkedin_not_configured"
KEY_MISSING = "linkedin_token_key_missing"
MOCK_MODE = "linkedin_mock_mode"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_state(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def fernet_for(settings: Settings) -> Fernet | None:
    """Fernet from server-side key material. None when no key configured."""
    material = (settings.linkedin_token_key or "").strip()
    if not material:
        return None
    try:
        return Fernet(material)
    except Exception:
        digest = hashlib.sha256(material.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(settings: Settings, token: str) -> str | None:
    cipher = fernet_for(settings)
    if cipher is None:
        return None
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(settings: Settings, blob: str) -> str:
    """Decrypt a stored token. Reserved for M10 publishing use."""
    cipher = fernet_for(settings)
    if cipher is None:
        raise ValueError("no token key configured")
    return cipher.decrypt(blob.encode()).decode()


def _new_state(db: DbSession, user_id: int) -> str:
    raw = secrets.token_urlsafe(32)
    db.query(LinkedInOAuthState).filter(
        LinkedInOAuthState.expires_at < _utcnow()
    ).delete()
    db.add(
        LinkedInOAuthState(
            state_hash=_hash_state(raw),
            user_id=user_id,
            expires_at=_utcnow() + STATE_TTL,
            consumed=False,
        )
    )
    db.commit()
    return raw


def _consume_state(db: DbSession, user_id: int, raw: str | None) -> bool:
    if not raw:
        return False
    row = (
        db.query(LinkedInOAuthState)
        .filter_by(state_hash=_hash_state(raw), user_id=user_id, consumed=False)
        .one_or_none()
    )
    if row is None:
        return False
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < _utcnow():
        return False
    row.consumed = True
    db.commit()
    return True


def _account_public(account: LinkedInAccount | None, mode: str, mock: bool) -> dict:
    if account is None:
        return {"connected": False, "mode": mode, "mock": mock}
    connected_at = account.connected_at
    if connected_at is not None and connected_at.tzinfo is None:
        connected_at = connected_at.replace(tzinfo=timezone.utc)
    try:
        scopes = json.loads(account.scopes or "[]")
    except ValueError:
        scopes = []
    return {
        "connected": True,
        "mode": mode,
        "mock": mock or account.is_mock,
        "member_name": account.linkedin_name,
        "member_id": account.linkedin_member_id,
        "connected_at": connected_at.isoformat() if connected_at else None,
        "scopes": scopes if isinstance(scopes, list) else [],
    }


def _exchange_code(settings: Settings, code: str) -> dict:
    try:
        res = httpx.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
                "redirect_uri": settings.linkedin_redirect_uri,
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="linkedin_exchange_failed"
        ) from exc
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="linkedin_exchange_failed"
        )
    return res.json()


def _fetch_member(access_token: str) -> dict:
    try:
        res = httpx.get(
            LINKEDIN_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="linkedin_identity_failed"
        ) from exc
    if res.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="linkedin_identity_failed"
        )
    return res.json()


@router.get("/status")
def linkedin_status(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if settings.linkedin_mode == "mock":
        account = db.query(LinkedInAccount).filter_by(user_id=user.id).one_or_none()
        result = _account_public(account, "mock", True)
        result["configured"] = False
        return result
    account = db.query(LinkedInAccount).filter_by(user_id=user.id).one_or_none()
    result = _account_public(account, "live", False)
    result["configured"] = settings.linkedin_configured
    return result


@router.get("/connect")
def linkedin_connect(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if settings.linkedin_mode == "mock":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=MOCK_MODE)
    if not settings.linkedin_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_CONFIGURED
        )
    if fernet_for(settings) is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=KEY_MISSING
        )
    state = _new_state(db, user.id)
    url = (
        f"{LINKEDIN_AUTHORIZE_URL}?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": settings.linkedin_client_id,
                "redirect_uri": settings.linkedin_redirect_uri,
                "state": state,
                "scope": " ".join(settings.linkedin_scope_list),
            }
        )
    )
    return RedirectResponse(url)


@router.get("/callback")
def linkedin_callback(
    request: Request,
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    params = request.query_params
    if params.get("error"):
        return RedirectResponse(f"{settings.frontend_url}/settings?linkedin=cancelled")
    session_user = get_session_user(db, request.cookies.get(SESSION_COOKIE))
    if session_user is None:
        return RedirectResponse(f"{settings.frontend_url}/settings?linkedin=session")
    if not _consume_state(db, session_user.id, params.get("state")):
        return RedirectResponse(f"{settings.frontend_url}/settings?linkedin=state")
    code = params.get("code", "")
    if not code:
        return RedirectResponse(f"{settings.frontend_url}/settings?linkedin=error")
    try:
        token_data = _exchange_code(settings, code)
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="linkedin_exchange_failed",
            )
        member = _fetch_member(access_token)
        member_id = member.get("sub", "")
        if not member_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="linkedin_identity_failed",
            )
        encrypted = encrypt_token(settings, access_token)
        if encrypted is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=KEY_MISSING
            )
        expires_in = token_data.get("expires_in")
        account = (
            db.query(LinkedInAccount).filter_by(user_id=session_user.id).one_or_none()
        )
        if account is None:
            account = LinkedInAccount(user_id=session_user.id)
            db.add(account)
        account.linkedin_member_id = member_id
        account.linkedin_name = member.get("name", "")
        account.linkedin_email = member.get("email")
        account.profile_url = None
        account.access_token_encrypted = encrypted
        account.token_expires_at = (
            _utcnow() + timedelta(seconds=int(expires_in))
            if isinstance(expires_in, int)
            else None
        )
        account.scopes = json.dumps(settings.linkedin_scope_list)
        account.is_mock = False
        account.connected_at = _utcnow()
        db.commit()
    except HTTPException:
        return RedirectResponse(f"{settings.frontend_url}/settings?linkedin=error")
    return RedirectResponse(f"{settings.frontend_url}/settings?linkedin=connected")


@router.delete("/connection")
def linkedin_disconnect(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    account = db.query(LinkedInAccount).filter_by(user_id=user.id).one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not_connected"
        )
    db.delete(account)
    db.query(LinkedInOAuthState).filter_by(user_id=user.id).delete()
    db.commit()
    return {"status": "ok"}


@router.post("/mock/connect")
def mock_connect(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Clearly-fake local connection for UI testing. Mock mode only, no token."""
    if settings.linkedin_mode != "mock":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not_found"
        )
    account = db.query(LinkedInAccount).filter_by(user_id=user.id).one_or_none()
    if account is None:
        account = LinkedInAccount(user_id=user.id)
        db.add(account)
    account.linkedin_member_id = "mock-member"
    account.linkedin_name = "Mock Member"
    account.linkedin_email = None
    account.profile_url = None
    account.access_token_encrypted = ""
    account.token_expires_at = None
    account.scopes = json.dumps(["mock"])
    account.is_mock = True
    account.connected_at = _utcnow()
    db.commit()
    db.refresh(account)
    return _account_public(account, "mock", True)
