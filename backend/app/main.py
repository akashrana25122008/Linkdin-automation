"""FastAPI entrypoint. M12: + learning. Health, status, auth, dashboard, studio, research."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import analytics, auth, dashboard, learning, linkedin_oauth, research_api, strategy, studio
from app.config import get_settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.database_url)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    docs_on = (
        settings.docs_enabled
        if settings.docs_enabled is not None
        else settings.app_env != "production"
    )
    app = FastAPI(
        title="LinkedIn AI",
        version="0.8.0-m12",
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
        openapi_url="/openapi.json" if docs_on else None,
    )

    app.router.lifespan_context = lifespan
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        # Must cover every method the frontend uses; otherwise browsers
        # block PATCH/PUT/DELETE preflights and mutations silently fail.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
            "google_auth": (
                "READY" if settings.google_configured else "NOT CONFIGURED"
            ),
            "linkedin_oauth": (
                "READY" if settings.linkedin_configured else "NOT CONFIGURED"
            ),
            "linkedin_publishing": "NOT CONFIGURED",
            "analytics": "NOT CONFIGURED",
            "ai": "MOCK" if settings.ai_provider == "mock" else "NOT CONFIGURED",
            "research": (
                "MOCK" if settings.research_provider == "mock" else "NOT CONFIGURED"
            ),
        }

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(studio.router)
    app.include_router(research_api.router)
    app.include_router(strategy.router)
    app.include_router(linkedin_oauth.router)
    app.include_router(analytics.router)
    app.include_router(learning.router)

    return app


app = create_app()
