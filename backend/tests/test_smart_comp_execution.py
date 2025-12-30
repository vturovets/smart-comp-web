from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_csv_one() -> bytes:
    return b"value\n10\n12\n14\n16\n18\n20\n"


@pytest.fixture
def sample_csv_two() -> bytes:
    return b"value\n11\n13\n15\n17\n19\n21\n"


@pytest.fixture
def kw_group_files() -> list[tuple[str, bytes, str]]:
    return [
        ("GroupA.csv", b"value\n1\n2\n3\n4\n", "text/csv"),
        ("GroupB.csv", b"value\n5\n6\n7\n8\n", "text/csv"),
        ("GroupC.csv", b"value\n2\n4\n6\n8\n", "text/csv"),
    ]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _normalize_ids(result: dict, expected: dict) -> None:
    result["jobId"] = "normalized"
    expected["jobId"] = "normalized"


def test_bootstrap_single_flow(api_client, test_settings, sample_csv_one: bytes, golden_dir: Path) -> None:
    config = {
        "alpha": 0.05,
        "threshold": 18,
        "bootstrapIterations": 5,
        "sampleSize": 4,
        "plots": {"histogram": True, "boxplot": True},
        "createLog": True,
        "cleanAll": False,
    }
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_SINGLE", "config": json.dumps(config)},
        files=[("files", ("dataset.csv", sample_csv_one, "text/csv"))],
    )
    job_id = creation.json()["jobId"]
    output_dir = test_settings.storage_root / job_id / "output"

    results = _read_json(output_dir / "results.json")
    expected = _read_json(golden_dir / "bootstrap_single.json")
    _normalize_ids(results, expected)
    assert results == expected

    assert _read_text(output_dir / "results.txt") == _read_text(golden_dir / "bootstrap_single.txt")
    assert (output_dir / "tool.log").exists()
    assert sorted(p.name for p in (output_dir / "plots").glob("*.png"))


def test_bootstrap_dual_flow(
    api_client,
    test_settings,
    sample_csv_one: bytes,
    sample_csv_two: bytes,
    golden_dir: Path,
) -> None:
    config = {
        "alpha": 0.05,
        "bootstrapIterations": 6,
        "sampleSize": 4,
        "plots": {"histogram": True},
        "cleanAll": False,
    }
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "BOOTSTRAP_DUAL", "config": json.dumps(config)},
        files=[
            ("files", ("dataset1.csv", sample_csv_one, "text/csv")),
            ("files", ("dataset2.csv", sample_csv_two, "text/csv")),
        ],
    )
    job_id = creation.json()["jobId"]
    output_dir = test_settings.storage_root / job_id / "output"

    results = _read_json(output_dir / "results.json")
    expected = _read_json(golden_dir / "bootstrap_dual.json")
    _normalize_ids(results, expected)
    assert results == expected
    assert _read_text(output_dir / "results.txt") == _read_text(golden_dir / "bootstrap_dual.txt")


def test_descriptive_only_flow(api_client, test_settings, sample_csv_one: bytes, golden_dir: Path) -> None:
    config = {
        "descriptiveEnabled": True,
        "plots": {"histogram": True, "boxplot": True, "kde": True},
        "createLog": False,
    }
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "DESCRIPTIVE_ONLY", "config": json.dumps(config)},
        files=[("files", ("dataset.csv", sample_csv_one, "text/csv"))],
    )
    job_id = creation.json()["jobId"]
    output_dir = test_settings.storage_root / job_id / "output"

    results = _read_json(output_dir / "results.json")
    expected = _read_json(golden_dir / "descriptive_only.json")
    _normalize_ids(results, expected)
    assert results == expected
    assert _read_text(output_dir / "results.txt") == _read_text(golden_dir / "descriptive_only.txt")
    assert sorted(p.name for p in (output_dir / "plots").glob("*.png"))


def test_kw_permutation_flow(api_client, test_settings, kw_group_files: list[tuple[str, bytes, str]], golden_dir: Path) -> None:
    config = {
        "permutationCount": 5,
        "alpha": 0.05,
        "cleanAll": False,
    }
    creation = api_client.post(
        "/api/jobs",
        data={"jobType": "KW_PERMUTATION", "config": json.dumps(config)},
        files=[("files", entry) for entry in kw_group_files],
    )
    job_id = creation.json()["jobId"]
    output_dir = test_settings.storage_root / job_id / "output"

    results = _read_json(output_dir / "results.json")
    expected = _read_json(golden_dir / "kw_permutation.json")
    _normalize_ids(results, expected)
    assert results == expected
    assert _read_text(output_dir / "results.txt") == _read_text(golden_dir / "kw_permutation.txt")
    assert (output_dir / "kw_report.json").exists()
    assert (output_dir / "kw_summary.csv").exists()
