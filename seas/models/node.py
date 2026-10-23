from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from seas.models.job import JobType
from seas.models.security import Cap


class NodeClass(StrEnum):
    CPU = "CPU"
    GPU = "GPU"


class TypeProfile(BaseModel):
    """Per-slot throughput and per-slot loaded power for one job type (SYNTHETIC unless provenance)."""

    model_config = ConfigDict(frozen=True)

    throughput: float = Field(gt=0, description="work units per second per slot")
    power_load_w: float = Field(gt=0, description="node power attributable to one busy slot incl. idle share")


class Node(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    cls: NodeClass
    capacity: int = Field(ge=1, description="concurrent job slots")
    memory_gb: float = Field(gt=0)
    capabilities: frozenset[Cap] = frozenset()
    sigma_protected: float = Field(ge=1.0, default=1.0)
    power_idle_w: float = Field(ge=0)
    profile: dict[JobType, TypeProfile]

    @model_validator(mode="after")
    def _check(self) -> Node:
        if set(self.profile) != set(JobType):
            missing = set(JobType) - set(self.profile)
            raise ValueError(f"node {self.id}: profile missing job types {sorted(missing)}")
        for t, p in self.profile.items():
            if p.power_load_w <= self.power_idle_w:
                raise ValueError(f"node {self.id}/{t}: power_load_w must exceed power_idle_w")
        return self

    def delta_power(self, t: JobType) -> float:
        """Incremental (dynamic) power of one busy slot running type t."""
        return self.profile[t].power_load_w - self.power_idle_w


class Cluster(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    nodes: tuple[Node, ...]
    default_bandwidth_gbps: float = Field(gt=0, default=10.0)
    provenance: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _unique(self) -> Cluster:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate node ids")
        return self

    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)
