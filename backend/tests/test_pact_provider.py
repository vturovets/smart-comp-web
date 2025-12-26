from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


CONTRACT_PATH = Path(__file__).parent / "contracts" / "provider_pact.json"


def _apply_state(state: str | None, client, kw_zip_bytes: bytes) -> dict[str, Any]:
    if state == "completed KW job":
        response = client.post(
            "/api/jobs",
            data={"jobType": "KW_PERMUTATION", "config": json.dumps({"permutationCount": 2})},
            files={"kwBundle": ("bundle.zip", kw_zip_bytes, "application/zip")},
        )
        response.raise_for_status()
        return {"jobId": response.json()["jobId"]}
    return {}


def _assert_body_subset(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    for key, value in expected.items():
        assert key in actual
        if isinstance(value, dict):
            assert isinstance(actual[key], dict)
            _assert_body_subset(value, actual[key])
        else:
            assert actual[key] == value


@pytest.mark.parametrize("interaction", json.loads(CONTRACT_PATH.read_text())["interactions"])
def test_provider_contracts(api_client, kw_zip_bytes: bytes, interaction: dict[str, Any]) -> None:
    state_values = _apply_state(interaction.get("providerState"), api_client, kw_zip_bytes)
    request = interaction["request"]
    response = interaction["response"]
    path = request["path"].replace("{{jobId}}", state_values.get("jobId", ""))

    result = api_client.request(request["method"], path)
    assert result.status_code == response["status"], interaction["description"]
    if "body" in response:
        _assert_body_subset(response["body"], result.json())
