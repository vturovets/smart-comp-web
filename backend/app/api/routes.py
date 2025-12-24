from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.errors import ApiError
from app.api.dependencies import get_job_service, get_settings_dep
from app.api.schemas import (
    ArtifactList,
    ArtifactModel,
    ConfigDefaultsResponse,
    ErrorResponse,
    JobCreateResponse,
    JobModel,
    ResultsUnion,
)
from app.core.contracts import ConfigOverrides, JobType
from app.core.job_service import JobService
from app.core.smart_comp import defaults_to_overrides, load_config_defaults

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/config/defaults",
    tags=["config"],
    response_model=ConfigDefaultsResponse,
)
def get_config_defaults(settings=Depends(get_settings_dep)) -> ConfigDefaultsResponse:
    defaults = defaults_to_overrides(load_config_defaults(settings.smart_comp_config_path))
    return ConfigDefaultsResponse(**defaults)


@router.post(
    "/jobs",
    status_code=201,
    tags=["jobs"],
    response_model=JobCreateResponse,
    responses={400: {"model": ErrorResponse}},
)
async def create_job(
    jobType: Annotated[JobType, Form(...)],
    config: Annotated[str, Form(...)],
    file1: UploadFile | None = File(default=None),
    file2: UploadFile | None = File(default=None),
    kwBundle: UploadFile | None = File(default=None),
    job_service: JobService = Depends(get_job_service),
) -> JobCreateResponse:
    try:
        parsed_config = ConfigOverrides.model_validate_json(config)
    except json.JSONDecodeError as exc:
        raise ApiError(400, "INVALID_CONFIG", f"Invalid config JSON: {exc}") from exc
    except ValidationError as exc:
        raise ApiError(400, "INVALID_CONFIG", "Config validation failed.", details={"errors": exc.errors()}) from exc

    record = job_service.create_job(
        job_type=jobType,
        config=parsed_config,
        file1=await file1.read() if file1 else None,
        file2=await file2.read() if file2 else None,
        kw_bundle=await kwBundle.read() if kwBundle else None,
    )
    return JobCreateResponse(jobId=record.job_id)


@router.get(
    "/jobs/{job_id}",
    tags=["jobs"],
    response_model=JobModel,
    responses={404: {"model": ErrorResponse}},
)
def get_job(job_id: str, job_service: JobService = Depends(get_job_service)) -> JobModel:
    record = job_service.get_job(job_id)
    if not record:
        raise ApiError(404, "NOT_FOUND", f"Job {job_id} not found.")
    return JobModel(**record.to_dict())


@router.post(
    "/jobs/{job_id}/cancel",
    tags=["jobs"],
    response_model=JobModel,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def cancel_job(job_id: str, job_service: JobService = Depends(get_job_service)) -> JobModel:
    record = job_service.cancel_job(job_id)
    return JobModel(**record.to_dict())


@router.get(
    "/jobs/{job_id}/results",
    tags=["jobs"],
    response_model=ResultsUnion,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def get_results(job_id: str, job_service: JobService = Depends(get_job_service)) -> ResultsUnion:
    results = job_service.get_results(job_id)
    return results


@router.get(
    "/jobs/{job_id}/artifacts",
    tags=["jobs"],
    response_model=ArtifactList,
    responses={404: {"model": ErrorResponse}},
)
def list_artifacts(job_id: str, job_service: JobService = Depends(get_job_service)) -> ArtifactList:
    artifacts = job_service.list_artifacts(job_id)
    serialized = [
        ArtifactModel(
            name=artifact["name"],
            contentType=artifact["contentType"],
            sizeBytes=artifact["sizeBytes"],
            createdAt=artifact["createdAt"],
        )
        for artifact in artifacts
    ]
    return ArtifactList(jobId=job_id, artifacts=serialized)


@router.get(
    "/jobs/{job_id}/artifacts/{artifact_name:path}",
    tags=["jobs"],
    responses={404: {"model": ErrorResponse}},
)
def get_artifact(
    job_id: str,
    artifact_name: str,
    job_service: JobService = Depends(get_job_service),
) -> FileResponse:
    path = job_service.get_artifact_path(job_id, artifact_name)
    return FileResponse(path)
