"""FastAPI entrypoint. M0: health + honest integration status only."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.database_url)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LinkedIn AI", version="0.0.0-m0")

    app.router.lifespan_context = lifespan
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", **settings.public_summary()}

    @app.get("/api/health")
    def api_health() -> dict:
        return health()

    @app.get("/api/status")
    def integration_status() -> dict:
        """Honest capability flags. Nothing here claims real integrations."""
        return {
            "backend": "IMPLEMENTED",
            "google_auth": "NOT CONFIGURED",
            "linkedin_oauth": "NOT CONFIGURED",
            "linkedin_publishing": "NOT CONFIGURED",
            "analytics": "NOT CONFIGURED",
            "ai": "MOCK" if settings.ai_provider == "mock" else "NOT CONFIGURED",
            "research": (
                "MOCK" if settings.research_provider == "mock" else "NOT CONFIGURED"
            ),
        }

    return app


app = create_app()
