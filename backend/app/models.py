"""M4 schema: User + Session + ContentItem with body and content type."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

