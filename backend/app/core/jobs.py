from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from redis import Redis

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class JobProgress:
    percent: float = 0.0
    step: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "JobProgress":
        if not data:
            return cls()
        return cls(
            percent=float(data.get("percent", 0.0)),
            step=data.get("step"),
            message=data.get("message"),
        )


@dataclass
class JobRecord:
    job_id: str
    job_type: str
    status: JobStatus
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    task_id: str | None = None
    progress: JobProgress = field(default_factory=JobProgress)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "jobId": self.job_id,
            "jobType": self.job_type,
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "taskId": self.task_id,
            "progress": self.progress.to_dict(),
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=data["jobId"],
            job_type=data["jobType"],
            status=JobStatus(data["status"]),
            created_at=_parse_datetime(data.get("createdAt")),
            started_at=_parse_datetime(data.get("startedAt")),
            finished_at=_parse_datetime(data.get("finishedAt")),
            task_id=data.get("taskId"),
            progress=JobProgress.from_dict(data.get("progress")),
            error=data.get("error"),
        )

    @classmethod
    def from_json(cls, value: str | bytes | None) -> "JobRecord | None":
        if not value:
            return None
        return cls.from_dict(json.loads(value))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class JobRepository:
    """Redis-backed persistence for job metadata and cancellation flags."""

    def __init__(self, redis_client: Redis, *, namespace: str = "job") -> None:
        self.redis = redis_client
        self.namespace = namespace

    def _job_key(self, job_id: str) -> str:
        return f"{self.namespace}:{job_id}"

    def _cancel_key(self, job_id: str) -> str:
        return f"{self.namespace}:{job_id}:cancel"

    def save(self, record: JobRecord) -> JobRecord:
        self.redis.set(self._job_key(record.job_id), record.to_json())
        logger.debug("Persisted job %s state %s", record.job_id, record.status)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        value = self.redis.get(self._job_key(job_id))
        return JobRecord.from_json(value)

    def mark_cancel_flag(self, job_id: str) -> None:
        self.redis.set(self._cancel_key(job_id), "1")
        logger.info("Cancellation requested for job %s", job_id)

    def clear_cancel_flag(self, job_id: str) -> None:
        self.redis.delete(self._cancel_key(job_id))

    def is_cancel_requested(self, job_id: str) -> bool:
        flag = self.redis.get(self._cancel_key(job_id))
        return bool(int(flag)) if flag is not None else False

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        error: str | None = None,
    ) -> JobRecord:
        record = self.get(job_id)
        if not record:
            raise KeyError(f"Job {job_id} not found")

        record.status = status
        record.started_at = started_at if started_at is not None else record.started_at
        record.finished_at = finished_at if finished_at is not None else record.finished_at
        record.error = error
        return self.save(record)

    def update_progress(
        self,
        job_id: str,
        *,
        percent: float | None = None,
        step: str | None = None,
        message: str | None = None,
    ) -> JobRecord:
        record = self.get(job_id)
        if not record:
            raise KeyError(f"Job {job_id} not found")

        if percent is not None:
            record.progress.percent = float(percent)
        if step is not None:
            record.progress.step = step
        if message is not None:
            record.progress.message = message

        return self.save(record)

    def update_task_id(self, job_id: str, task_id: str) -> JobRecord:
        record = self.get(job_id)
        if not record:
            raise KeyError(f"Job {job_id} not found")
        record.task_id = task_id
        return self.save(record)


class JobSemaphore:
    """Redis-backed counter used to limit concurrent job execution."""

    def __init__(self, redis_client: Redis, *, key: str = "job:semaphore") -> None:
        self.redis = redis_client
        self.key = key

    def acquire(self, limit: int, *, ttl_seconds: int) -> bool:
        script = """
        local current = tonumber(redis.call('get', KEYS[1]) or '0')
        local limit = tonumber(ARGV[1])
        local ttl = tonumber(ARGV[2])
        if current >= limit then
            return 0
        end
        local updated = redis.call('incr', KEYS[1])
        if ttl > 0 then
            redis.call('expire', KEYS[1], ttl)
        end
        return updated
        """
        result = self.redis.eval(script, 1, self.key, limit, ttl_seconds)
        return bool(result)

    def release(self) -> None:
        script = """
        local current = tonumber(redis.call('get', KEYS[1]) or '0')
        if current <= 0 then
            redis.call('del', KEYS[1])
            return 0
        end
        local updated = redis.call('decr', KEYS[1])
        if updated <= 0 then
            redis.call('del', KEYS[1])
        end
        return updated
        """
        self.redis.eval(script, 1, self.key)
