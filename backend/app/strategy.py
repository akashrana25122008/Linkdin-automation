"""M8 Strategy: one user-owned personal-brand configuration.

- GET returns defaults for first-time users without creating a row.
- PUT merges provided fields over the stored (or default) configuration.
- get_user_strategy() is the user-scoped context source future AI flows
  can call; strategy_context_text() renders it as a prompt-ready block.
"""

import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import CONTENT_TYPES, User, UserStrategy
from app.security import get_current_user

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

FREQUENCIES = ("daily", "3x_week", "weekly", "2x_month", "custom")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

NAME_MAX = 255
TEXT_MAX = 2000
LIST_ITEM_MAX = 120
LIST_COUNT_MAX = 50

TEXT_FIELDS = (
    "display_name",
    "headline",
    "bio",
    "target_audience",
    "writing_style",
    "posting_frequency",
    "timezone",
)
LIST_FIELDS = (
    "skills",
    "projects",
    "technologies",
    "interests",
    "professional_goals",
    "content_goals",
    "preferred_topics",
    "forbidden_topics",
    "content_types",
    "preferred_days",
    "preferred_times",
)


def _check_text(value, name: str, max_len: int) -> str:
    text = value if isinstance(value, str) else ""
    if len(text) > max_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_too_long"
        )
    return text


def _check_list(value, name: str) -> list[str]:
    items = value if isinstance(value, list) else []
    if not isinstance(value, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_invalid"
        )
    if len(items) > LIST_COUNT_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_too_many"
        )
    cleaned = []
    for entry in items:
        if not isinstance(entry, str) or not entry.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_invalid"
            )
        if len(entry.strip()) > LIST_ITEM_MAX:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_too_long"
            )
        cleaned.append(entry.strip())
    return cleaned


def _check_constrained(data: dict) -> None:
    freq = data.get("posting_frequency", "")
    if freq and freq not in FREQUENCIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_frequency"
        )
    if any(d not in DAYS for d in data.get("preferred_days", [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_day"
        )
    if any(not TIME_RE.match(t) for t in data.get("preferred_times", [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_time"
        )
    if any(c not in CONTENT_TYPES for c in data.get("content_types", [])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_content_type"
        )
    tz = data.get("timezone", "")
    if tz:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_timezone"
            )


def _defaults() -> dict:
    data: dict = {f: "" for f in TEXT_FIELDS}
    data.update({f: [] for f in LIST_FIELDS})
    return data


def strategy_public(row: UserStrategy | None) -> dict:
    data = _defaults()
    if row is None:
        return data
    for field in TEXT_FIELDS:
        data[field] = getattr(row, field) or ""
    for field in LIST_FIELDS:
        try:
            decoded = json.loads(getattr(row, field) or "[]")
            data[field] = decoded if isinstance(decoded, list) else []
        except (ValueError, TypeError):
            data[field] = []
    return data


def get_user_strategy(db: DbSession, user_id: int) -> dict:
    """User-scoped strategy retrieval for future AI integration."""
    row = db.query(UserStrategy).filter_by(user_id=user_id).one_or_none()
    return strategy_public(row)


def strategy_context_text(data: dict) -> str:
    """Compact prompt-ready rendering of non-empty strategy fields."""
    lines = []
    if data.get("display_name"):
        lines.append(f"Author: {data['display_name']}")
    if data.get("headline"):
        lines.append(f"Headline: {data['headline']}")
    if data.get("bio"):
        lines.append(f"Bio: {data['bio']}")
    for field, label in (
        ("skills", "Skills"),
        ("technologies", "Technologies"),
        ("projects", "Projects"),
        ("interests", "Interests"),
        ("target_audience", "Target audience"),
        ("professional_goals", "Professional goals"),
        ("content_goals", "Content goals"),
        ("preferred_topics", "Preferred topics"),
        ("forbidden_topics", "Forbidden topics"),
        ("writing_style", "Writing style"),
        ("content_types", "Preferred content types"),
    ):
        value = data.get(field)
        if not value:
            continue
        if isinstance(value, list):
            lines.append(f"{label}: {', '.join(value)}")
        else:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


@router.get("")
def read_strategy(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    return get_user_strategy(db, user.id)


@router.put("")
def save_strategy(
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_payload"
        )
    row = db.query(UserStrategy).filter_by(user_id=user.id).one_or_none()
    data = strategy_public(row)
    for field in TEXT_FIELDS:
        if field in payload:
            cap = NAME_MAX if field in ("display_name", "headline") else TEXT_MAX
            data[field] = _check_text(payload[field], field, cap)
    for field in LIST_FIELDS:
        if field in payload:
            data[field] = _check_list(payload[field], field)
    _check_constrained(data)
    if row is None:
        row = UserStrategy(user_id=user.id)
        db.add(row)
    for field in TEXT_FIELDS:
        setattr(row, field, data[field])
    for field in LIST_FIELDS:
        setattr(row, field, json.dumps(data[field]))
    db.commit()
    db.refresh(row)
    return strategy_public(row)
