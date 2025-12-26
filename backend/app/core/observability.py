from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
except ImportError:  # pragma: no cover - fallback for optional dependency
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

    class _NoopMetric:
        def labels(self, **_: Any) -> "_NoopMetric":
            return self

        def inc(self, *_: Any, **__: Any) -> None:
            return None

        def observe(self, *_: Any, **__: Any) -> None:
            return None

    def generate_latest(_: object | None = None) -> bytes:
        return b""

    class _NoopRegistry:  # pragma: no cover - minimal placeholder
        pass

    REGISTRY = _NoopRegistry()
    Counter = Histogram = _NoopMetric  # type: ignore[assignment]

PROMETHEUS_AVAILABLE = not isinstance(REGISTRY, type)

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)
job_id_ctx: ContextVar[str | None] = ContextVar("job_id", default=None)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ("method", "path", "status"),
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path", "status"),
)
jobs_started_total = Counter(
    "smartcomp_jobs_started_total",
    "Jobs accepted for execution",
    ("job_type",),
)
jobs_completed_total = Counter(
    "smartcomp_jobs_completed_total",
    "Jobs finished with a terminal status",
    ("job_type", "status"),
)
job_runtime_seconds = Histogram(
    "smartcomp_job_runtime_seconds",
    "Wall-clock duration of job execution",
    ("job_type", "status"),
)


def bind_request_context(request_id: str, trace_id: str | None = None) -> None:
    request_id_ctx.set(request_id)
    trace_id_ctx.set(trace_id or request_id)


def bind_job_context(job_id: str) -> None:
    job_id_ctx.set(job_id)


def get_request_id(default: str | None = None) -> str | None:
    return request_id_ctx.get(default)


def get_trace_id(default: str | None = None) -> str | None:
    return trace_id_ctx.get(default)


def get_job_id(default: str | None = None) -> str | None:
    return job_id_ctx.get(default)


def record_request_metrics(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    labels = {"method": method, "path": path, "status": str(status_code)}
    http_requests_total.labels(**labels).inc()
    http_request_duration_seconds.labels(**labels).observe(duration_seconds)


def record_job_started(job_type: str) -> None:
    jobs_started_total.labels(job_type=job_type).inc()


def record_job_completion(job_type: str, status: str, duration_seconds: float) -> None:
    labels = {"job_type": job_type, "status": status}
    jobs_completed_total.labels(**labels).inc()
    job_runtime_seconds.labels(**labels).observe(duration_seconds)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - part of logging contract
        record.request_id = get_request_id()
        record.trace_id = get_trace_id()
        record.job_id = get_job_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - part of logging contract
        base: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "requestId": getattr(record, "request_id", None),
            "traceId": getattr(record, "trace_id", None),
            "jobId": getattr(record, "job_id", None),
        }
        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        return json.dumps({k: v for k, v in base.items() if v is not None})


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(isinstance(handler, logging.StreamHandler) and isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())
    root.setLevel(level)
    root.addHandler(handler)


@contextmanager
def job_logging(job_id: str, log_path: Path):
    bind_job_context(job_id)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())
    logger = logging.getLogger()
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)
