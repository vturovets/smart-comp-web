from __future__ import annotations

from fastapi import Depends
from redis import Redis

from app.core.config import Settings, get_settings
from app.core.job_service import JobService
from app.core.jobs import JobRepository
from app.worker.tasks import get_redis_client


def get_settings_dep() -> Settings:
    return get_settings()


def get_redis_client_dep() -> Redis:
    return get_redis_client()


def get_job_repository(redis_client: Redis = Depends(get_redis_client_dep)) -> JobRepository:
    return JobRepository(redis_client)


def get_job_service(
    repository: JobRepository = Depends(get_job_repository),
    settings: Settings = Depends(get_settings_dep),
) -> JobService:
    return JobService(repository, settings=settings)
