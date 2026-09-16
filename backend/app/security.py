"""Backend-owned authentication boundary.

Rules (PRD):
- Backend owns authentication and authorization decisions.
- Identity comes from the validated server-side session cookie.
- Never trust a frontend-supplied user_id.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import User


def get_current_user(
    request: Request, db: DbSession = Depends(get_db)
) -> User:
    """Resolve the user from the session cookie. 401 when unauthenticated."""
    from app.auth import SESSION_COOKIE, get_session_user

    user = get_session_user(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated"
        )
    return user
