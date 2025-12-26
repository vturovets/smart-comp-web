from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.observability import PROMETHEUS_AVAILABLE
from tests.conftest import StubRedis, build_test_client


def test_request_and_trace_ids_propagate(api_client) -> None:
    headers = {"X-Request-ID": "req-123", "X-Trace-ID": "trace-abc"}
    response = api_client.get("/api/health", headers=headers)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == headers["X-Request-ID"]
    assert response.headers["X-Trace-ID"] == headers["X-Trace-ID"]


def test_error_response_contains_request_id(api_client) -> None:
    headers = {"X-Request-ID": "req-error"}
    response = api_client.post("/api/jobs", data={}, headers=headers)

    assert response.status_code == 422
    payload = response.json()
    assert payload["requestId"] == headers["X-Request-ID"]
    assert payload["error"]["code"] == "REQUEST_VALIDATION_ERROR"


def test_metrics_endpoint_exposes_counters(api_client) -> None:
    if not PROMETHEUS_AVAILABLE:
        pytest.skip("Prometheus client not installed")
    api_client.get("/")
    metrics_response = api_client.get("/metrics")

    assert metrics_response.status_code == 200
    body = metrics_response.content
    assert b"http_requests_total" in body
    assert b'path="/"' in body


def test_upload_limit_enforced(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    config_file = tmp_path / "config.txt"
    config_file.write_text("[test]\nalpha=0.05\n", encoding="utf-8")

    env = {
        "APP_ENVIRONMENT": "test",
        "APP_STORAGE_ROOT": str(storage_root),
        "APP_MAX_UPLOAD_MB": "1",
        "APP_SMART_COMP_CONFIG_PATH": str(config_file),
    }
    client = build_test_client(monkeypatch, StubRedis(), env_overrides=env)

    large_bytes = b"a" * (2 * 1024 * 1024)
    response = client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps({"bootstrapIterations": 1})},
        files={"file1": ("large.csv", large_bytes, "text/csv")},
    )

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert "exceeds configured limit" in payload["error"]["message"]


def test_job_timeout_returns_failed_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    config_file = tmp_path / "config.txt"
    config_file.write_text("[test]\nalpha=0.05\n", encoding="utf-8")

    env = {
        "APP_ENVIRONMENT": "test",
        "APP_STORAGE_ROOT": str(storage_root),
        "APP_JOB_TIMEOUT_SECONDS": "1",
        "APP_SMART_COMP_CONFIG_PATH": str(config_file),
    }
    client = build_test_client(monkeypatch, StubRedis(), env_overrides=env)

    from app.worker.runner import JobRunner, JobTimeoutError

    def immediate_timeout(self, job_id, deadline):
        raise JobTimeoutError(f"Job {job_id} exceeded timeout of {self.settings.job_timeout_seconds}s")

    monkeypatch.setattr(JobRunner, "_guard", immediate_timeout)

    creation = client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps({"bootstrapIterations": 1})},
        files={"file1": ("dataset.csv", b"value\n1", "text/csv")},
    )
    job_id = creation.json()["jobId"]

    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "FAILED"
    assert "timeout" in (body["error"] or "").lower()

    assert not storage_root.joinpath(job_id).exists()
