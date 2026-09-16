"""M4 schema: User + Session + ContentItem with body and content type."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Content lifecycle stages tracked by the dashboard pipeline.
CONTENT_STATUSES = ("idea", "draft", "approved", "scheduled", "published")

# Post directions supported by Content Studio (M4).
CONTENT_TYPES = (
    "educational",
    "technical",
    "project_showcase",
    "personal_learning",
    "hackathon",
    "career",
    "ai_tech_commentary",
    "storytelling",
    "tutorial",
    "opinion",
    "achievement_update",
)


class User(Base):
    """Application user. Identity comes from Google OAuth in M1 (not implemented)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    google_subject_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_picture: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserOwnedMixin:
    """Pattern for every future user-owned table: FK to users + NOT NULL.

    All queries on these tables MUST filter by the backend-derived user id
    (see app.security). Never accept user_id from the frontend.
    """

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class Session(Base):
    """Server-side application session. Only the SHA-256 hash is stored;
    the raw token lives in an HTTP-only cookie and is never logged."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContentItem(Base, UserOwnedMixin):
    """User-owned content record. Powers the dashboard pipeline and the M4
    Content Studio; full draft management arrives in M6."""

    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="educational"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="idea")
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_tz: Mapped[str | None] = mapped_column(String(64), nullable=True)
    linkedin_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    publish_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ResearchItem(Base, UserOwnedMixin):
    """User-owned saved research. Search results are transient; only
    explicitly saved items persist, with status saved or ignored."""

    __tablename__ = "research_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    relevance_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(nullable=False, default=0.0)
    linkedin_angle: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="saved")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserStrategy(Base):
    """One row per user with personal-brand configuration (M8).

    List fields are JSON-encoded string arrays in Text columns — the
    simplest durable shape for small user-edited lists. user_id is unique.
    """

    __tablename__ = "user_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    headline: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skills: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    projects: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    technologies: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    interests: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    target_audience: Mapped[str] = mapped_column(Text, nullable=False, default="")
    professional_goals: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    content_goals: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_topics: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    forbidden_topics: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    writing_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_types: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    posting_frequency: Mapped[str] = mapped_column(
        String(32), nullable=False, default=""
    )
    preferred_days: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    preferred_times: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LinkedInAccount(Base):
    """One LinkedIn member connection per application user (M9).

    The access token is stored Fernet-encrypted, server-side only. It is
    never serialized, logged, or sent to the frontend.
    """

    __tablename__ = "linkedin_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    linkedin_member_id: Mapped[str] = mapped_column(String(255), nullable=False)
    linkedin_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    linkedin_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_mock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LinkedInOAuthState(Base):
    """Single-use, expiring OAuth states bound to a user (CSRF protection)."""

    __tablename__ = "linkedin_oauth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

