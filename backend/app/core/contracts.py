from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class JobType(str, Enum):
    BOOTSTRAP_SINGLE = "BOOTSTRAP_SINGLE"
    BOOTSTRAP_DUAL = "BOOTSTRAP_DUAL"
    KW_PERMUTATION = "KW_PERMUTATION"
    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"


class PlotToggles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    histogram: bool | None = Field(default=None)
    boxplot: bool | None = Field(default=None)
    kde: bool | None = Field(default=None)


class ConfigOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alpha: float | None = Field(default=None)
    threshold: float | None = Field(default=None)
    bootstrapIterations: int | None = Field(default=None)
    permutationCount: int | None = Field(default=None)
    sampleSize: int | None = Field(default=None)
    outlierLowerBound: float | None = Field(default=None)
    outlierUpperBound: float | None = Field(default=None)
    descriptiveEnabled: bool | None = Field(default=None)
    createLog: bool | None = Field(default=None)
    cleanAll: bool | None = Field(default=None)
    plots: PlotToggles | None = Field(default=None)


class ConfigDefaultsModel(BaseModel):
    alpha: float | None = Field(default=None)
    threshold: float | None = Field(default=None)
    bootstrapIterations: int | None = Field(default=None)
    permutationCount: int | None = Field(default=None)
    sampleSize: int | None = Field(default=None)
    descriptiveEnabled: bool = Field(default=True)
    createLog: bool = Field(default=False)
    cleanAll: bool = Field(default=False)
    plots: PlotToggles = Field(default_factory=PlotToggles)
