"""AI Command Center: natural-language control over existing capabilities.

A small deterministic intent router — no agent framework, no arbitrary code
execution. Every intent maps to an already-existing application operation
(studio, research, strategy, analytics, learning, calendar). Destructive or
consequential operations (schedule, strategy update) require an explicit
two-step confirmation. Publishing and deletion are NEVER executed here;
they stay behind their existing human-approval UI.
"""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app import ai as ai_module
from app.config import Settings, get_settings
from app.database import get_db
from app.models import ContentItem, User
from app.security import get_current_user
from app.strategy import (
    FREQUENCIES,
    get_user_strategy,
    strategy_context_text,
)

router = APIRouter(prefix="/api/commands", tags=["commands"])

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

def _fail(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _user_tz_name(db: DbSession, user_id: int) -> str:
    name = (get_user_strategy(db, user_id).get("timezone") or "").strip()
    if name:
        try:
            ZoneInfo(name)
            return name
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return "UTC"


def _latest_draft(db: DbSession, user_id: int):
    return (
        db.query(ContentItem)
        .filter_by(user_id=user_id)
        .filter(ContentItem.status.in_(("idea", "draft", "approved")))
        .order_by(ContentItem.updated_at.desc())
        .first()
    )


def _last_published(db: DbSession, user_id: int):
    return (
        db.query(ContentItem)
        .filter_by(user_id=user_id, status="published")
        .order_by(ContentItem.published_at.desc())
        .first()
    )


def _resolve_draft(db: DbSession, user_id: int, text: str):
    """Resolve 'latest draft' or 'draft <id>' to an owned item or None."""
    match = re.search(r"draft\s+#?(\d+)", text)
    if match:
        return (
            db.query(ContentItem)
            .filter_by(id=int(match.group(1)), user_id=user_id)
            .one_or_none()
        )
    if "last published post" in text or "latest published" in text:
        return _last_published(db, user_id)
    if "latest draft" in text or "this draft" in text or "my draft" in text:
        return _latest_draft(db, user_id)
    if "latest post" in text or "this post" in text or "my post" in text:
        return _latest_draft(db, user_id)
    return None


def _parse_when(text: str, tz_name: str) -> tuple[datetime, str] | None:
    """Parse weekday/time expressions into an aware datetime. None if absent."""
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    now = datetime.now(timezone.utc).astimezone(zone)
    day_match = re.search(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b", text
    )
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
    if not day_match or not time_match:
        return None
    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    meridiem = time_match.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    word = day_match.group(1)
    if word == "today":
        day = now.date()
    elif word == "tomorrow":
        day = (now + timedelta(days=1)).date()
    else:
        delta = (WEEKDAYS[word] - now.weekday()) % 7
        day = (now + timedelta(days=delta)).date()
    try:
        moment = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
    except ValueError:
        return None
    if moment <= now:
        moment += timedelta(days=7)
    label = (
        moment.strftime("%A")
        + f" at {moment.hour % 12 or 12}:{moment.minute:02d} "
        + ("PM" if moment.hour >= 12 else "AM")
        + f" ({tz_name})"
    )
    return moment, label


def _quoted_or_rest(text: str, keywords: list[str]) -> str:
    """Extract a quoted span, else the text after the last keyword."""
    quoted = re.search(r'"([^"]{2,200})"', text)
    if quoted:
        return quoted.group(1).strip()
    lowered = text
    cut = 0
    for keyword in keywords:
        at = lowered.find(keyword)
        if at != -1:
            cut = max(cut, at + len(keyword))
    rest = text[cut:].strip(" .:")
    rest = re.sub(r"^(about|on)\s+", "", rest)
    return rest[:300]


def route_command(text: str) -> tuple[str, dict]:
    """Deterministic intent routing. Returns (intent, params)."""
    t = (text or "").lower().strip()
    if not t:
        return "UNKNOWN", {}

    def has(*words):
        return any(w in t for w in words)

    showy = has("show", "list", "what", "display", "view")
    if has("unschedule", "cancel schedule", "cancel the schedul"):
        return "UNSCHEDULE_HELP", {}
    if has("delete", "remove") and ("draft" in t or "post" in t):
        return "DELETE_REFUSED", {}
    if has("repurpose", "new angle", "different angle"):
        return "REPURPOSE_POST", {}
    if showy and has("scheduled", "calendar", "upcoming", "planned"):
        return "SHOW_CALENDAR", {}
    if has("published", "live post") and ("show" in t or "list" in t or "recent" in t or "what" in t or "view" in t):
        return "SHOW_PUBLISHED", {}
    if has("publish") and (
        "my draft" in t or "latest draft" in t or "this draft" in t
        or "publish it" in t or "publish my" in t or "publish this" in t
    ):
        return "PUBLISH_REFUSED", {}
    if (has("schedule") and not showy) or (
        ("friday" in t or "monday" in t or "tuesday" in t or "wednesday" in t
         or "thursday" in t or "saturday" in t or "sunday" in t or "tomorrow" in t)
        and ("draft" in t or "post" in t or "this" in t)
        and not showy
    ):
        return "SCHEDULE_POST", {}
    if has("disconnect") and "linkedin" in t:
        return "LINKEDIN_STATUS", {"hint": "disconnect"}
    if "linkedin" in t and has("connect", "status", "connected"):
        return "LINKEDIN_STATUS", {}
    if has("strateg") and has("show", "view", "what is", "display"):
        return "SHOW_STRATEGY", {}
    if (has("strateg") and has("update", "change", "set")) or (
        has("posting frequency", "target audience", "preferred days")
        and has("set", "change", "update")
    ):
        return "UPDATE_STRATEGY", {}
    if has("analytic", "performance", "how am i doing", "stats"):
        return "SHOW_ANALYTICS", {}
    if has("how is my", "how's my") and has("content", "performing", "doing"):
        return "SHOW_ANALYTICS", {}
    if has("review", "critique", "feedback", "analyze", "analyse", "reject"):
        return "REVIEW_DRAFT", {}
    if has("draft"):
        return "SHOW_DRAFTS", {}
    if has("shorter", "rewrite", "hook", "tone", "hashtag", "cta", "improve", "simplif", "expand"):
        return "REWRITE_DRAFT", {}
    if has("idea"):
        return "CREATE_IDEAS", {}
    if has("research", "topics", "find", "trends", "news"):
        return "RESEARCH", {}
    if has("achievement"):
        return "CREATE_FROM_ACHIEVEMENT", {}
    if has("certificat"):
        return "CREATE_FROM_CERTIFICATE", {}
    if has("resume", "cv", "profile"):
        return "CREATE_FROM_RESUME", {}
    if has("github", "repo"):
        return "CREATE_FROM_GITHUB", {}
    if has("article", "url", "http"):
        return "CREATE_FROM_URL", {}
    if has("rough thought", "messy", "notes"):
        return "CREATE_FROM_THOUGHT", {}
    if has("voice", "transcri"):
        return "CREATE_FROM_VOICE", {}
    if has("screenshot", "image", "photo"):
        return "CREATE_FROM_SCREENSHOT", {}
    if has("video"):
        return "CREATE_FROM_VIDEO", {}
    if has("help", "what can you", "commands", "how do i"):
        return "HELP", {}
    if has("post", "write", "create", "draft", "generate", "compose"):
        return "CREATE_POST", {}
    return "UNKNOWN", {}


def _ai_text(settings: Settings, prompt: str) -> tuple[str, bool]:
    try:
        provider = ai_module.get_ai_provider(settings.ai_provider, settings=settings)
    except ValueError as exc:
        raise _fail("ai_provider_not_configured", status.HTTP_501_NOT_IMPLEMENTED) from exc
    try:
        out = provider.generate(prompt)
    except ai_module.AIProviderError as exc:
        raise _fail(exc.detail, status.HTTP_502_BAD_GATEWAY) from exc
    return out.get("text", ""), provider.name == "mock"


@router.post("")
def run_command(
    payload: dict,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    text = payload.get("text", "") if isinstance(payload, dict) else ""
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise _fail("invalid_command")
    text = text.strip()
    confirmed = payload.get("confirmed") is True
    proposal = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else {}
    intent, _ = route_command(text)

    if intent == "UNKNOWN":
        return {
            "intent": intent,
            "message": "I didn't understand that command. Try 'help' to see what I can do.",
            "action": {"kind": "none"},
        }
    if intent == "HELP":
        return {
            "intent": intent,
            "message": (
                "I can create posts and ideas, research topics, review and rewrite "
                "drafts, show drafts, scheduled posts, analytics, and strategy, "
                "schedule approved drafts, and report LinkedIn status. "
                "Publishing and deletion always stay in their approval UI."
            ),
            "action": {"kind": "none"},
        }
    if intent == "PUBLISH_REFUSED":
        return {
            "intent": intent,
            "message": "Publishing needs human approval. Open the draft in Content Studio, review it, approve it, then publish from there.",
            "action": {"kind": "navigate", "href": "/drafts"},
        }
    if intent == "DELETE_REFUSED":
        return {
            "intent": intent,
            "message": "I don't delete content by command. Open Drafts to review and delete with confirmation.",
            "action": {"kind": "navigate", "href": "/drafts"},
        }
    if intent == "UNSCHEDULE_HELP":
        return {
            "intent": intent,
            "message": "Open the calendar to reschedule or unschedule with confirmation.",
            "action": {"kind": "navigate", "href": "/calendar"},
        }

    if intent == "CREATE_POST":
        topic = _quoted_or_rest(text.lower(), ["about", "on", "post", "create", "write", "generate"])
        if not topic:
            return {
                "intent": intent,
                "message": "What should the post be about? For example: create a post about \"onboarding checklists\".",
                "action": {"kind": "none"},
            }
        strategy_text = ""
        try:
            from app.strategy import get_user_strategy, strategy_context_text

            strategy_text = strategy_context_text(get_user_strategy(db, user.id))[:600]
        except Exception:
            strategy_text = ""
        prompt = f"Task: generate a new draft. Topic: {topic}."
        if strategy_text:
            prompt += f" Profile context: {strategy_text}."
        generated, is_mock = _ai_text(settings, prompt)
        return {
            "intent": intent,
            "message": "Draft generated below. Review it in Content Studio before saving." + (" (Mock AI — configure a provider for real generation.)" if is_mock else ""),
            "mock": is_mock,
            "action": {"kind": "studio_prefill", "topic": topic, "notes": "", "body": generated},
        }

    if intent == "CREATE_IDEAS":
        strategy = {}
        try:
            from app.strategy import get_user_strategy

            strategy = get_user_strategy(db, user.id)
        except Exception:
            strategy = {}
        topics = [t for t in strategy.get("preferred_topics", []) if isinstance(t, str)][:5]
        types = [c for c in strategy.get("content_types", []) if isinstance(c, str)][:4]
        from_strategy = bool(topics)
        if not topics:
            topics = ["developer productivity", "learning in public", "code quality"]
        ideas = []
        for i, topic in enumerate(topics[:3]):
            kind = types[i % len(types)] if types else "educational"
            ideas.append({"topic": topic, "content_type": kind})
        return {
            "intent": intent,
            "message": (
                f"Here are {len(ideas)} post ideas from your strategy and interests."
                if from_strategy
                else f"Here are {len(ideas)} starter ideas. Set preferred topics in Strategy for personalized ones."
            ),
            "ideas": ideas,
            "action": {"kind": "navigate", "href": "/studio"},
        }

    if intent == "RESEARCH":
        topic = _quoted_or_rest(text.lower(), ["about", "on", "research", "find", "topics"])
        if not topic:
            return {
                "intent": intent,
                "message": 'Which topic should I research? For example: find AI topics I can post about.',
                "action": {"kind": "none"},
            }
        try:
            from app import research as research_module

            provider = research_module.get_research_provider(settings.research_provider)
        except ValueError as exc:
            raise _fail("research_provider_not_configured", status.HTTP_501_NOT_IMPLEMENTED) from exc
        results = provider.search(topic[:120])
        return {
            "intent": intent,
            "message": f"Found {len(results)} signals for '{topic}'.",
            "mock": provider.name == "mock",
            "results": [
                {"title": r.get("title", ""), "summary": r.get("summary", ""), "angle": r.get("linkedin_angle", "")}
                for r in results
            ],
            "action": {"kind": "navigate", "href": "/research"},
        }

    if intent in ("REVIEW_DRAFT", "REWRITE_DRAFT", "REPURPOSE_POST"):
        item = _resolve_draft(db, user.id, text.lower())
        if item is None:
            return {
                "intent": intent,
                "message": "Which draft? Say 'latest draft' or give its title from Drafts.",
                "action": {"kind": "navigate", "href": "/drafts"},
            }
        if intent == "REVIEW_DRAFT":
            from app.studio import heuristic_review

            result = heuristic_review(item.body or "")
            weak = [d["label"] for d in result["dimensions"] if d["status"] == "needs_work"]
            summary = f"Quality {result['score']}/100."
            if weak:
                summary += " Needs work: " + ", ".join(weak) + "."
            return {
                "intent": intent,
                "message": summary,
                "review": result,
                "action": {"kind": "navigate", "href": f"/studio?id={item.id}"},
            }
        action = "alternatives" if intent == "REPURPOSE_POST" else "shorten"
        for keyword, name in (
            ("hook", "improve_hook"), ("cta", "improve_cta"), ("hashtag", "improve_hashtags"),
            ("tone", "tone_professional"), ("expand", "expand"), ("simpl", "simplify"),
        ):
            if keyword in text.lower():
                action = name
        rewrite_prompt = (
            f"Task: {action}. Topic: {item.title or 'draft'}. "
            f"Current draft:\n{item.body or ''}"
        )
        rewritten, is_mock = _ai_text(settings, rewrite_prompt)
        return {
            "intent": intent,
            "message": "Rewritten below. Apply it in Content Studio after review." + (" (Mock AI.)" if is_mock else ""),
            "mock": is_mock,
            "action": {
                "kind": "studio_prefill",
                "topic": item.title or "",
                "notes": "",
                "body": rewritten,
                "draft_id": item.id,
            },
        }

    if intent.startswith("CREATE_FROM_"):
        kinds = {
            "CREATE_FROM_ACHIEVEMENT": ("achievement details (what happened, result, lesson)", "/studio"),
            "CREATE_FROM_CERTIFICATE": ("certificate upload", "/studio"),
            "CREATE_FROM_RESUME": ("resume upload on the Strategy page", "/strategy"),
            "CREATE_FROM_GITHUB": ("repository URL", "/studio"),
            "CREATE_FROM_URL": ("article URL", "/studio"),
            "CREATE_FROM_THOUGHT": ("rough notes", "/studio"),
            "CREATE_FROM_VOICE": ("voice note", "/studio"),
            "CREATE_FROM_SCREENSHOT": ("screenshot upload", "/studio"),
            "CREATE_FROM_VIDEO": ("video upload", "/studio"),
        }
        need, href = kinds[intent]
        return {
            "intent": intent,
            "message": f"To create from that source I need the {need}. Open the create dialog and choose it there.",
            "action": {"kind": "navigate", "href": href},
        }

    if intent == "SCHEDULE_POST":
        item = _resolve_draft(db, user.id, text.lower())
        if item is None:
            return {
                "intent": intent,
                "message": "Which draft should I schedule? Say 'latest draft' or pick one in Drafts.",
                "action": {"kind": "navigate", "href": "/drafts"},
            }
        if item.status != "approved":
            return {
                "intent": intent,
                "message": "That draft isn't approved yet. Approve it in Content Studio first, then schedule.",
                "action": {"kind": "navigate", "href": f"/studio?id={item.id}"},
            }
        tz_name = _user_tz_name(db, user.id)
        parsed = _parse_when(text.lower(), tz_name)
        if parsed is None:
            return {
                "intent": intent,
                "message": "When should it go out? For example: schedule for Friday at 7 PM.",
                "action": {"kind": "none"},
            }
        moment, label = parsed
        iso = moment.isoformat()
        if not confirmed or proposal.get("draft_id") != item.id or proposal.get("at") != iso:
            return {
                "intent": intent,
                "needs_confirmation": True,
                "proposal": {"draft_id": item.id, "at": iso, "timezone": tz_name, "label": label},
                "message": f"Schedule '{item.title or '(untitled)'}' for {label}? Confirm to proceed.",
                "action": {"kind": "none"},
            }
        from app.studio import _get_owned, _item_public, _parse_schedule

        try:
            instant, zone = _parse_schedule({"scheduled_at": iso, "timezone": tz_name})
        except HTTPException as exc:
            raise _fail(exc.detail) from exc
        owned = _get_owned(db, user.id, item.id)
        if owned is None:
            raise _fail("not_found", status.HTTP_404_NOT_FOUND)
        owned.scheduled_at = instant
        owned.scheduled_tz = zone
        owned.status = "scheduled"
        db.commit()
        db.refresh(owned)
        return {
            "intent": intent,
            "message": f"Scheduled for {label}.",
            "scheduled": _item_public(owned),
            "action": {"kind": "navigate", "href": "/calendar"},
        }

    if intent == "SHOW_DRAFTS":
        rows = (
            db.query(ContentItem)
            .filter_by(user_id=user.id)
            .filter(ContentItem.status.in_(("idea", "draft", "approved")))
            .order_by(ContentItem.updated_at.desc())
            .limit(10)
            .all()
        )
        return {
            "intent": intent,
            "message": f"You have {len(rows)} open drafts." if rows else "No open drafts.",
            "items": [{"id": r.id, "title": r.title, "status": r.status} for r in rows],
            "action": {"kind": "navigate", "href": "/drafts"},
        }

    if intent == "SHOW_PUBLISHED":
        rows = (
            db.query(ContentItem)
            .filter_by(user_id=user.id, status="published")
            .order_by(ContentItem.published_at.desc())
            .limit(10)
            .all()
        )
        return {
            "intent": intent,
            "message": f"{len(rows)} published posts." if rows else "Nothing published yet.",
            "items": [{"id": r.id, "title": r.title} for r in rows],
            "action": {"kind": "navigate", "href": "/published"},
        }

    if intent == "SHOW_CALENDAR":
        return {
            "intent": intent,
            "message": "Opening your calendar.",
            "action": {"kind": "navigate", "href": "/calendar"},
        }

    if intent == "SHOW_ANALYTICS":
        return {
            "intent": intent,
            "message": "Opening analytics (application publishing data; LinkedIn engagement is unavailable).",
            "action": {"kind": "navigate", "href": "/analytics"},
        }

    if intent == "SHOW_STRATEGY":
        return {
            "intent": intent,
            "message": "Opening your strategy.",
            "action": {"kind": "navigate", "href": "/strategy"},
        }

    if intent == "UPDATE_STRATEGY":
        updates: dict = {}
        freq = re.search(r"frequency\s*(?:to|=|:)?\s*([a-z0-9_/]+)", text.lower())
        if freq and freq.group(1) in FREQUENCIES:
            updates["posting_frequency"] = freq.group(1)
        audience = re.search(r"audience\s*(?:to|=|:)?\s*([^.,;]{2,120})", text.lower())
        if audience:
            updates["target_audience"] = audience.group(1).strip()
        if not updates:
            return {
                "intent": intent,
                "message": "I can update posting frequency (daily, 3x_week, weekly, 2x_month, custom) or target audience. For example: set posting frequency to weekly.",
                "action": {"kind": "none"},
            }
        if not confirmed or proposal != updates:
            return {
                "intent": intent,
                "needs_confirmation": True,
                "proposal": updates,
                "message": "Apply this strategy change? " + ", ".join(f"{k} = {v}" for k, v in updates.items()),
                "action": {"kind": "none"},
            }
        from app.strategy import TEXT_FIELDS, UserStrategy, strategy_public

        safe = {k: v for k, v in updates.items() if k in TEXT_FIELDS}
        row = db.query(UserStrategy).filter_by(user_id=user.id).one_or_none()
        data = strategy_public(row)
        data.update(safe)
        if row is None:
            row = UserStrategy(user_id=user.id)
            db.add(row)
        for field in TEXT_FIELDS:
            setattr(row, field, data[field])
        db.commit()
        return {
            "intent": intent,
            "message": "Strategy updated: " + ", ".join(f"{k} = {v}" for k, v in safe.items()),
            "action": {"kind": "navigate", "href": "/strategy"},
        }

    if intent == "LINKEDIN_STATUS":
        from app.models import LinkedInAccount

        account = db.query(LinkedInAccount).filter_by(user_id=user.id).one_or_none()
        if account is None:
            return {
                "intent": intent,
                "message": "LinkedIn is not connected. Connect it in Settings.",
                "action": {"kind": "navigate", "href": "/settings"},
            }
        label = "Mock Member (development)" if account.is_mock else (account.linkedin_name or "LinkedIn member")
        return {
            "intent": intent,
            "message": f"LinkedIn connected as {label}. Disconnect any time in Settings.",
            "action": {"kind": "navigate", "href": "/settings"},
        }

    raise _fail("invalid_command")
