from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.core.jobs import JobRecord, JobRepository, JobSemaphore, JobStatus
from app.core.storage import JobPaths, cleanup_after_completion, cleanup_job

logger = logging.getLogger(__name__)


class JobExecutionError(RuntimeError):
    """Base error for job lifecycle failures."""


class JobCancelledError(JobExecutionError):
    """Raised when a cancellation flag is detected."""


class JobTimeoutError(JobExecutionError):
    """Raised when wall-clock timeout is exceeded."""


class JobRunner:
    """Coordinates lifecycle, progress and cleanup for Smart-Comp jobs."""

    def __init__(
        self,
        repository: JobRepository,
        semaphore: JobSemaphore,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.semaphore = semaphore
        self.settings = settings or get_settings()

    def execute(
        self,
        job_id: str,
        job_type: str,
        job_paths: JobPaths,
        payload: dict[str, Any],
        *,
        set_task_id: Callable[[JobRecord], None] | None = None,
    ) -> JobRecord:
        record = self.repository.get(job_id) or JobRecord(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
        )
        if set_task_id:
            record = set_task_id(record) or record
        record = self.repository.save(record)

        if set_task_id and record.task_id:
            set_task_id(record)

        acquired = self.semaphore.acquire(
            self.settings.max_concurrent_jobs,
            ttl_seconds=self.settings.job_timeout_seconds,
        )
        if not acquired:
            logger.warning("Concurrency limit reached, rejecting job %s", job_id)
            finished = self.repository.update_status(
                job_id,
                JobStatus.FAILED,
                error="Concurrency limit reached",
                finished_at=_utcnow(),
            )
            cleanup_job(job_paths)
            return finished

        started_at = _utcnow()
        self.repository.update_status(job_id, JobStatus.RUNNING, started_at=started_at)
        deadline = started_at + timedelta(seconds=self.settings.job_timeout_seconds)

        try:
            self._run_job(job_id, job_type, job_paths, payload, deadline)
            finished = self.repository.update_status(
                job_id,
                JobStatus.COMPLETED,
                finished_at=_utcnow(),
            )
            self.repository.update_progress(job_id, percent=100.0, step="completed", message=None)
            cleanup_after_completion(job_paths, payload.get("cleanAll", False))
            return finished
        except JobCancelledError:
            finished = self.repository.update_status(
                job_id,
                JobStatus.CANCELLED,
                finished_at=_utcnow(),
                error="Cancelled",
            )
            cleanup_job(job_paths)
            return finished
        except JobTimeoutError as exc:
            finished = self.repository.update_status(
                job_id,
                JobStatus.FAILED,
                finished_at=_utcnow(),
                error=str(exc),
            )
            cleanup_job(job_paths)
            return finished
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.exception("Unhandled error during job %s", job_id)
            finished = self.repository.update_status(
                job_id,
                JobStatus.FAILED,
                finished_at=_utcnow(),
                error=str(exc),
            )
            cleanup_job(job_paths)
            return finished
        finally:
            self.repository.clear_cancel_flag(job_id)
            self.semaphore.release()

    def _run_job(
        self,
        job_id: str,
        job_type: str,
        job_paths: JobPaths,
        payload: dict[str, Any],
        deadline: datetime,
    ) -> None:
        """Run bootstrap/permutation loops with periodic cancellation/timeout checks."""
        iterations_bootstrap = int(payload.get("bootstrapIterations", 5))
        iterations_permutation = int(payload.get("permutationCount", 5))

        writer = JobArtifactWriter(job_paths)

        self.repository.update_progress(job_id, percent=5, step="prepare", message="Preparing inputs")
        writer.write_placeholder("inputs.ready")
        self._guard(job_id, deadline)

        if "KW" in job_type.upper() or "PERMUT" in job_type.upper():
            self._permutation_loop(job_id, iterations_permutation, deadline)
        else:
            self._bootstrap_loop(job_id, iterations_bootstrap, deadline)

        writer.write_placeholder("dataset_cleaned.csv")
        writer.write_placeholder("results.json")
        self.repository.update_progress(job_id, percent=90, step="finalize", message="Finalizing outputs")
        self._guard(job_id, deadline)

    def _bootstrap_loop(self, job_id: str, iterations: int, deadline: datetime) -> None:
        for index in range(iterations):
            self._guard(job_id, deadline)
            percent = 5 + ((index + 1) / max(iterations, 1)) * 70
            self.repository.update_progress(
                job_id,
                percent=percent,
                step="bootstrap",
                message=f"Bootstrap iteration {index + 1}/{iterations}",
            )

    def _permutation_loop(self, job_id: str, iterations: int, deadline: datetime) -> None:
        for index in range(iterations):
            self._guard(job_id, deadline)
            percent = 5 + ((index + 1) / max(iterations, 1)) * 70
            self.repository.update_progress(
                job_id,
                percent=percent,
                step="permutation",
                message=f"Permutation {index + 1}/{iterations}",
            )

    def _guard(self, job_id: str, deadline: datetime) -> None:
        if self.repository.is_cancel_requested(job_id):
            raise JobCancelledError(f"Job {job_id} cancelled")

        now = _utcnow()
        if now > deadline:
            raise JobTimeoutError(f"Job {job_id} exceeded timeout of {self.settings.job_timeout_seconds}s")


class JobArtifactWriter:
    """Persists placeholder outputs to ensure cleanup paths exist."""

    def __init__(self, job_paths: JobPaths) -> None:
        self.job_paths = job_paths

    def write_placeholder(self, name: str) -> Path:
        target = self.job_paths.output_dir / name
        target.write_text("placeholder", encoding="utf-8")
        return target


def _utcnow() -> datetime:
    now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now
