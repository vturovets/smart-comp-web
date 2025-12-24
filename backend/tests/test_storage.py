from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from app.core.storage import (
    cleanup_after_completion,
    ensure_within_size_limit,
    prepare_job_paths,
    safe_join,
    sweep_expired_jobs,
)


def test_prepare_job_paths_creates_expected_layout(tmp_path) -> None:
    job_paths = prepare_job_paths("job-123", tmp_path)

    assert job_paths.root == tmp_path / "job-123"
    assert job_paths.input_dir.exists()
    assert job_paths.output_dir.exists()
    assert job_paths.plots_dir.exists()
    assert job_paths.log_file.name == "tool.log"


def test_safe_join_prevents_path_traversal(tmp_path) -> None:
    with pytest.raises(ValueError):
        safe_join(tmp_path, "../escape")


def test_size_limit_guard() -> None:
    ensure_within_size_limit(512, 1024)
    with pytest.raises(ValueError):
        ensure_within_size_limit(2048, 1024)
    with pytest.raises(ValueError):
        ensure_within_size_limit(-1, 1024)
    with pytest.raises(ValueError):
        ensure_within_size_limit(1, 0)


def test_cleanup_after_completion_removes_intermediate_outputs(tmp_path) -> None:
    job_paths = prepare_job_paths("job-clean", tmp_path)
    cleaned = job_paths.output_dir / "data_cleaned.csv"
    sampled = job_paths.output_dir / "data_sampled.csv"
    cleaned.write_text("c")
    sampled.write_text("s")
    samples_dir = job_paths.output_dir / "samples"
    samples_dir.mkdir()
    (samples_dir / "sample.csv").write_text("x")

    removed = cleanup_after_completion(job_paths, clean_all=True)

    assert cleaned.exists() is False
    assert sampled.exists() is False
    assert samples_dir.exists() is False
    assert len(removed) >= 3


def test_ttl_sweeper_respects_cutoff(tmp_path) -> None:
    storage_root = tmp_path
    old_job = storage_root / "old"
    recent_job = storage_root / "recent"
    old_job.mkdir()
    recent_job.mkdir()

    reference = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    old_time = reference - timedelta(hours=2)
    recent_time = reference - timedelta(minutes=30)
    os.utime(old_job, (old_time.timestamp(), old_time.timestamp()))
    os.utime(recent_job, (recent_time.timestamp(), recent_time.timestamp()))

    deleted = sweep_expired_jobs(storage_root, ttl_hours=1, now=reference)

    assert old_job not in storage_root.iterdir()
    assert recent_job in storage_root.iterdir()
    assert set(deleted) == {old_job}


def test_ttl_zero_deletes_all(tmp_path) -> None:
    job_a = tmp_path / "a"
    job_b = tmp_path / "b"
    job_a.mkdir()
    job_b.mkdir()

    deleted = sweep_expired_jobs(tmp_path, ttl_hours=0, now=datetime.now(timezone.utc))

    assert not job_a.exists()
    assert not job_b.exists()
    assert set(deleted) == {job_a, job_b}
