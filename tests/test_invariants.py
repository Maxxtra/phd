"""Property-based invariants over random workloads, security mixes, loads and noise."""

from __future__ import annotations

import hashlib
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from seas.experiments.metrics import compute_metrics
from seas.experiments.verify import replay_trace
from seas.models.io import NoiseSpec, load_cluster, load_workload
from seas.policies import ALL, make
from seas.sim.engine import simulate
from seas.workloads import generate

CLUSTERS = ["configs/clusters/C-A.yaml", "configs/clusters/C-B.yaml", "configs/clusters/C-C.yaml"]


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    seed=st.integers(5000, 10_000),
    cl=st.sampled_from(CLUSTERS),
    frac=st.floats(0, 1),
    scale=st.floats(0.3, 2.5),
    sigma=st.sampled_from([0.0, 0.3]),
    n=st.integers(5, 60),
)
def test_invariants(tmp_path: Path, seed: int, cl: str, frac: float, scale: float, sigma: float, n: int) -> None:
    cluster = load_cluster(cl)
    spec = load_workload("configs/workloads/baseline-mix.yaml")
    spec = spec.model_copy(
        update={"n_jobs": n, "security_fraction": frac, "arrival_rate_per_s": spec.arrival_rate_per_s * scale}
    )
    jobs = generate(spec, cluster, seed, NoiseSpec(sigma=sigma) if sigma else None)
    for name in ALL:
        res = simulate(cluster, jobs, make(name))
        m = compute_metrics(res)
        assert m["eligibility_violations"] == 0
        assert m["submitted"] == m["rejected_ineligible"] + m["expired"] + m["completed"]
        assert m["reasons"].get("STARVED", 0) == 0
        d = tmp_path / name
        d.mkdir(exist_ok=True)
        ev = res.events_jsonl()
        (d / "events.jsonl").write_text(ev)
        (d / "trace.sha256").write_text(hashlib.sha256(ev.encode()).hexdigest())
        assert replay_trace(d / "events.jsonl", cl) == []


def test_crn_security_monotone() -> None:
    cl = load_cluster("configs/clusters/C-B.yaml")
    spec = load_workload("configs/workloads/baseline-mix.yaml")
    lo = generate(spec.model_copy(update={"security_fraction": 0.2}), cl, 7)
    hi = generate(spec.model_copy(update={"security_fraction": 0.6}), cl, 7)
    assert [j.release for j in lo] == [j.release for j in hi]
    assert [j.work for j in lo] == [j.work for j in hi]
    sec_lo = {j.id for j in lo if j.required}
    sec_hi = {j.id for j in hi if j.required}
    assert sec_lo <= sec_hi
