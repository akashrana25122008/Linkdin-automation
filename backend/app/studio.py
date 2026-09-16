"""M4 Content Studio: user-owned content CRUD, one AI action endpoint,
and a heuristic quality review.

- Every query is scoped to the session user. Missing and foreign items both
  return 404 so ownership cannot be probed.
- AI goes through the configured provider from app.ai (mock by default).
  Unconfigured providers fail with 501, never fabricated output.
- Quality scoring is deterministic and heuristic; factual verification is
  never claimed.
"""

import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app import ai as ai_module
from app import publishing as publishing_module
from app.config import Settings, get_settings
from app.database import get_db
from app.linkedin_oauth import decrypt_token
from app.models import (
    CONTENT_STATUSES,
    CONTENT_TYPES,
    ContentItem,
    LinkedInAccount,
    User,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/studio", tags=["studio"])

TITLE_MAX = 255
BODY_MAX = 20000
TOPIC_MAX = 500
CONTEXT_MAX = 2000

AI_ACTIONS = (
    "generate",
    "improve_hook",
    "shorten",
    "expand",
    "simplify",
    "tone_technical",
    "tone_personal",
    "tone_professional",
    "improve_cta",
    "improve_hashtags",
    "alternatives",
)

# Studio may only move items between early stages; scheduled/published
# belong to the later Calendar/Publishing milestones.
STUDIO_STATUSES = ("idea", "draft", "approved")

NOT_CONFIGURED = "ai_provider_not_configured"

GENERIC_PHRASES = (
    "in today's fast-paced world",
    "game-changer",
    "game changer",
    "supercharge",
    "delve into",
    "unlock the power",
    "revolutionize",
    "cutting-edge",
    "synergy",
    "thought leader",
)

CTA_MARKERS = (
    "?",
    "comment",
    "share",
    "thoughts",
    "agree",
    "follow",
    "link in",
    "subscribe",
    "message me",
)

VALUE_MARKERS = (
    "how to",
    "lesson",
    "learned",
    "mistake",
    "framework",
    "steps",
    "tip",
)

STOPWORDS = set(
    "a an the and or but if then so of on in to for with is are was were be "
    "been it its this that these those i you he she we they my your our their "
    "me him her us them as at by from up out about into over after no not do "
    "does did can will just than too very".split()
)


def _aware_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _item_public(item: ContentItem) -> dict:
    scheduled = item.scheduled_at
    if scheduled is not None and scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    published = item.published_at
    if published is not None and published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "content_type": item.content_type,
        "status": item.status,
        "scheduled_at": scheduled.isoformat() if scheduled else None,
        "scheduled_tz": item.scheduled_tz or ("UTC" if scheduled else None),
        "linkedin_post_id": item.linkedin_post_id,
        "published_at": published.isoformat() if published else None,
        "publish_error": item.publish_error or "",
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _get_owned(db: DbSession, user_id: int, item_id: int) -> ContentItem | None:
    return (
        db.query(ContentItem)
        .filter_by(id=item_id, user_id=user_id)
        .one_or_none()
    )


def _missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="not_found"
    )


def _provider(settings: Settings):
    try:
        return ai_module.get_ai_provider(settings.ai_provider)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=NOT_CONFIGURED
        ) from exc


def _check_str(value, name: str, max_len: int, required: bool = False) -> str:
    text = value if isinstance(value, str) else ""
    text = text.strip() if required else text
    if required and not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_required"
        )
    if len(value if isinstance(value, str) else "") > max_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name}_too_long"
        )
    return value if isinstance(value, str) else ""


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    content_type = payload.get("content_type", "educational")
    item_status = payload.get("status", "draft")
    if content_type not in CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_content_type"
        )
    if item_status not in STUDIO_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status"
        )
    item = ContentItem(
        user_id=user.id,
        title=_check_str(payload.get("title", ""), "title", TITLE_MAX),
        body=_check_str(payload.get("body", ""), "body", BODY_MAX),
        content_type=content_type,
        status=item_status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_public(item)


@router.get("/items")
def list_items(
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    items = (
        db.query(ContentItem)
        .filter_by(user_id=user.id)
        .order_by(ContentItem.updated_at.desc())
        .limit(50)
        .all()
    )
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "preview": (item.body or "")[:160],
                "content_type": item.content_type,
                "status": item.status,
                "linkedin_post_id": item.linkedin_post_id,
                "published_at": _aware_iso(item.published_at),
                "publish_error": item.publish_error or "",
                "created_at": (
                    item.created_at.isoformat() if item.created_at else None
                ),
                "updated_at": (
                    item.updated_at.isoformat() if item.updated_at else None
                ),
            }
            for item in items
        ]
    }


