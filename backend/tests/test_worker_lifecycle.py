from __future__ import annotations

from datetime import datetime, timedelta, timezone

import fakeredis
import pytest

from app.core.config import get_settings
from app.core.jobs import JobRecord, JobRepository, JobSemaphore, JobStatus
from app.core.storage import prepare_job_paths
from app.worker import tasks as worker_tasks
from app.worker.celery_app import celery_app
from app.worker.runner import JobRunner


def configure_settings(monkeypatch: pytest.MonkeyPatch, tmp_path, *, timeout_seconds: int = 1):
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("APP_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_JOB_TIMEOUT_SECONDS", str(timeout_seconds))
    get_settings.cache_clear()
    return get_settings()


def test_runner_cancels_and_cleans(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    settings = configure_settings(monkeypatch, tmp_path, timeout_seconds=5)
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    repository = JobRepository(redis_client)
    semaphore = JobSemaphore(redis_client)
    job_id = "cancelled-job"
    job_paths = prepare_job_paths(job_id, settings.storage_root)
    repository.save(JobRecord(job_id=job_id, job_type="BOOTSTRAP_SINGLE", status=JobStatus.QUEUED))
    repository.mark_cancel_flag(job_id)

    runner = JobRunner(repository, semaphore, settings=settings)
    result = runner.execute(
        job_id=job_id,
        job_type="BOOTSTRAP_SINGLE",
        job_paths=job_paths,
        payload={"bootstrapIterations": 4},
    )

    assert result.status == JobStatus.CANCELLED
    assert result.error == "Cancelled"
    assert not job_paths.root.exists()


def test_runner_times_out(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    settings = configure_settings(monkeypatch, tmp_path, timeout_seconds=1)
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    repository = JobRepository(redis_client)
    semaphore = JobSemaphore(redis_client)
    job_id = "timeout-job"
    job_paths = prepare_job_paths(job_id, settings.storage_root)
    repository.save(JobRecord(job_id=job_id, job_type="BOOTSTRAP_SINGLE", status=JobStatus.QUEUED))

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ticks = iter(
        [
            base,  # started_at
            base + timedelta(seconds=0.1),  # guard after prepare
            base + timedelta(seconds=0.3),  # loop 1
            base + timedelta(seconds=2),  # loop 2 triggers timeout
            base + timedelta(seconds=2),  # finish timestamps
        ],
    )

    def fake_now() -> datetime:
        try:
            return next(ticks)
        except StopIteration:
            return base + timedelta(seconds=2)

    monkeypatch.setattr("app.worker.runner._utcnow", fake_now)

    runner = JobRunner(repository, semaphore, settings=settings)
    result = runner.execute(
        job_id=job_id,
        job_type="BOOTSTRAP_SINGLE",
        job_paths=job_paths,
        payload={"bootstrapIterations": 3},
    )

    assert result.status == JobStatus.FAILED
    assert "timeout" in (result.error or "").lower()
    assert not job_paths.root.exists()


def test_enqueue_run_and_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    settings = configure_settings(monkeypatch, tmp_path, timeout_seconds=5)
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(worker_tasks, "get_redis_client", lambda: fake_redis)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    record = worker_tasks.enqueue_job(
        "KW_PERMUTATION",
        {"permutationCount": 3, "cleanAll": True},
    )
    refreshed = JobRepository(fake_redis).get(record.job_id)
    assert refreshed is not None
    assert refreshed.status == JobStatus.COMPLETED
    assert refreshed.progress.percent == pytest.approx(100.0)
    assert refreshed.progress.step == "completed"

    results_path = settings.storage_root / record.job_id / "output" / "results.json"
    cleaned_path = settings.storage_root / record.job_id / "output" / "dataset_cleaned.csv"
    assert results_path.exists()
    assert not cleaned_path.exists()
