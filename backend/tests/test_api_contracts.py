from __future__ import annotations

import json

import pytest


def test_config_defaults_contract(api_client) -> None:
    response = api_client.get("/api/config/defaults")
    assert response.status_code == 200
    body = response.json()
    assert "alpha" in body
    assert "plots" in body
    assert isinstance(body["plots"], dict)


def test_create_kw_job_and_fetch_results(api_client, kw_zip_bytes: bytes) -> None:
    response = api_client.post(
        "/api/jobs",
        data={"jobType": "KW_PERMUTATION", "config": json.dumps({"permutationCount": 2})},
        files={"kwBundle": ("bundle.zip", kw_zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    job_id = response.json()["jobId"]

    status_response = api_client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == "COMPLETED"
    assert status_body["jobType"] == "KW_PERMUTATION"

    results_response = api_client.get(f"/api/jobs/{job_id}/results")
    assert results_response.status_code == 200
    results_body = results_response.json()
    assert results_body["jobType"] == "KW_PERMUTATION"
    assert results_body["decision"]["alpha"] == pytest.approx(0.05)

    artifacts_response = api_client.get(f"/api/jobs/{job_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifact_names = [artifact["name"] for artifact in artifacts_response.json()["artifacts"]]
    assert "results.json" in artifact_names

    artifact_stream = api_client.get(f"/api/jobs/{job_id}/artifacts/results.json")
    assert artifact_stream.status_code == 200


def test_invalid_config_rejected(api_client) -> None:
    response = api_client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": '{"unknown":true}'},
        files={"file1": ("data.csv", b"value\n1", "text/csv")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CONFIG"


def test_openapi_includes_contract_schemas(api_client) -> None:
    schema = api_client.get("/openapi.json").json()
    assert "/api/config/defaults" in schema["paths"]
    assert "ConfigDefaultsResponse" in schema["components"]["schemas"]
