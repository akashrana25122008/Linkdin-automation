"""Application configuration. Secrets stay server-side; never expose to frontend."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "change-me-dev-only"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'app.db').as_posix()}"

    ai_provider: str = "mock"
    research_provider: str = "mock"
    linkedin_mode: str = "mock"

    @property
    def is_mock_mode(self) -> bool:
        return (
            self.ai_provider == "mock"
            and self.research_provider == "mock"
            and self.linkedin_mode == "mock"
        )

    def public_summary(self) -> dict:
        """Safe subset for /health and logs. Never includes secrets or keys."""
        return {
            "app_env": self.app_env,
            "ai_provider": self.ai_provider,
            "research_provider": self.research_provider,
            "linkedin_mode": self.linkedin_mode,
            "mock_mode": self.is_mock_mode,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