@router.get("/items/{item_id}")
def read_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    return _item_public(item)


@router.patch("/items/{item_id}")
def update_item(
    item_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    if "title" in payload:
        item.title = _check_str(payload["title"], "title", TITLE_MAX)
    if "body" in payload:
        item.body = _check_str(payload["body"], "body", BODY_MAX)
    if "content_type" in payload:
        if payload["content_type"] not in CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_content_type",
            )
        item.content_type = payload["content_type"]
    if "status" in payload:
        if payload["status"] not in STUDIO_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status"
            )
        if item.scheduled_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="unschedule_first"
            )
        item.status = payload["status"]
    db.commit()
    db.refresh(item)
    return _item_public(item)


@router.post("/items/{item_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    source = _get_owned(db, user.id, item_id)
    if source is None:
        raise _missing()
    base = (source.title or "").strip() or "Untitled"
    copy = ContentItem(
        user_id=user.id,
        title=f"{base} Copy"[:TITLE_MAX],
        body=source.body,
        content_type=source.content_type,
        # A copy is new work: never inherit schedule or publishing state,
        # which would otherwise display a status that was never earned
        # and cannot be changed or republished.
        status="draft",
    )
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return _item_public(copy)


@router.delete("/items/{item_id}")
def delete_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    db.delete(item)
    db.commit()
    return {"status": "ok"}


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_schedule(payload: dict) -> tuple[datetime, str]:
    """Validate scheduling input. Returns (naive UTC instant, IANA timezone).

    Rejects missing/malformed timestamps, naive timestamps (ambiguous),
    unknown timezones, and past times. Never adjusts the requested time.
    """
    raw = payload.get("scheduled_at", "")
    tz_name = payload.get("timezone", "")
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="scheduled_at_required"
        )
    if not isinstance(tz_name, str) or not tz_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="timezone_required"
        )
    try:
        zone = ZoneInfo(tz_name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_timezone"
        )
    try:
        moment = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed_schedule"
        ) from exc
    if moment.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="timezone_required"
        )
    instant = moment.astimezone(timezone.utc)
    if instant <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="past_time"
        )
    return instant.replace(tzinfo=None), zone.key


@router.get("/scheduled")
def scheduled_range(
    start: str,
    end: str,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    """Own scheduled items within [start, end]. Bounded to 93 days."""
    try:
        start_dt = _naive_utc(datetime.fromisoformat(start))
        end_dt = _naive_utc(datetime.fromisoformat(end))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed_range"
        ) from exc
    if end_dt < start_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="malformed_range"
        )
    if (end_dt - start_dt).days > 93:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="range_too_large"
        )
    items = (
        db.query(ContentItem)
        .filter_by(user_id=user.id, status="scheduled")
        .filter(ContentItem.scheduled_at.is_not(None))
        .filter(ContentItem.scheduled_at >= start_dt)
        .filter(ContentItem.scheduled_at <= end_dt)
        .order_by(ContentItem.scheduled_at.asc())
        .limit(200)
        .all()
    )
    return {"items": [_item_public(item) for item in items]}


@router.post("/items/{item_id}/schedule")
def schedule_item(
    item_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    if item.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="approval_required"
        )
    instant, tz_name = _parse_schedule(payload)
    item.scheduled_at = instant
    item.scheduled_tz = tz_name
    item.status = "scheduled"
    db.commit()
    db.refresh(item)
    return _item_public(item)


@router.post("/items/{item_id}/reschedule")
def reschedule_item(
    item_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    if item.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="not_scheduled"
        )
    instant, tz_name = _parse_schedule(payload)
    item.scheduled_at = instant
    item.scheduled_tz = tz_name
    db.commit()
    db.refresh(item)
    return _item_public(item)


@router.post("/items/{item_id}/unschedule")
def unschedule_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    if item.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="not_scheduled"
        )
    item.scheduled_at = None
    item.scheduled_tz = None
    item.status = "approved"
    db.commit()
    db.refresh(item)
    return _item_public(item)


PUBLISHABLE_STATUSES = ("approved", "scheduled", "failed")


def _account_scopes(account: LinkedInAccount) -> list[str]:
    try:
        scopes = json.loads(account.scopes or "[]")
    except ValueError:
        return []
    return scopes if isinstance(scopes, list) else []


