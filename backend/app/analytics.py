"""M11 Analytics: honest, application-data-only publishing analytics.

LinkedIn engagement capability (verified against the member integration):
our app holds OpenID Connect identity scopes plus optional w_member_social,
and ugcPosts creation returns only a post ID. Post-level engagement
(impressions, reactions, comments, shares, reach, CTR, followers) is NOT
AVAILABLE through these permissions — it requires additional LinkedIn
products/permissions. It is therefore never fetched, estimated, or shown.

Every number here comes from the user's own stored content rows
(source: APPLICATION_DATA). No new tables, no cache, no LinkedIn calls.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.models import ContentItem, LinkedInAccount, User, UserStrategy
from app.security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

SOURCE = "APPLICATION_DATA"

RANGES = {"7": 7, "30": 30, "90": 90, "all": None}

ENGAGEMENT_UNAVAILABLE = (
    "LinkedIn engagement metrics (impressions, reactions, comments, "
    "shares) are not available through the connected member integration, "
    "which requires additional LinkedIn products/permissions. "
    "Only application publishing data is shown."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _user_tz(db: DbSession, user_id: int) -> timezone | ZoneInfo:
    row = db.query(UserStrategy).filter_by(user_id=user_id).one_or_none()
    name = (row.timezone if row else "") or ""
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone.utc


def _parse_days(raw: str | None) -> tuple[str, int | None]:
    key = (raw or "30").strip()
    if key not in RANGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_range"
        )
    return key, RANGES[key]


def _own_items(db: DbSession, user_id: int) -> list[ContentItem]:
    return db.query(ContentItem).filter_by(user_id=user_id).all()


def _in_range(published_at: datetime | None, cutoff: datetime | None) -> bool:
    if published_at is None:
        return False
    moment = _as_utc(published_at)
    assert moment is not None
    return cutoff is None or moment >= cutoff


def _buckets(
    published: list[datetime], days: int | None, tz: timezone | ZoneInfo
) -> list[dict]:
    """Chronological activity buckets. Daily for 7d, weekly otherwise,
    monthly for all-time (capped at 24). Only buckets within the range."""
    now = _utcnow().astimezone(tz)
    if days == 7:
        starts = [
            (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            for i in range(6, -1, -1)
        ]
        fmt = lambda d: d.strftime("%a")  # noqa: E731
    elif days is None:
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starts = []
        cursor = first
        for _ in range(24):
            starts.insert(0, cursor)
            cursor = (cursor - timedelta(days=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        fmt = lambda d: d.strftime("%b %Y")  # noqa: E731
    else:
        span = 5 if days == 30 else 13
        anchor = now.replace(hour=0, minute=0, second=0, microsecond=0)
        anchor = anchor - timedelta(days=anchor.weekday())
        starts = [anchor - timedelta(weeks=i) for i in range(span - 1, -1, -1)]
        fmt = lambda d: d.strftime("%b %d")  # noqa: E731
    out = []
    for index, start in enumerate(starts):
        # Each bucket ends where the next begins: no gaps, no double counts.
        end = starts[index + 1] if index + 1 < len(starts) else start + timedelta(days=32)
        count = sum(
            1 for moment in published if start <= moment.astimezone(tz) < end
        )
        out.append({"label": fmt(start), "start": start.isoformat(), "count": count})
    return out


def _linkedin_block(db: DbSession, user_id: int) -> dict:
    account = db.query(LinkedInAccount).filter_by(user_id=user_id).one_or_none()
    return {
        "connected": account is not None,
        "mock": bool(account and account.is_mock),
        "engagement": {"state": "unavailable", "message": ENGAGEMENT_UNAVAILABLE},
    }


@router.get("/overview")
def analytics_overview(
    days: str = "30",
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    key, span = _parse_days(days)
    tz = _user_tz(db, user.id)
    cutoff = (_utcnow() - timedelta(days=span)) if span else None

    items = _own_items(db, user.id)
    by_status: dict[str, int] = {}
    for item in items:
        by_status[item.status] = by_status.get(item.status, 0) + 1

    published = [
        _as_utc(item.published_at)
        for item in items
        if item.status == "published" and _in_range(item.published_at, cutoff)
    ]
    published = [moment for moment in published if moment is not None]

    by_type: dict[str, int] = {}
    for item in items:
        if item.status == "published" and _in_range(item.published_at, cutoff):
            by_type[item.content_type] = by_type.get(item.content_type, 0) + 1

    weeks = (span / 7) if span else None
    return {
        "source": SOURCE,
        "range": key,
        "timezone": str(tz),
        "status_counts": by_status,
        "published_in_range": len(published),
        "posts_per_week": round(len(published) / weeks, 1) if weeks else None,
        "by_content_type": by_type,
        "weekly_activity": _buckets(
            published, span, tz if isinstance(tz, ZoneInfo) else timezone.utc
        ),
        "linkedin": _linkedin_block(db, user.id),
    }


@router.get("/posts")
def analytics_posts(
    days: str = "30",
    post_status: str = "",
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    key, span = _parse_days(days)
    if post_status and post_status not in (
        "published",
        "scheduled",
        "failed",
        "draft",
        "approved",
        "idea",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status"
        )
    limit = max(1, min(limit, 100))
    cutoff = (_utcnow() - timedelta(days=span)) if span else None

    query = db.query(ContentItem).filter_by(user_id=user.id)
    if post_status:
        query = query.filter_by(status=post_status)
    rows = (
        query.order_by(ContentItem.published_at.desc())
        .limit(limit + 1)
        .all()
    )

    def moment(item: ContentItem) -> datetime | None:
        return _as_utc(item.published_at or item.scheduled_at or item.updated_at)

    if span is not None:
        rows = [r for r in rows if (moment(r) or _utcnow()) >= cutoff]
    rows = rows[:limit]

    return {
        "source": SOURCE,
        "range": key,
        "engagement": "unavailable",
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "content_type": item.content_type,
                "status": item.status,
                "published_at": _as_utc(item.published_at).isoformat()
                if _as_utc(item.published_at)
                else None,
                "scheduled_at": _as_utc(item.scheduled_at).isoformat()
                if _as_utc(item.scheduled_at)
                else None,
                "linkedin_post_id": item.linkedin_post_id,
            }
            for item in rows
        ],
    }
