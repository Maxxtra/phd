from __future__ import annotations

from seas.models import Cap
from seas.policies import ALL, make
from seas.policies.seas_policy import SEAS
from seas.sim.engine import simulate
from tests.conftest import ENC, job

TEE_CPU = ENC | {Cap.TEE_CPU}
TEE_GPU = ENC | {Cap.TEE_GPU, Cap.ATTESTED}


def test_no_eligible_node_rejected_for_every_policy(toy) -> None:  # type: ignore[no-untyped-def]
    jobs = [job("a", required=frozenset({Cap.TEE_GPU, Cap.ENC_AT_REST, Cap.ATTESTED})), job("b", mem=500.0), job("c")]
    for name in ALL:
        res = simulate(toy, jobs, make(name))
        assert res.records["a"].status == "COMPLETED"  # gpu-tee-0 offers TEE_GPU
        assert res.records["b"].status == "REJECTED" and res.records["b"].reason == "NO_ELIGIBLE_NODE_MEMORY"
    only_cpu = toy.model_copy(update={"nodes": tuple(n for n in toy.nodes if n.id != "gpu-tee-0")})
    res = simulate(only_cpu, [job("a", required=TEE_GPU)], make("seas"))
    assert res.records["a"].reason == "NO_ELIGIBLE_NODE_SECURITY"


def test_faster_ineligible_node_never_used(toy) -> None:  # type: ignore[no-untyped-def]
    """Figure-C case: gpu-0 is fastest for infer_small but lacks TEE_CPU."""
    jobs = [job(f"j{i}", required=TEE_CPU, release=float(i)) for i in range(6)]
    for name in ALL:
        res = simulate(toy, jobs, make(name))
        assert all(r.node_id != "gpu-0" for r in res.records.values())
        assert res.eligibility_violations == 0


def test_seas_alpha_extremes(toy) -> None:  # type: ignore[no-untyped-def]
    """prep: CPU is cheaper (energy) but GPU is faster. alpha=1 -> CPU; alpha=0 -> GPU."""
    jp = [job("p", jtype="prep", work=10.0, deadline=1000.0)]
    r1 = simulate(toy, jp, SEAS(alpha=1.0))
    r0 = simulate(toy, jp, SEAS(alpha=0.0))
    assert r1.records["p"].node_id == "cpu-tee-0"
    assert r0.records["p"].node_id in {"gpu-0", "gpu-tee-0"}
    assert r1.records["p"].energy_dyn_j < r0.records["p"].energy_dyn_j


def test_eft_picks_earliest_finish(toy) -> None:  # type: ignore[no-untyped-def]
    res = simulate(toy, [job("p", jtype="prep", work=10.0, deadline=1000.0)], make("eft"))
    assert res.records["p"].node_id == "gpu-0"  # ties by id: gpu-0 < gpu-tee-0


def test_energy_greedy_waits_for_cheapest(toy) -> None:  # type: ignore[no-untyped-def]
    # two big jobs that want the GPUs, then one infer_small that energy-greedy will wait for
    jobs = [
        job("L1", jtype="finetune", work=150.0, mem=40, deadline=10_000),
        job("L2", jtype="finetune", work=150.0, mem=40, deadline=10_000),
        job("s", jtype="infer_small", work=20.0, release=1.0, deadline=10_000),
    ]
    res = simulate(toy, jobs, make("energy-greedy"))
    assert res.records["s"].node_id in {"gpu-0", "gpu-tee-0"}
    assert res.records["s"].start is not None and res.records["s"].start >= 100.0 - 1e-9
    res_eft = simulate(toy, jobs, make("eft"))
    assert res_eft.records["s"].node_id == "cpu-tee-0"  # finishes earlier on the free CPU


def test_expiry_rule_uniform(toy) -> None:  # type: ignore[no-untyped-def]
    """A job that cannot meet its deadline even on its fastest node once it starts waiting expires."""
    one_gpu = toy.model_copy(update={"nodes": tuple(n for n in toy.nodes if n.id == "gpu-tee-0")})
    jobs = [
        job("big", jtype="finetune", work=150.0, mem=40, deadline=10_000),
        job("tight", jtype="infer_small", work=20.0, release=1.0, deadline=5.0),
    ]
    for name in ALL:
        res = simulate(one_gpu, jobs, make(name))
        assert res.records["tight"].status == "EXPIRED"
        assert res.records["tight"].reason == "DEADLINE_EXPIRED_WHILE_WAITING"


def test_capacity_and_memory_respected(toy) -> None:  # type: ignore[no-untyped-def]
    """GPU nodes have 1 slot; the CPU node has 2 slots but only 64 GB, so two 60 GB jobs never overlap."""
    jobs = [job(f"f{i}", jtype="infer_large", work=40.0, mem=60.0, deadline=10_000) for i in range(5)]
    for name in ALL:
        res = simulate(toy, jobs, make(name))
        for nid in ("cpu-tee-0", "gpu-0", "gpu-tee-0"):
            ivs = sorted((r.start, r.end) for r in res.records.values() if r.node_id == nid)
            for (_, prev_end), (next_start, _) in zip(ivs, ivs[1:], strict=False):
                assert next_start >= prev_end - 1e-9


def test_determinism(toy) -> None:  # type: ignore[no-untyped-def]
    jobs = [
        job(f"j{i}", jtype=t, release=i * 0.7, deadline=i * 0.7 + 60, required=TEE_CPU if i % 3 == 0 else frozenset())
        for i, t in enumerate(["prep", "infer_small", "pipe_stage"] * 8)
    ]
    for name in ALL:
        a = simulate(toy, jobs, make(name)).events_jsonl()
        b = simulate(toy, jobs, make(name)).events_jsonl()
        assert a == b


def test_late_counted_with_noise(toy) -> None:  # type: ignore[no-untyped-def]
    j = job("n", jtype="infer_small", work=20.0, deadline=1.5, noise=1.0)  # est 1 s on GPU, actual 2 s
    res = simulate(toy, [j], make("eft"))
    assert res.records["n"].status == "COMPLETED" and res.records["n"].late
