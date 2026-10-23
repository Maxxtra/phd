from __future__ import annotations

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from seas.estimators import actual_dyn_energy, compute_time, dyn_energy, exec_time, transfer_time
from seas.models import Cap, Job, JobType, is_eligible, needs_protection
from seas.models.io import ProvenanceError, load_cluster
from tests.conftest import FIX, job

ALL_CAPS = list(Cap)
SUBSETS = [frozenset(c) for r in range(len(ALL_CAPS) + 1) for c in itertools.combinations(ALL_CAPS, r)]


def test_eligibility_truth_table_exhaustive() -> None:
    assert len(SUBSETS) == 32
    for req, off in itertools.product(SUBSETS, SUBSETS):
        assert is_eligible(req, off, 1.0, 2.0) == req.issubset(off)
        assert not is_eligible(req, off, 3.0, 2.0)


@given(st.sets(st.sampled_from(ALL_CAPS)), st.sets(st.sampled_from(ALL_CAPS)))
def test_eligibility_property(req: set[Cap], off: set[Cap]) -> None:
    assert is_eligible(frozenset(req), frozenset(off), 0.0, 0.0) == (req <= off)


def test_protection_flag() -> None:
    assert needs_protection(frozenset({Cap.TEE_CPU}))
    assert needs_protection(frozenset({Cap.TEE_GPU, Cap.ATTESTED}))
    assert not needs_protection(frozenset({Cap.ENC_AT_REST, Cap.ATTESTED}))


def test_estimators_analytic(toy) -> None:  # type: ignore[no-untyped-def]
    cpu, gpu = toy.node("cpu-tee-0"), toy.node("gpu-0")
    j = Job(id="a", type=JobType.infer_small, work=20.0, memory_gb=4, release=0, deadline=10, data_gb=1.25)
    assert compute_time(j, cpu) == pytest.approx(20.0)
    assert transfer_time(j, toy) == pytest.approx(1.0)  # 8 * 1.25 GB / 10 Gbps
    assert exec_time(j, gpu, toy) == pytest.approx(1.0 + 1.0)
    assert dyn_energy(j, cpu) == pytest.approx((90 - 50) * 20.0)
    assert dyn_energy(j, gpu) == pytest.approx((220 - 70) * 1.0)
    jt = j.model_copy(update={"required": frozenset({Cap.TEE_CPU})})
    assert compute_time(jt, cpu) == pytest.approx(1.10 * 20.0)
    assert dyn_energy(jt, cpu) == pytest.approx(40 * 22.0)
    jn = j.model_copy(update={"noise": 0.5})
    assert actual_dyn_energy(jn, cpu) == pytest.approx(1.5 * dyn_energy(j, cpu))


def test_validation_errors() -> None:
    with pytest.raises(ValidationError):
        job("x", release=5, deadline=5)
    with pytest.raises(ValidationError):
        job("x", alpha=1.5)


def test_calibrated_requires_provenance() -> None:
    with pytest.raises(ProvenanceError):
        load_cluster(FIX / "toy_cluster.yaml", require_provenance=True)


def test_power_must_exceed_idle(toy) -> None:  # type: ignore[no-untyped-def]
    data = toy.node("gpu-0").model_dump()
    data["profile"][JobType.prep]["power_load_w"] = 10.0
    from seas.models import Node

    with pytest.raises(ValidationError):
        Node.model_validate(data)
