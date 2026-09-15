"""M5 Research Agent: transient provider search plus user-owned saved items.

- Search results are transient and come from the configured research
  provider (mock by default, always labeled). Scores are transparent
  heuristics, never scientifically-validated claims.
- Saved items belong to the session user. Missing and foreign items both
  return 404 so ownership cannot be probed.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app import ai as ai_module
from app import research as research_module
from app.config import Settings, get_settings
from app.database import get_db
from app.models import ResearchItem, User
from app.security import get_current_user

router = APIRouter(prefix="/api/research", tags=["research"])

QUERY_MAX = 200
TITLE_MAX = 255
SUMMARY_MAX = 5000
URL_MAX = 1024
ANGLE_MAX = 2000

NOT_CONFIGURED = "research_provider_not_configured"
AI_NOT_CONFIGURED = "ai_provider_not_configured"

SCORING_NOTE = (
    "Heuristic estimate based on query overlap and observation time, not a "
    "validated measure. Mock items carry no publication dates."
)


def _missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="not_found"
    )


def _check_str(value, name: str, max_len: int, required: bool = False) -> str:
    text = value if isinstance(value, str) else ""
    if required and not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_required"
        )
    if len(text) > max_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_too_long"
        )
    return text


def _clamp_score(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def _item_public(item: ResearchItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "summary": item.summary,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "topic": item.topic,
        "relevance_score": item.relevance_score,
        "freshness_score": item.freshness_score,
        "linkedin_angle": item.linkedin_angle,
        "status": item.status,
    }


@router.post("/search")
def search(
    payload: dict,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ = user
    query = _check_str(payload.get("query", ""), "query", QUERY_MAX, required=True)
    try:
        provider = research_module.get_research_provider(settings.research_provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_CONFIGURED
        ) from exc
    return {
        "query": query.strip(),
        "results": provider.search(query.strip()),
        "mock": provider.name == "mock",
        "scoring": {"method": "heuristic", "note": SCORING_NOTE},
    }


@router.get("/items")
def list_items(
    item_status: str = "saved",
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    if item_status not in ("saved", "ignored"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status"
        )
    items = (
        db.query(ResearchItem)
        .filter_by(user_id=user.id, status=item_status)
        .order_by(ResearchItem.updated_at.desc())
        .limit(100)
        .all()
    )
    return {"items": [_item_public(item) for item in items]}


@router.get("/items/{item_id}")
def read_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = (
        db.query(ResearchItem)
        .filter_by(id=item_id, user_id=user.id)
        .one_or_none()
    )
    if item is None:
        raise _missing()
    return _item_public(item)


@router.post("/items", status_code=status.HTTP_201_CREATED)
def save_item(
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = ResearchItem(
        user_id=user.id,
        title=_check_str(payload.get("title", ""), "title", TITLE_MAX, required=True),
        summary=_check_str(payload.get("summary", ""), "summary", SUMMARY_MAX),
        source_name=_check_str(
            payload.get("source_name", payload.get("source", "")), "source_name", TITLE_MAX
        ),
        source_url=_check_str(
            payload.get("source_url", payload.get("url", "")), "source_url", URL_MAX
        ),
        topic=_check_str(payload.get("topic", ""), "topic", TITLE_MAX),
        relevance_score=_clamp_score(payload.get("relevance_score", 0.0)),
        freshness_score=_clamp_score(payload.get("freshness_score", 0.0)),
        linkedin_angle=_check_str(
            payload.get("linkedin_angle", payload.get("potential_angle", "")),
            "linkedin_angle",
            ANGLE_MAX,
        ),
        status="saved",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_public(item)


@router.post("/items/{item_id}/ignore")
def ignore_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = (
        db.query(ResearchItem)
        .filter_by(id=item_id, user_id=user.id)
        .one_or_none()
    )
    if item is None:
        raise _missing()
    item.status = "ignored"
    db.commit()
    db.refresh(item)
    return _item_public(item)


@router.post("/angle")
def linkedin_angle(
    payload: dict,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ = user
    title = _check_str(payload.get("title", ""), "title", TITLE_MAX)
    summary = _check_str(payload.get("summary", ""), "summary", SUMMARY_MAX)
    topic = _check_str(payload.get("topic", ""), "topic", TITLE_MAX)
    if not (title.strip() or summary.strip() or topic.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="input_required"
        )
    try:
        provider = ai_module.get_ai_provider(settings.ai_provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=AI_NOT_CONFIGURED
        ) from exc
    prompt = (
        "Suggest one concise LinkedIn angle (educational, technical insight, "
        "developer impact, opinion, or practical lesson)."
    )
    if topic.strip():
        prompt += f" Topic: {topic.strip()}."
    if title.strip():
        prompt += f" Research title: {title.strip()}."
    if summary.strip():
        prompt += f" Summary: {summary.strip()}."
    text = provider.generate(prompt).get("text", "")
    return {"angle": text, "mock": provider.name == "mock"}
