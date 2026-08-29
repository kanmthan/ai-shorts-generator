"""Application configuration.

All settings are loaded from environment variables (or a local ``.env`` file in
development). Every value has a sensible development default so the app can boot
locally without a fully-populated environment; production overrides everything.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- App ----
    APP_NAME: str = "AI Shorts Generator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ---- Database ----
    DATABASE_URL: str = (
        "postgresql://user:password@localhost:5432/ai_shorts_generator"
    )

    # ---- Auth ----
    SECRET_KEY: str = "dev-secret-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # ---- Claude / Anthropic ----
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"

    # ---- Stock B-roll ----
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""

    # ---- Async / Celery ----
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ---- Media / pipeline ----
    FFMPEG_BINARY: str = "ffmpeg"
    YTDLP_BINARY: str = "yt-dlp"
    MEDIA_ROOT: str = "./media"
    MAX_VIDEO_DURATION_SECONDS: int = 14400
    MAX_OUTPUT_FILE_MB: int = 200
    SHORT_MIN_SECONDS: int = 30
    SHORT_MAX_SECONDS: int = 60

    # ---- Storage (prod, S3-compatible) ----
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""

    # ---- Frontend / CORS ----
    VITE_API_URL: str = "http://localhost:8000"
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Allow CORS_ORIGINS to be provided as a comma-separated string."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                # Leave JSON-style lists for pydantic to parse.
                return value
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def s3_enabled(self) -> bool:
        """True when enough S3 config is present to use object storage."""
        return bool(self.S3_BUCKET and self.S3_ACCESS_KEY_ID and self.S3_SECRET_ACCESS_KEY)


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` singleton."""
    return Settings()


settings: Settings = get_settings()
