from __future__ import annotations

import json


def test_cancel_completed_job_rejected(api_client, kw_csv_files: list[tuple[str, bytes, str]]) -> None:
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "KW_PERMUTATION", "config": json.dumps({"permutationCount": 1})},
        files=[("files", entry) for entry in kw_csv_files],
    )
    job_id = creation.json()["jobId"]

    cancel_response = api_client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 409
    assert cancel_response.json()["error"]["code"] == "INVALID_STATE"


def test_artifact_list_contains_logs(api_client, kw_csv_files: list[tuple[str, bytes, str]]) -> None:
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps({"bootstrapIterations": 1})},
        files=[("files", ("dataset.csv", b"value\n1", "text/csv"))],
    )
    job_id = creation.json()["jobId"]

    artifacts_response = api_client.get(f"/api/jobs/{job_id}/artifacts")
    names = [artifact["name"] for artifact in artifacts_response.json()["artifacts"]]
    assert "results.json" in names
    assert "tool.log" in names
