"""SQLite foundation. Minimal for M0; full schema arrives with later milestones."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_engine_for(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


_engine = None
_SessionLocal = None


def init_db(database_url: str):
    """Initialize engine/session for the given URL. Creates tables + data dir."""
    global _engine, _SessionLocal
    if database_url.startswith("sqlite"):
        path = database_url.split("sqlite:///")[-1]
        if path != ":memory:":
            from pathlib import Path

            Path(path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine_for(database_url)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    from app import models  # noqa: F401 — register models

    Base.metadata.create_all(bind=_engine)
    return _engine


def get_session_local():
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionLocal


def get_db():
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()
