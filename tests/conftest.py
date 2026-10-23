from __future__ import annotations

from pathlib import Path

import pytest

from seas.models import Cap, Cluster, Job, JobType
from seas.models.io import load_cluster

FIX = Path(__file__).parent / "fixtures"
ENC = frozenset({Cap.ENC_AT_REST, Cap.ENC_IN_TRANSIT})


@pytest.fixture
def toy() -> Cluster:
    return load_cluster(FIX / "toy_cluster.yaml")


def job(
    jid: str,
    jtype: str = "infer_small",
    work: float = 20.0,
    release: float = 0.0,
    deadline: float = 100.0,
    required: frozenset[Cap] = frozenset(),
    mem: float = 4.0,
    alpha: float = 0.5,
    noise: float = 0.0,
) -> Job:
    return Job(
        id=jid,
        type=JobType(jtype),
        work=work,
        memory_gb=mem,
        release=release,
        deadline=deadline,
        required=required,
        alpha=alpha,
        noise=noise,
    )
