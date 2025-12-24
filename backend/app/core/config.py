from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyUrl, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", case_sensitive=False)

    environment: str = Field("local", description="Deployment environment name")
    debug: bool = Field(False, description="Enable debug and reload features")
    secret_key: str = Field("changeme", description="Application secret key")

    api_prefix: str = Field("/api", description="Prefix applied to all API routes")
    project_name: str = Field("Smart Comp API", description="OpenAPI title")
    project_version: str = Field("0.1.0", description="Semantic version")

    redis_url: AnyUrl | str = Field(
        "redis://redis:6379/0",
        description="Redis connection string for Celery broker and result backend",
    )
    result_backend: AnyUrl | str = Field(
        "redis://redis:6379/1",
        description="Celery result backend connection string",
    )
    task_queue: str = Field("smart-comp", description="Default Celery task queue")

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description="Allowed CORS origins",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:  # noqa: N805
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @computed_field
    @property
    def cors_allow_origin_regex(self) -> str:
        return "|".join(self.cors_origins)

    storage_root: Path = Field(
        Path("/tmp/smartcomp"),
        description="Base directory for per-job working data",
    )
    job_ttl_hours: int = Field(
        24,
        ge=0,
        description="Retention window in hours for completed job artifacts; 0 deletes immediately",
    )
    smart_comp_config_path: Path | None = Field(
        None,
        description="Optional override path to Smart-Comp config file (config.txt)",
    )
    max_upload_mb: int = Field(
        100,
        gt=0,
        description="Maximum allowed upload size per file in megabytes",
    )

    job_timeout_seconds: int = Field(
        1800,
        gt=0,
        description="Wall-clock timeout enforced for long-running jobs.",
    )
    max_concurrent_jobs: int = Field(
        2,
        ge=1,
        description=(
            "Maximum number of worker tasks allowed to run concurrently across the cluster.",
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
