from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.core.config import get_settings
from app.core.jobs import JobRecord, JobRepository, JobSemaphore, JobStatus
from app.core.storage import prepare_job_paths
from app.worker import tasks as worker_tasks
from app.worker.celery_app import celery_app
from app.worker.runner import JobRunner


class _MemoryRedis:
    """Minimal Redis stub to avoid external test dependency."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._store[key] = str(value)

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    def eval(self, script: str, numkeys: int, *args):
        # Only supports the simple increment/decrement scripts used by JobSemaphore.
        if numkeys != 1:
            raise ValueError("Expected a single key for semaphore scripts")
        key = args[0]
        if "incr" in script:
            limit = int(args[1])
            current = int(self._store.get(key, "0"))
            if current >= limit:
                return 0
            current += 1
            self._store[key] = str(current)
            return current

        current = int(self._store.get(key, "0"))
        if current <= 0:
            self._store.pop(key, None)
            return 0
        current -= 1
        if current <= 0:
            self._store.pop(key, None)
            return current
        self._store[key] = str(current)
        return current


def configure_settings(monkeypatch: pytest.MonkeyPatch, tmp_path, *, timeout_seconds: int = 1):
    monkeypatch.setenv("APP_ENVIRONMENT", "test")
    monkeypatch.setenv("APP_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_JOB_TIMEOUT_SECONDS", str(timeout_seconds))
    get_settings.cache_clear()
    return get_settings()


def test_runner_cancels_and_cleans(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    settings = configure_settings(monkeypatch, tmp_path, timeout_seconds=5)
    redis_client = _MemoryRedis()
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
    redis_client = _MemoryRedis()
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
    fake_redis = _MemoryRedis()
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
