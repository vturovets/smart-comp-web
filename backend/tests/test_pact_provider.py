from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import requests

import pytest

from app.core.config import get_settings


CONTRACT_PATH = Path(__file__).parent / "contracts" / "provider_pact.json"


def _matching_rule_paths(interaction: dict[str, Any]) -> set[tuple[str, ...]]:
    rules = interaction.get("response", {}).get("matchingRules", {}).get("body", {})
    paths: set[tuple[str, ...]] = set()
    for raw_path in rules:
        if not raw_path.startswith("$."):
            continue
        trimmed = raw_path[2:]
        segments: list[str] = []
        for part in trimmed.split("."):
            if not part:
                continue
            segments.append(part.split("[")[0])
        paths.add(tuple(segments))
    return paths


def _load_contract() -> tuple[dict[str, Any], str]:
    broker = os.getenv("PACT_BROKER_BASE_URL")
    consumer = os.getenv("PACT_CONSUMER_NAME", "smart-comp-web")
    provider = os.getenv("PACT_PROVIDER_NAME", "smart-comp-api")
    tag = os.getenv("PACT_CONSUMER_TAG", "main")

    if not broker:
        return json.loads(CONTRACT_PATH.read_text()), str(CONTRACT_PATH)

    url = f"{broker.rstrip('/')}/pacts/provider/{provider}/consumer/{consumer}/latest/{tag}"
    headers = {"Accept": "application/json"}
    token = os.getenv("PACT_BROKER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json(), url


def _replace_ids(value: Any, *, job_id: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _replace_ids(val, job_id=job_id) for key, val in value.items()}
    if isinstance(value, list):
        return [_replace_ids(item, job_id=job_id) for item in value]
    if isinstance(value, str) and job_id:
        return value.replace("pact-job-1", job_id)
    return value


def _apply_state(states: Iterable[str], client, kw_zip_bytes: bytes) -> dict[str, Any]:
    state_values: dict[str, Any] = {}
    for state in states:
        state_values |= _handle_state(state, client, kw_zip_bytes, state_values)
    return state_values


def _handle_state(
    state: str,
    client,
    kw_zip_bytes: bytes,
    current: dict[str, Any],
) -> dict[str, Any]:
    if state == "ready to accept job creation":
        return {"nextJobId": "pact-job-1"}

    if state in {
        "job is complete",
        "results ready",
        "artifacts ready",
        "plot artifact available",
    }:
        if "jobId" in current:
            return {}
        return _seed_completed_job(client)

    if state == "completed KW job":
        response = client.post(
            "/api/jobs",
            data={"jobType": "KW_PERMUTATION", "config": json.dumps({"permutationCount": 2})},
            files={"kwBundle": ("bundle.zip", kw_zip_bytes, "application/zip")},
        )
        response.raise_for_status()
        return {"jobId": response.json()["jobId"]}

    return {}


def _seed_completed_job(client) -> dict[str, Any]:
    from datetime import datetime, timezone

    from app.core.jobs import JobRecord, JobRepository, JobStatus
    from app.core.storage import prepare_job_paths
    from app.worker import tasks as worker_tasks

    job_id = "pact-job-1"
    now = datetime.now(timezone.utc)
    repo = JobRepository(worker_tasks.get_redis_client())
    record = JobRecord(
        job_id=job_id,
        job_type="BOOTSTRAP_SINGLE",
        status=JobStatus.QUEUED,
        created_at=now,
    )
    repo.save(record)

    job_paths = prepare_job_paths(job_id, get_settings().storage_root)
    results = {
        "jobId": job_id,
        "jobType": "BOOTSTRAP_SINGLE",
        "decision": {"alpha": 0.05, "pValue": 0.03, "significant": True},
        "descriptive": {"mean": 1.5},
        "metrics": {"delta": 1.2},
        "plots": [{"artifactName": "plot.json", "kind": "histogram"}],
    }
    job_paths.output_dir.mkdir(parents=True, exist_ok=True)
    (job_paths.output_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")
    plot_content = {"data": [{"type": "bar", "x": [1, 2], "y": [3, 4]}]}
    (job_paths.output_dir / "plot.json").write_text(json.dumps(plot_content), encoding="utf-8")

    repo.update_status(job_id, JobStatus.COMPLETED, started_at=now, finished_at=now)
    repo.update_progress(job_id, percent=100, step="completed", message=None)
    repo.update_task_id(job_id, "pact-task")
    client.get(f"/api/jobs/{job_id}")
    return {"jobId": job_id}


def _assert_body_subset(
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    skip_paths: set[tuple[str, ...]] | None = None,
    prefix: tuple[str, ...] = (),
) -> None:
    for key, value in expected.items():
        path = prefix + (key,)
        if skip_paths and path in skip_paths:
            continue
        assert key in actual
        if isinstance(value, dict):
            assert isinstance(actual[key], dict)
            _assert_body_subset(
                value,
                actual[key],
                skip_paths=skip_paths,
                prefix=path,
            )
        else:
            assert actual[key] == value


def _interaction_states(interaction: dict[str, Any]) -> list[str]:
    explicit = [
        state.get("name")
        for state in interaction.get("providerStates", [])
        if state.get("name")
    ]
    legacy = interaction.get("providerState")
    if legacy:
        return explicit + [legacy]
    return explicit


@pytest.mark.parametrize("interaction", _load_contract()[0]["interactions"])
def test_provider_contracts(
    api_client,
    kw_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
    interaction: dict[str, Any],
) -> None:
    states = _interaction_states(interaction)
    state_values = _apply_state(states, api_client, kw_zip_bytes)
    if next_job := state_values.get("nextJobId"):
        monkeypatch.setattr("app.core.job_service.uuid.uuid4", lambda: next_job)
    request = interaction["request"]
    response = interaction["response"]

    path = request["path"]
    if "jobId" in state_values:
        path = path.replace("pact-job-1", state_values["jobId"])
    path = path.replace("{{jobId}}", state_values.get("jobId", ""))

    request_kwargs: dict[str, Any] = {}
    if request["method"] == "POST" and path.endswith("/api/jobs"):
        request_kwargs = {
            "data": {
                "jobType": "BOOTSTRAP_SINGLE",
                "config": json.dumps({"alpha": 0.05}),
            },
            "files": {"file1": ("file1.csv", b"value\n1\n2", "text/csv")},
        }

    result = api_client.request(request["method"], path, **request_kwargs)
    assert result.status_code == response["status"], interaction["description"]
    if "body" in response:
        expected_body = _replace_ids(response["body"], job_id=state_values.get("jobId"))
        skip_paths = _matching_rule_paths(interaction)
        _assert_body_subset(expected_body, result.json(), skip_paths=skip_paths)
