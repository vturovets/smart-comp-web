from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.core.config import Settings, get_settings
from app.core.jobs import JobRecord, JobRepository, JobSemaphore, JobStatus
from app.core.observability import bind_job_context, configure_logging, job_logging, record_job_completion
from app.core.storage import JobPaths, cleanup_after_completion, cleanup_job
from app.worker.smart_comp_executor import SmartCompExecutor

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
        configure_logging(logging.DEBUG if self.settings.debug else logging.INFO)

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
        bind_job_context(job_id)
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
            finished_at = _utcnow()
            finished = self.repository.update_status(
                job_id,
                JobStatus.FAILED,
                error="Concurrency limit reached",
                finished_at=finished_at,
            )
            record_job_completion(job_type, JobStatus.FAILED.value, 0.0)
            cleanup_job(job_paths)
            return finished

        started_at = _utcnow()
        self.repository.update_status(job_id, JobStatus.RUNNING, started_at=started_at)
        deadline = started_at + timedelta(seconds=self.settings.job_timeout_seconds)

        try:
            self._run_job(job_id, job_type, job_paths, payload, deadline)
            finished_at = _utcnow()
            finished = self.repository.update_status(
                job_id,
                JobStatus.COMPLETED,
                finished_at=finished_at,
            )
            self.repository.update_progress(job_id, percent=100.0, step="completed", message=None)
            record_job_completion(job_type, JobStatus.COMPLETED.value, (finished_at - started_at).total_seconds())
            cleanup_after_completion(job_paths, payload.get("cleanAll", False))
            return finished
        except JobCancelledError:
            finished_at = _utcnow()
            finished = self.repository.update_status(
                job_id,
                JobStatus.CANCELLED,
                finished_at=finished_at,
                error="Cancelled",
            )
            record_job_completion(job_type, JobStatus.CANCELLED.value, (finished_at - started_at).total_seconds())
            cleanup_job(job_paths)
            return finished
        except JobTimeoutError as exc:
            finished_at = _utcnow()
            finished = self.repository.update_status(
                job_id,
                JobStatus.FAILED,
                finished_at=finished_at,
                error=str(exc),
            )
            record_job_completion(job_type, JobStatus.FAILED.value, (finished_at - started_at).total_seconds())
            cleanup_job(job_paths)
            return finished
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.exception("Unhandled error during job %s", job_id)
            finished_at = _utcnow()
            finished = self.repository.update_status(
                job_id,
                JobStatus.FAILED,
                finished_at=finished_at,
                error=str(exc),
            )
            record_job_completion(job_type, JobStatus.FAILED.value, (finished_at - started_at).total_seconds())
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
        """Run Smart-Comp execution and enforce cancellation/timeout checks."""
        bind_job_context(job_id)
        self.repository.update_progress(job_id, percent=2, step="prepare", message="Preparing Smart-Comp inputs")
        with job_logging(job_id, job_paths.log_file):
            executor = SmartCompExecutor(
                job_id,
                job_type,
                job_paths,
                payload,
                progress_cb=lambda percent, step, message=None: self.repository.update_progress(
                    job_id,
                    percent=percent,
                    step=step,
                    message=message,
                ),
                guard_cb=lambda: self._guard(job_id, deadline),
            )
            executor.run()
        self.repository.update_progress(job_id, percent=90, step="finalize", message="Finalizing outputs")
        self._guard(job_id, deadline)

    def _guard(self, job_id: str, deadline: datetime) -> None:
        if self.repository.is_cancel_requested(job_id):
            raise JobCancelledError(f"Job {job_id} cancelled")

        now = _utcnow()
        if now > deadline:
            raise JobTimeoutError(f"Job {job_id} exceeded timeout of {self.settings.job_timeout_seconds}s")


def _utcnow() -> datetime:
    now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now
