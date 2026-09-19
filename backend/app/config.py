"""
Central configuration for SmartAlloc AI backend.

All values are overridable via environment variables / .env file.
Falls back to safe local defaults (SQLite + in-memory event bus) so the
application runs even when Postgres/Redis are not available, per the
"local deterministic fallback" engineering requirement.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Maestro AI"
    ENV: str = "development"

    # Database: defaults to local SQLite file so the app runs without Docker.
    # Set DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db to use Postgres.
    DATABASE_URL: str = "sqlite:///./smartalloc.db"

    # Redis: used for the event stream (disruption events). If unreachable,
    # the app transparently falls back to an in-process async event bus.
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str = "smartalloc-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # LLM (optional). If no key is set, the Explanation/Manager agents use a
    # deterministic template-based fallback so the app fully works offline.
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-5"

    # CORS
    # "localhost" and "127.0.0.1" are different CORS origins even though
    # they resolve to the same machine -- allow both plus the port Next.js
    # falls back to (3001) when 3000 is briefly occupied, so local dev never
    # breaks on this.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    # Optimizer
    SOLVER_TIME_LIMIT_SECONDS: float = 12.0
    TOP_K_CANDIDATES: int = 20

    # Demo
    RANDOM_SEED: int = 42


@lru_cache
def get_settings() -> Settings:
    return Settings()