@router.post("/items/{item_id}/publish")
def publish_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    item = _get_owned(db, user.id, item_id)
    if item is None:
        raise _missing()
    if item.status == "published" and item.linkedin_post_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_published"
        )
    if item.status not in PUBLISHABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="not_approved"
        )
    text = item.body if isinstance(item.body, str) else ""
    if not text.strip() or len(text) > publishing_module.TEXT_MAX:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_content",
        )
    account = db.query(LinkedInAccount).filter_by(user_id=user.id).one_or_none()
    use_mock = settings.linkedin_mode == "mock" or (
        account is not None and account.is_mock
    )
    if use_mock:
        result = publishing_module.mock_publish(item.id)
        item.status = "published"
        item.linkedin_post_id = result["post_id"]
        item.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
        item.publish_error = ""
        db.commit()
        db.refresh(item)
        return {**_item_public(item), "mock": True}
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="linkedin_not_connected"
        )
    if publishing_module.PUBLISH_SCOPE not in _account_scopes(account):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="missing_scope"
        )
    try:
        access_token = decrypt_token(settings, account.access_token_encrypted)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="linkedin_token_error"
        ) from exc
    try:
        result = publishing_module.real_publish(
            access_token, account.linkedin_member_id, text
        )
    except publishing_module.PublishTimeoutUnknown as exc:
        item.publish_error = exc.detail
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail
        ) from exc
    except publishing_module.PublishUpstreamError as exc:
        item.status = "failed"
        item.publish_error = exc.detail
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.detail
        ) from exc
    item.status = "published"
    item.linkedin_post_id = result["post_id"]
    item.published_at = datetime.now(timezone.utc).replace(tzinfo=None)
    item.publish_error = ""
    db.commit()
    db.refresh(item)
    return {**_item_public(item), "mock": False}


ACTION_LABELS = {
    "generate": "generate a new draft",
    "improve_hook": "rewrite only the opening hook",
    "shorten": "shorten while keeping the key insight",
    "expand": "expand with one concrete detail",
    "simplify": "simplify the language",
    "tone_technical": "shift toward a technical tone",
    "tone_personal": "shift toward a personal tone",
    "tone_professional": "shift toward a professional tone",
    "improve_cta": "improve only the closing call to action",
    "improve_hashtags": "suggest better hashtags",
    "alternatives": "produce an alternative version",
}


def _action_prompt(
    action: str,
    user: User,
    content: str,
    topic: str,
    content_type: str,
    context: str,
    variant: int = 0,
) -> str:
    name = user.name or user.email or "the author"
    base = f"Task: {ACTION_LABELS[action]}."
    if topic:
        base += f" Topic: {topic}."
    base += (
        f" LinkedIn post ({content_type}) for {name}. "
        "Natural professional writing, concrete wording, no motivational fluff, "
        "no exaggerated claims, restrained emoji use."
    )
    if context:
        base += f" Author notes: {context}."
    if action != "generate":
        base += f" Current draft:\n{content}"
    if variant:
        base += f" (variation {variant + 1})"
    return base


@router.post("/ai")
def ai_action(
    payload: dict,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    action = payload.get("action", "")
    if action not in AI_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_action"
        )
    content = _check_str(payload.get("content", ""), "content", BODY_MAX)
    topic = _check_str(
        payload.get("topic", ""),
        "topic",
        TOPIC_MAX,
        required=(action == "generate"),
    )
    if action != "generate":
        _check_str(content, "content", BODY_MAX, required=True)
    content_type = payload.get("content_type", "educational")
    if content_type not in CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_content_type"
        )
    context = _check_str(payload.get("context", ""), "context", CONTEXT_MAX)
    provider = _provider(settings)

    if action == "alternatives":
        texts = [
            provider.generate(
                _action_prompt(
                    action, user, content, topic, content_type, context, i
                )
            ).get("text", "")
            for i in range(3)
        ]
        return {"action": action, "mock": provider.name == "mock", "texts": texts}
    text = provider.generate(
        _action_prompt(action, user, content, topic, content_type, context)
    ).get("text", "")
    return {"action": action, "mock": provider.name == "mock", "text": text}


def _dim(key: str, label: str, verdict: str, detail: str) -> dict:
    return {"key": key, "label": label, "status": verdict, "detail": detail}


