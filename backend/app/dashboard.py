"""M3 dashboard: one authenticated endpoint assembling the Overview.

- All queries scoped to the backend-derived user. No user_id parameters.
- Brief/recommendations come from the configured AI provider (mock by
  default, always labeled). Signals come from the research provider.
- Performance is never fabricated: without LinkedIn analytics the section
  reports not_connected with zero metrics.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app import ai as ai_module
from app import research as research_module
from app.config import Settings, get_settings
from app.database import get_db
from app.models import CONTENT_STATUSES, ContentItem, User
from app.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _pipeline_counts(db: DbSession, user_id: int) -> dict[str, int]:
    counts = {status: 0 for status in CONTENT_STATUSES}
    rows = (
        db.query(ContentItem.status)
        .filter_by(user_id=user_id)
        .all()
    )
    for (status,) in rows:
        if status in counts:
            counts[status] += 1
    return counts


def _upcoming(db: DbSession, user_id: int, limit: int = 5) -> list[dict]:
    items = (
        db.query(ContentItem)
        .filter_by(user_id=user_id, status="scheduled")
        .filter(ContentItem.scheduled_at.is_not(None))
        .order_by(ContentItem.scheduled_at.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": item.id,
            "title": item.title,
            "status": item.status,
            "scheduled_at": (
                item.scheduled_at.isoformat() if item.scheduled_at else None
            ),
        }
        for item in items
    ]


def _brief_text(
    settings: Settings, user: User, total_items: int
) -> dict:
    """Deterministic context summary, optionally phrased by the AI provider."""
    name = user.name or user.email or "there"
    context = (
        f"Today's brief for {name}: {total_items} content item(s) in the "
        "pipeline. LinkedIn analytics and publishing arrive in later milestones."
    )
    try:
        result = ai_module.get_ai_provider(settings.ai_provider).generate(context)
        return {"text": result.get("text", context), "mock": bool(result.get("mock"))}
    except ValueError:
        return {"text": context, "mock": False, "note": "NOT CONFIGURED"}


def _recommendations(total_items: int, upcoming_count: int) -> list[dict]:
    recs = []
    if total_items == 0:
        recs.append(
            {
                "title": "Create your first draft",
                "detail": "Turn a topic into a LinkedIn post in Content Studio.",
                "href": "/studio",
                "mock": True,
            }
        )
    recs.append(
        {
            "title": "Explore a research signal",
            "detail": "Pick a mock signal below and shape it into an idea.",
            "href": "/research",
            "mock": True,
        }
    )
    if total_items > 0 and upcoming_count == 0:
        recs.append(
            {
                "title": "Schedule your next post",
                "detail": "Give a draft a date in the Calendar workflow.",
                "href": "/calendar",
                "mock": True,
            }
        )
    return recs


@router.get("")
def dashboard(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    counts = _pipeline_counts(db, user.id)
    total = sum(counts.values())
    upcoming = _upcoming(db, user.id)
    try:
        signals = research_module.get_research_provider(
            settings.research_provider
        ).search("professional growth")
    except ValueError:
        signals = []
    return {
        "user": {"name": user.name, "email": user.email},
        "brief": _brief_text(settings, user, total),
        "pipeline": counts,
        "signals": signals,
        "upcoming": upcoming,
        "performance": {
            "state": "not_connected",
            "message": "LinkedIn analytics are not connected yet. "
            "No metrics are shown rather than estimates.",
        },
        "recommendations": _recommendations(total, len(upcoming)),
        "mock": settings.ai_provider == "mock"
        and settings.research_provider == "mock",
    }
