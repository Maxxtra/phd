"""YAML loaders for clusters, workload specs and scenarios."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from seas.models.job import JobType
from seas.models.node import Cluster

REPO_ROOT = Path(__file__).resolve().parents[2]


class ProvenanceError(ValueError):
    pass


def _read(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        p = REPO_ROOT / p
    with open(p, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping")
    return data


def resolve(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        p = REPO_ROOT / p
    return p


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(resolve(path).read_bytes()).hexdigest()


def load_cluster(path: str | Path, require_provenance: bool = False) -> Cluster:
    data = _read(path)
    if require_provenance and not data.get("provenance"):
        raise ProvenanceError(f"{path}: calibrated profiles must carry a provenance block")
    return Cluster.model_validate(data)


class Dist(BaseModel):
    model_config = ConfigDict(frozen=True)
    dist: Literal["fixed", "uniform", "lognormal"]
    value: float | None = None
    lo: float | None = None
    hi: float | None = None
    mu: float | None = None
    sigma: float | None = None


class WorkloadSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    n_jobs: int = Field(gt=0)
    arrival_rate_per_s: float = Field(gt=0)
    type_mix: dict[JobType, float]
    work: dict[JobType, Dist]
    memory_gb: dict[JobType, float]
    data_gb: dict[JobType, Dist]
    deadline_slack: Dist
    deadline_floor_s: float = Field(ge=0, default=0.0)
    security_fraction: float = Field(ge=0, le=1)
    secure_mix: dict[str, float]
    security_classes: dict[str, list[str]]
    alpha: float = Field(ge=0, le=1, default=0.5)


def load_workload(path: str | Path) -> WorkloadSpec:
    return WorkloadSpec.model_validate(_read(path))


class NoiseSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    sigma: float = Field(ge=0)
    floor: float = Field(default=-0.5, gt=-1.0)


class Scenario(BaseModel):
    """A scenario = cluster + workload + policies + seeds + optional sweep / overrides."""

    model_config = ConfigDict(frozen=True)

    id: str
    status: Literal["confirmatory", "exploratory", "correctness"]
    description: str
    cluster: str
    workload: str
    policies: list[str]
    seeds: list[int]
    sweep: dict[str, list[Any]] = Field(default_factory=dict)
    overrides: dict[str, Any] = Field(default_factory=dict)
    noise: NoiseSpec | None = None


def load_scenario(path: str | Path) -> Scenario:
    data = _read(path)
    seeds = data.get("seeds")
    if isinstance(seeds, dict):
        data["seeds"] = list(range(int(seeds["start"]), int(seeds["start"]) + int(seeds["count"])))
    return Scenario.model_validate(data)
