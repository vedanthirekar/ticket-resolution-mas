from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from LUMA_-prefixed environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LUMA_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: str = Field(default="postgresql+psycopg://luma:luma_dev_only@localhost:5432/luma")
    database_echo: bool = False
    operations_username: str = "operations"
    operations_password: str = "change-me-before-production"
    operations_display_name: str = "Luma Operations"
    session_ttl_hours: int = Field(default=8, ge=1, le=168)
    worker_lease_seconds: int = Field(default=120, ge=10, le=3600)
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=60)
    model_provider: Literal["anthropic", "google_genai", "openrouter"] = "anthropic"
    model_name: str = "claude-sonnet-4-6"
    model_api_key: str | None = Field(default=None, repr=False)
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias="ANTHROPIC_API_KEY",
        repr=False,
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model_timeout_seconds: float = Field(default=30, gt=0, le=120)
    model_stage_timeout_seconds: float = Field(default=180, gt=0, le=600)
    model_max_retries: int = Field(default=2, ge=0, le=5)
    model_structured_output_max_attempts: int = Field(default=3, ge=1, le=6)
    model_max_output_tokens: int = Field(default=2000, ge=128, le=16000)
    model_input_cost_per_million_usd: float | None = Field(default=None, ge=0)
    model_output_cost_per_million_usd: float | None = Field(default=None, ge=0)
    agent_max_tool_calls: int = Field(default=8, ge=1, le=20)
    agent_max_supplemental_calls: int = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def require_free_openrouter_model(self) -> Self:
        if self.model_provider == "openrouter" and not self.model_name.endswith(":free"):
            raise ValueError("OpenRouter model names must end in ':free' for this project")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
