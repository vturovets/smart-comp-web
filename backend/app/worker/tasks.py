from __future__ import annotations

import uuid
from typing import Any

from redis import Redis

from app.core.config import get_settings
from app.core.jobs import JobRecord, JobRepository, JobSemaphore, JobStatus
from app.core.storage import prepare_job_paths
from app.worker.celery_app import celery_app
from app.worker.runner import JobRunner

_cached_redis: Redis | None = None


def get_redis_client() -> Redis:
    settings = get_settings()
    global _cached_redis
    if settings.environment == "test":
        if _cached_redis is None:
            try:
                import fakeredis

                _cached_redis = fakeredis.FakeRedis(decode_responses=True)
            except Exception:  # pragma: no cover - fallback to real Redis if fakeredis missing
                _cached_redis = None
        if _cached_redis is not None:
            return _cached_redis
    return Redis.from_url(str(settings.redis_url), decode_responses=True)


def enqueue_job(job_type: str, payload: dict[str, Any] | None = None, *, job_id: str | None = None) -> JobRecord:
    """Create a job record and submit to Celery."""
    settings = get_settings()
    redis_client = get_redis_client()
    repository = JobRepository(redis_client)

    job_id = job_id or str(uuid.uuid4())
    record = JobRecord(job_id=job_id, job_type=job_type, status=JobStatus.QUEUED)
    repository.save(record)

    async_result = run_job.delay(job_id=job_id, job_type=job_type, payload=payload or {})
    repository.update_task_id(job_id, async_result.id)
    return repository.get(job_id) or record


@celery_app.task(bind=True, name="app.worker.tasks.run_job")
def run_job(self, job_id: str, job_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute Smart-Comp job lifecycle with cancellation and timeout guards."""
    settings = get_settings()
    redis_client = get_redis_client()
    repository = JobRepository(redis_client)
    semaphore = JobSemaphore(redis_client)
    job_paths = prepare_job_paths(job_id, settings.storage_root)
    runner = JobRunner(repository, semaphore, settings=settings)

    def attach_task(record: JobRecord) -> JobRecord:
        return repository.update_task_id(record.job_id, self.request.id)

    result = runner.execute(
        job_id=job_id,
        job_type=job_type,
        job_paths=job_paths,
        payload=payload or {},
        set_task_id=attach_task,
    )
    return result.to_dict()