def heuristic_review(content: str) -> dict:
    """Deterministic heuristic review. Never claims external verification."""
    lowered = content.lower()
    words = re.findall(r"[a-z0-9'#]+", lowered)
    sentences = [s for s in re.split(r"[.!?\n]+", content) if s.strip()]
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    hook = lines[0] if lines else ""

    dims = []
    if not hook:
        dims.append(_dim("hook", "Hook", "needs_work", "No opening line found."))
    elif any(p in hook.lower() for p in GENERIC_PHRASES):
        dims.append(_dim("hook", "Hook", "needs_work", "Opening uses a generic AI-style phrase."))
    elif 20 <= len(hook) <= 200:
        dims.append(_dim("hook", "Hook", "strong", "Opening line is a focused length."))
    else:
        dims.append(_dim("hook", "Hook", "good", "Opening line could be tightened."))

    avg_len = len(words) / max(len(sentences), 1)
    dims.append(
        _dim(
            "clarity",
            "Clarity",
            "good" if avg_len <= 28 else "needs_work",
            f"Average sentence length is {avg_len:.0f} words.",
        )
    )

    if len(words) < 40:
        dims.append(_dim("readability", "Readability", "needs_work", "Too short to judge flow; expand the body."))
    elif len(words) <= 600:
        dims.append(_dim("readability", "Readability", "good", f"{len(words)} words, a readable length."))
    else:
        dims.append(_dim("readability", "Readability", "needs_work", f"{len(words)} words is long for one post."))

    freq: dict[str, int] = {}
    for word in words:
        if word not in STOPWORDS and len(word) > 3:
            freq[word] = freq.get(word, 0) + 1
    repeats = [w for w, c in freq.items() if c > max(3, len(words) // 25)]
    dims.append(
        _dim(
            "repetition",
            "Repetition",
            "good" if not repeats else "needs_work",
            "No notable repetition." if not repeats else f"Repeated terms: {', '.join(repeats[:3])}.",
        )
    )

    found = [p for p in GENERIC_PHRASES if p in lowered]
    dims.append(
        _dim(
            "generic_wording",
            "Generic wording",
            "good" if not found else "needs_work",
            "No generic AI filler detected." if not found else f"Generic phrasing: {', '.join(found[:3])}.",
        )
    )

    caps = [w for w in content.split() if w.isupper() and len(w) > 3]
    emoji = re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", content)
    if content.count("!") > 3 or len(caps) > 2 or len(emoji) > 3:
        dims.append(_dim("professional_tone", "Professional tone", "needs_work", "Tone down emphasis markers for a calmer voice."))
    else:
        dims.append(_dim("professional_tone", "Professional tone", "good", "Tone reads professionally."))

    has_value = bool(re.search(r"\d", content)) or any(m in lowered for m in VALUE_MARKERS)
    dims.append(
        _dim(
            "value",
            "Value to reader",
            "good" if has_value else "needs_work",
            "Contains concrete detail." if has_value else "Add one concrete detail, number, or lesson.",
        )
    )

    has_cta = any(m in lowered for m in CTA_MARKERS)
    dims.append(
        _dim(
            "cta",
            "CTA",
            "good" if has_cta else "needs_work",
            "Ends with reader engagement." if has_cta else "No clear call to action.",
        )
    )

    tags = re.findall(r"#\w+", content)
    if 3 <= len(tags) <= 8:
        dims.append(_dim("hashtags", "Hashtags", "good", f"{len(tags)} hashtags."))
    elif not tags:
        dims.append(_dim("hashtags", "Hashtags", "needs_work", "No hashtags; 3-5 relevant ones help."))
    else:
        dims.append(_dim("hashtags", "Hashtags", "good", f"{len(tags)} hashtags; trim if over 8."))

    score = sum(10 if d["status"] == "needs_work" else 2 if d["status"] == "good" else 0 for d in dims)
    score = max(20, min(98, 100 - score))
    return {"score": score, "dimensions": dims}


@router.post("/review")
def review(
    payload: dict,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    content = payload.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="content_required"
        )
    if len(content) > BODY_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="content_too_long"
        )
    result = heuristic_review(content)
    try:
        provider = ai_module.get_ai_provider(settings.ai_provider)
        summary = provider.generate(
            f"One-sentence quality summary for a LinkedIn draft by "
            f"{user.name or user.email or 'the author'} "
            f"(heuristic score {result['score']}/100)."
        ).get("text", "")
        mock = provider.name == "mock"
    except ValueError:
        summary = (
            f"Heuristic review scored this draft {result['score']}/100. "
            "AI provider not configured."
        )
        mock = False
    return {
        "score": result["score"],
        "method": "heuristic",
        "mock": mock,
        "summary": summary,
        "dimensions": result["dimensions"],
        "factual_note": "Potential factual concerns — verify claims before "
        "publishing. No external fact-checking was performed.",
    }
