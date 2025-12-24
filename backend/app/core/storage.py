from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobPaths:
    root: Path
    input_dir: Path
    output_dir: Path
    plots_dir: Path
    log_file: Path


def safe_join(base: Path, *parts: str | Path) -> Path:
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*parts).resolve()
    if candidate == base_resolved or base_resolved in candidate.parents:
        return candidate
    raise ValueError(f"Unsafe path traversal attempted outside {base_resolved}: {candidate}")


def prepare_job_paths(job_id: str, storage_root: Path) -> JobPaths:
    job_root = safe_join(storage_root, job_id)
    input_dir = job_root / "input"
    output_dir = job_root / "output"
    plots_dir = output_dir / "plots"
    log_file = output_dir / "tool.log"

    plots_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    logger.debug("Prepared job directories at %s", job_root)
    return JobPaths(
        root=job_root,
        input_dir=input_dir,
        output_dir=output_dir,
        plots_dir=plots_dir,
        log_file=log_file,
    )


def ensure_within_size_limit(size_bytes: int, max_bytes: int) -> None:
    if size_bytes < 0:
        raise ValueError("Size cannot be negative.")
    if max_bytes <= 0:
        raise ValueError("Maximum size must be positive.")
    if size_bytes > max_bytes:
        raise ValueError(
            f"Payload size {size_bytes} exceeds configured limit of {max_bytes} bytes.",
        )


def cleanup_job(job_paths: JobPaths) -> None:
    if job_paths.root.exists():
        shutil.rmtree(job_paths.root, ignore_errors=True)
        logger.info("Removed job directory %s", job_paths.root)


def cleanup_intermediate_outputs(job_paths: JobPaths) -> list[Path]:
    removed: list[Path] = []
    patterns = ("*_cleaned.csv", "*_sampled.csv", "*_sample.csv")

    for pattern in patterns:
        for file_path in job_paths.output_dir.glob(pattern):
            file_path.unlink(missing_ok=True)
            removed.append(file_path)

    samples_dir = job_paths.output_dir / "samples"
    if samples_dir.exists():
        shutil.rmtree(samples_dir, ignore_errors=True)
        removed.append(samples_dir)

    logger.info("Removed %d intermediate artifacts for %s", len(removed), job_paths.root)
    return removed


def cleanup_after_completion(job_paths: JobPaths, clean_all: bool) -> list[Path]:
    if not clean_all:
        return []
    return cleanup_intermediate_outputs(job_paths)


def sweep_expired_jobs(
    storage_root: Path,
    ttl_hours: float | int | None,
    *,
    now: datetime | None = None,
) -> list[Path]:
    if ttl_hours is None or ttl_hours < 0:
        return []

    if not storage_root.exists():
        return []

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    cutoff = reference_time - timedelta(hours=ttl_hours)

    deleted: list[Path] = []
    for entry in storage_root.iterdir():
        if not entry.is_dir():
            continue

        try:
            resolved = safe_join(storage_root, entry.name)
        except ValueError:
            logger.warning("Skipping suspicious path %s during TTL sweep", entry)
            continue

        if ttl_hours == 0:
            should_delete = True
        else:
            modified_time = datetime.fromtimestamp(
                resolved.stat().st_mtime,
                tz=timezone.utc,
            )
            should_delete = modified_time <= cutoff

        if should_delete:
            shutil.rmtree(resolved, ignore_errors=True)
            deleted.append(resolved)
            logger.info("Deleted expired job directory %s", resolved)

    return deleted
