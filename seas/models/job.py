from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from seas.models.security import Cap


class JobType(StrEnum):
    prep = "prep"
    infer_small = "infer_small"
    infer_large = "infer_large"
    finetune = "finetune"
    pipe_stage = "pipe_stage"


class Job(BaseModel):
    """An independent, non-preemptible AI job."""

    model_config = ConfigDict(frozen=True)

    id: str
    type: JobType
    work: float = Field(gt=0, description="abstract work units")
    memory_gb: float = Field(gt=0)
    release: float = Field(ge=0)
    deadline: float
    required: frozenset[Cap] = frozenset()
    alpha: float = Field(ge=0.0, le=1.0, default=0.5, description="energy weight (1=energy only)")
    data_gb: float = Field(ge=0.0, default=0.0)
    noise: float = Field(default=0.0, description="actual/estimated compute-time factor minus 1")

    @model_validator(mode="after")
    def _deadline_after_release(self) -> Job:
        if not self.deadline > self.release:
            raise ValueError(f"job {self.id}: deadline must be > release")
        if self.noise <= -1.0:
            raise ValueError(f"job {self.id}: noise must be > -1")
        return self
