"""Auth/session architecture boundary for M1.

Rules (PRD):
- Backend owns authorization decisions.
- Never trust a frontend-supplied user_id.
- Google OAuth + server-side sessions land here in M1.
"""

from fastapi import HTTPException, status

AUTH_NOT_IMPLEMENTED = "auth_not_configured"


def get_current_user() -> int:
    """M1 placeholder. Always 401 until Google OAuth + sessions exist."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_NOT_IMPLEMENTED
    )


def assert_user_scope(authenticated_user_id: int, record_user_id: int) -> None:
    """Enforce ownership: record must belong to the backend-derived user."""
    if authenticated_user_id != record_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="forbidden"
        )
