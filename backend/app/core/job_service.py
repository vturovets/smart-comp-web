from __future__ import annotations

import json
import logging
import mimetypes
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
import zipfile

from redis import Redis

from app.api.errors import ApiError
from app.core.config import Settings, get_settings
from app.core.contracts import ConfigOverrides, JobType
from app.core.jobs import JobRecord, JobRepository, JobStatus
from app.core.kw_zip import KWZipLayout, KWZipValidationError, validate_kw_zip
from app.core.smart_comp import defaults_to_overrides, load_config_defaults
from app.core.storage import JobPaths, cleanup_job, ensure_within_size_limit, prepare_job_paths, safe_join
from app.worker import tasks as worker_tasks

logger = logging.getLogger(__name__)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class JobService:
    """Coordinates request validation, storage and worker submission for API endpoints."""

    def __init__(self, repository: JobRepository, *, settings: Settings | None = None) -> None:
        self.repository = repository
        self.settings = settings or get_settings()

    @property
    def _max_bytes(self) -> int:
        return int(self.settings.max_upload_mb * 1024 * 1024)

    def create_job(
        self,
        job_type: JobType,
        config: ConfigOverrides,
        *,
        file1: bytes | None = None,
        file2: bytes | None = None,
        kw_bundle: bytes | None = None,
    ) -> JobRecord:
        job_id = str(uuid.uuid4())
        job_paths = prepare_job_paths(job_id, self.settings.storage_root)

        resolved_config = self._resolve_config(config)
        (job_paths.input_dir / "config.json").write_text(json.dumps(resolved_config), encoding="utf-8")
        payload: dict[str, Any] = _deep_merge({"jobType": job_type.value}, resolved_config)

        if job_type == JobType.KW_PERMUTATION:
            if kw_bundle is None:
                raise ApiError(400, "MISSING_FILE", "kwBundle is required for KW_PERMUTATION.")
            layout = self._validate_and_store_kw_bundle(job_paths, kw_bundle)
            payload["kwLayout"] = layout.layout
            payload["kwGroups"] = [group.name for group in layout.groups]
            if file1 or file2:
                raise ApiError(400, "INVALID_FILE", "file1/file2 are not accepted for KW_PERMUTATION.")
        elif job_type == JobType.BOOTSTRAP_DUAL:
            if file1 is None or file2 is None:
                raise ApiError(400, "MISSING_FILE", "file1 and file2 are required for BOOTSTRAP_DUAL.")
            self._store_file(job_paths.input_dir / "file1.csv", file1)
            self._store_file(job_paths.input_dir / "file2.csv", file2)
        elif job_type in (JobType.BOOTSTRAP_SINGLE, JobType.DESCRIPTIVE_ONLY):
            if file1 is None:
                raise ApiError(400, "MISSING_FILE", "file1 is required for the selected jobType.")
            self._store_file(job_paths.input_dir / "file1.csv", file1)
            if file2 is not None:
                self._store_file(job_paths.input_dir / "file2.csv", file2)
            if kw_bundle is not None:
                raise ApiError(400, "INVALID_FILE", "kwBundle is only valid for KW_PERMUTATION.")
        else:  # pragma: no cover - defensive branch
            raise ApiError(400, "INVALID_JOB_TYPE", "Unsupported jobType.")

        record = worker_tasks.enqueue_job(job_type.value, payload=payload, job_id=job_id)
        return record

    def _resolve_config(self, overrides: ConfigOverrides) -> dict[str, Any]:
        defaults = defaults_to_overrides(load_config_defaults(self.settings.smart_comp_config_path))
        overrides_dict = overrides.model_dump(exclude_none=True)
        merged = _deep_merge(defaults, overrides_dict)
        if "plots" not in merged:
            merged["plots"] = {}
        merged.setdefault("cleanAll", False)
        return merged

    def _store_file(self, destination: Path, data: bytes) -> None:
        ensure_within_size_limit(len(data), self._max_bytes)
        destination.write_bytes(data)

    def _validate_and_store_kw_bundle(self, job_paths: JobPaths, kw_bundle: bytes) -> KWZipLayout:
        ensure_within_size_limit(len(kw_bundle), self._max_bytes)
        try:
            layout = validate_kw_zip(kw_bundle)
        except KWZipValidationError as exc:
            raise ApiError(400, exc.code, str(exc), details=exc.details) from exc

        bundle_path = job_paths.input_dir / "kw_bundle.zip"
        bundle_path.write_bytes(kw_bundle)

        with zipfile.ZipFile(BytesIO(kw_bundle)) as zf:
            for group in layout.groups:
                for filename in group.files:
                    target_dir = job_paths.input_dir / group.name
                    target_dir.mkdir(parents=True, exist_ok=True)
                    with zf.open(filename) as src:
                        (target_dir / Path(filename).name).write_bytes(src.read())

        return layout

    def get_job(self, job_id: str) -> JobRecord | None:
        return self.repository.get(job_id)

    def cancel_job(self, job_id: str) -> JobRecord:
        record = self.repository.get(job_id)
        if not record:
            raise ApiError(404, "NOT_FOUND", f"Job {job_id} not found.")
        if record.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise ApiError(409, "INVALID_STATE", f"Job {job_id} is already {record.status.value}.")

        previous_status = record.status
        if record.task_id:
            worker_tasks.celery_app.control.revoke(record.task_id, terminate=True, signal="SIGTERM")
        self.repository.mark_cancel_flag(job_id)
        updated = self.repository.update_status(
            job_id,
            JobStatus.CANCELLED,
            finished_at=_utcnow(),
            error="Cancelled",
        )
        if previous_status == JobStatus.QUEUED:
            cleanup_job(prepare_job_paths(job_id, self.settings.storage_root))
        return updated

    def get_results(self, job_id: str) -> dict[str, Any]:
        record = self.repository.get(job_id)
        if not record:
            raise ApiError(404, "NOT_FOUND", f"Job {job_id} not found.")
        if record.status != JobStatus.COMPLETED:
            raise ApiError(409, "NOT_READY", f"Job {job_id} is not completed.")

        results_path = self._output_dir(job_id) / "results.json"
        if not results_path.exists():
            raise ApiError(404, "NOT_FOUND", "Results not available for this job.")
        return json.loads(results_path.read_text(encoding="utf-8"))

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        record = self.repository.get(job_id)
        if not record:
            raise ApiError(404, "NOT_FOUND", f"Job {job_id} not found.")
        output_dir = self._output_dir(job_id)
        if not output_dir.exists():
            return []

        artifacts: list[dict[str, Any]] = []
        for file_path in sorted(output_dir.glob("**/*")):
            if file_path.is_dir():
                continue
            stat = file_path.stat()
            artifacts.append(
                {
                    "name": str(file_path.relative_to(output_dir)),
                    "contentType": mimetypes.guess_type(str(file_path))[0] or "application/octet-stream",
                    "sizeBytes": stat.st_size,
                    "createdAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    "path": file_path,
                },
            )
        return artifacts

    def get_artifact_path(self, job_id: str, artifact_name: str) -> Path:
        output_dir = self._output_dir(job_id)
        try:
            target = safe_join(output_dir, artifact_name)
        except ValueError as exc:
            raise ApiError(400, "INVALID_ARTIFACT", str(exc)) from exc
        if not target.exists() or not target.is_file():
            raise ApiError(404, "NOT_FOUND", f"Artifact {artifact_name} not found.")
        return target

    def _output_dir(self, job_id: str) -> Path:
        try:
            job_root = safe_join(self.settings.storage_root, job_id)
        except ValueError as exc:
            raise ApiError(400, "INVALID_JOB", str(exc)) from exc
        return job_root / "output"


def _utcnow() -> datetime:
    now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now
