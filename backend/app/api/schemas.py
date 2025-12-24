from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import ConfigDefaultsModel, ConfigOverrides, JobType, PlotToggles
from app.core.jobs import JobStatus


class ErrorModel(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorModel
    requestId: str


class ProgressModel(BaseModel):
    step: str | None = None
    percent: float = Field(ge=0, le=100)
    message: str | None = None


class JobModel(BaseModel):
    jobId: str
    jobType: JobType
    status: JobStatus
    createdAt: datetime
    startedAt: datetime | None = None
    finishedAt: datetime | None = None
    taskId: str | None = None
    progress: ProgressModel
    error: str | None = None


class JobCreateResponse(BaseModel):
    jobId: str


class ArtifactModel(BaseModel):
    name: str
    contentType: str | None = None
    sizeBytes: int
    createdAt: datetime


class ArtifactList(BaseModel):
    jobId: str
    artifacts: list[ArtifactModel]


class DecisionModel(BaseModel):
    alpha: float | None = None
    pValue: float | None = None
    significant: bool | None = None


class PlotRef(BaseModel):
    kind: str | None = None
    artifactName: str


class BootstrapSingleResults(BaseModel):
    model_config = ConfigDict(extra="allow")

    jobId: str
    jobType: Literal[JobType.BOOTSTRAP_SINGLE]
    decision: DecisionModel
    metrics: dict[str, Any] = Field(default_factory=dict)
    descriptive: dict[str, Any] = Field(default_factory=dict)
    plots: list[PlotRef] = Field(default_factory=list)
    interpretation: dict[str, Any] | None = None


class BootstrapDualResults(BaseModel):
    model_config = ConfigDict(extra="allow")

    jobId: str
    jobType: Literal[JobType.BOOTSTRAP_DUAL]
    decision: DecisionModel
    metrics: dict[str, Any] = Field(default_factory=dict)
    descriptive: dict[str, Any] = Field(default_factory=dict)
    plots: list[PlotRef] = Field(default_factory=list)


class KwGroupFile(BaseModel):
    fileName: str
    n: int | None = None
    p95: float | None = None
    median: float | None = None


class KwGroupResult(BaseModel):
    groupName: str
    files: list[KwGroupFile] = Field(default_factory=list)


class KwPermutationResults(BaseModel):
    model_config = ConfigDict(extra="allow")

    jobId: str
    jobType: Literal[JobType.KW_PERMUTATION]
    decision: DecisionModel
    omnibus: dict[str, Any] = Field(default_factory=dict)
    groups: list[KwGroupResult] = Field(default_factory=list)
    plots: list[PlotRef] = Field(default_factory=list)


class DescriptiveOnlyResults(BaseModel):
    model_config = ConfigDict(extra="allow")

    jobId: str
    jobType: Literal[JobType.DESCRIPTIVE_ONLY]
    descriptive: dict[str, Any] = Field(default_factory=dict)
    plots: list[PlotRef] = Field(default_factory=list)


ResultsUnion = (
    BootstrapSingleResults
    | BootstrapDualResults
    | KwPermutationResults
    | DescriptiveOnlyResults
)


class ConfigDefaultsResponse(ConfigDefaultsModel):
    plots: PlotToggles = Field(default_factory=PlotToggles)
