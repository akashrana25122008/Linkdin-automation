"""M12 Learning Loop: evidence-based, user-scoped content insights.

Data honesty contract:
- Only APPLICATION_DATA is used (own published rows + own strategy).
  LinkedIn engagement is unavailable, so no performance-based learning
  is ever generated.
- Minimum-data thresholds are explicit constants below. Below them the
  API returns INSUFFICIENT_DATA instead of patterns.
- AI (when configured) only phrases already-validated facts into a
  summary string. It never produces stored structured data, metrics,
  or causal claims. Nothing is auto-saved, auto-generated, or published.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app import ai as ai_module
from app.config import Settings, get_settings
from app.database import get_db
from app.models import ContentItem, User
from app.security import get_current_user
from app.strategy import get_user_strategy

router = APIRouter(prefix="/api/learning", tags=["learning"])

SOURCE = "APPLICATION_DATA"

# Explicit minimum-data thresholds (documented, not hidden).
MIN_PUBLISHED_FOR_PATTERNS = 5
SUPPORTED_PATTERN_AT = 8
RECENT_WINDOW = 10
CONSISTENCY_DAYS = 30

FREQUENCY_TARGETS = {
    "daily": 30,
    "3x_week": 12,
    "weekly": 4,
    "2x_month": 2,
}

PERFORMANCE_UNAVAILABLE = (
    "Performance-based learning is not available: no verified LinkedIn "
    "engagement metrics exist for this integration."
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _published(db: DbSession, user_id: int) -> list[ContentItem]:
    rows = (
        db.query(ContentItem)
        .filter_by(user_id=user_id, status="published")
        .order_by(ContentItem.published_at.desc())
        .all()
    )
    # Rows without a timestamp carry no timing evidence; keep them only
    # for totals, never for recency or distribution claims.
    return rows


def _confidence(total: int) -> str:
    if total < MIN_PUBLISHED_FOR_PATTERNS:
        return "INSUFFICIENT_DATA"
    if total < SUPPORTED_PATTERN_AT:
        return "EARLY_SIGNAL"
    return "SUPPORTED_PATTERN"


def _insight(
    kind: str,
    title: str,
    evidence: str,
    confidence: str,
    recommendation: str | None = None,
) -> dict:
    return {
        "type": kind,
        "title": title,
        "evidence": evidence,
        "confidence": confidence,
        "source": SOURCE,
        "recommendation": recommendation,
    }


def _distribution_insights(recent: list[ContentItem], confidence: str) -> list[dict]:
    counts: dict[str, int] = {}
    for item in recent:
        counts[item.content_type] = counts.get(item.content_type, 0) + 1
    total = len(recent)
    insights = [
        _insight(
            "content_distribution",
            "Recent content mix",
            f"Of your last {total} published posts: "
            + ", ".join(f"{count} {kind}" for kind, count in sorted(counts.items())),
            confidence,
        )
    ]
    top_kind, top_count = max(counts.items(), key=lambda kv: kv[1])
    if top_count / total >= 0.8 and total >= MIN_PUBLISHED_FOR_PATTERNS:
        insights.append(
            _insight(
                "content_variety",
                f"{top_kind} dominates recent output",
                f"{top_count} of your last {total} published posts used the "
                f"{top_kind} format.",
                confidence,
                "Consider varying the format for one of your next posts.",
            )
        )
    return insights


def _consistency_insights(
    published: list[ContentItem], strategy: dict, confidence: str
) -> list[dict]:
    cutoff = _utcnow() - timedelta(days=CONSISTENCY_DAYS)
    recent = sum(
        1
        for item in published
        if _as_utc(item.published_at) is not None
        and _as_utc(item.published_at) >= cutoff
    )
    insights = [
        _insight(
            "publishing_consistency",
            "Publishing consistency",
            f"You published {recent} posts in the last {CONSISTENCY_DAYS} days.",
            confidence,
        )
    ]
    target = FREQUENCY_TARGETS.get(strategy.get("posting_frequency", ""))
    if target is not None:
        insights.append(
            _insight(
                "frequency_alignment",
                "Output versus your posting target",
                f"You published {recent} posts in the last {CONSISTENCY_DAYS} days "
                f"against a strategy target of about {target}.",
                confidence,
                "Consider scheduling one more post this week."
                if recent < target
                else "You are meeting your posting target.",
            )
        )
    return insights


def _alignment_insights(
    recent: list[ContentItem], strategy: dict, confidence: str
) -> list[dict]:
    wanted = [c for c in strategy.get("content_types", []) if isinstance(c, str)]
    if not wanted:
        return []
    used = {item.content_type for item in recent}
    missing = [c for c in wanted if c not in used]
    total = len(recent)
    insights = []
    for content_type in missing:
        insights.append(
            _insight(
                "strategy_alignment",
                f"{content_type} is underrepresented",
                f"None of your last {total} published posts used the "
                f"{content_type} format, although it is a stated strategy priority.",
                confidence,
                f"Consider making your next post a {content_type} piece.",
            )
        )
    return insights


def _learning_context(
    recent: list[ContentItem], strategy: dict, insights: list[dict]
) -> dict:
    mix: dict[str, int] = {}
    for item in recent:
        mix[item.content_type] = mix.get(item.content_type, 0) + 1
    return {
        "recent_content": [
            f"{count} {kind} posts" for kind, count in sorted(mix.items())
        ],
        "strategy_priorities": [
            c for c in strategy.get("content_types", []) if isinstance(c, str)
        ],
        "validated_learnings": [i["title"] for i in insights],
    }


def _ai_summary(settings: Settings, facts: list[str]) -> dict | None:
    """Phrase validated facts with the configured provider. Returns None
    when no provider is configured; never raises for missing config."""
    if not facts:
        return None
    try:
        provider = ai_module.get_ai_provider(settings.ai_provider, settings=settings)
    except ValueError:
        return None
    prompt = (
        "Summarize these validated content facts for the author in two "
        "sentences or fewer. Do not invent metrics, causes, or advice "
        "beyond what is stated:\n" + "\n".join(f"- {fact}" for fact in facts)
    )
    try:
        result = provider.generate(prompt)
    except ai_module.AIProviderError:
        return None
    return {"text": result.get("text", ""), "mock": bool(result.get("mock"))}


@router.get("/insights")
def learning_insights(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    published = _published(db, user.id)
    total = len(published)
    strategy = get_user_strategy(db, user.id)

    coverage = {
        "published_total": total,
        "application_history": total > 0,
        "linkedin_engagement": "unavailable",
        "performance_learning": "not_available",
        "minimum_for_patterns": MIN_PUBLISHED_FOR_PATTERNS,
    }

    if total < MIN_PUBLISHED_FOR_PATTERNS:
        return {
            "source": SOURCE,
            "state": "INSUFFICIENT_DATA",
            "coverage": coverage,
            "insights": [],
            "recommendations": [],
            "strategy_alignment": [],
            "learning_context": {"recent_content": [], "strategy_priorities": [],
                                 "validated_learnings": []},
            "ai_summary": None,
            "performance_note": PERFORMANCE_UNAVAILABLE,
            "message": (
                f"You have {total} published posts. There isn't enough "
                "performance history yet to identify reliable content patterns."
                if total
                else "Learning hasn't started yet. Publish more content to "
                "build enough history for meaningful patterns."
            ),
        }

    confidence = _confidence(total)
    recent = published[:RECENT_WINDOW]
    insights = _distribution_insights(recent, confidence)
    insights += _consistency_insights(published, strategy, confidence)
    alignment = _alignment_insights(recent, strategy, confidence)
    recommendations = [
        {"title": i["title"], "reason": i["evidence"], "confidence": confidence}
        for i in insights + alignment
        if i.get("recommendation")
    ]
    context = _learning_context(recent, strategy, insights + alignment)
    facts = [i["evidence"] for i in insights + alignment]
    return {
        "source": SOURCE,
        "state": confidence,
        "coverage": coverage,
        "insights": insights,
        "recommendations": recommendations,
        "strategy_alignment": alignment,
        "learning_context": context,
        "ai_summary": _ai_summary(settings, facts),
        "performance_note": PERFORMANCE_UNAVAILABLE,
    }
