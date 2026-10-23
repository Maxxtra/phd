"""Exploratory: wall-clock decision latency vs cluster size (C-B replicated k times, load scaled)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from seas.experiments.metrics import compute_metrics
from seas.models import Cluster
from seas.models.io import load_cluster, load_workload
from seas.policies import make
from seas.sim.engine import simulate
from seas.workloads import generate


def replicate(cl: Cluster, k: int) -> Cluster:
    nodes = tuple(n.model_copy(update={"id": f"{n.id}-r{i}"}) for i in range(k) for n in cl.nodes)
    return cl.model_copy(update={"nodes": nodes, "name": f"{cl.name}x{k}"})


def run_scaling(
    out_root: str = "results",
    ks: tuple[int, ...] = (1, 4, 16, 32),
    seeds: tuple[int, ...] = (0, 1, 2),
    jobs_per_replica: int = 100,
) -> pd.DataFrame:
    base = load_cluster("configs/clusters/C-B.yaml")
    spec0 = load_workload("configs/workloads/baseline-mix.yaml")
    rows = []
    for k in ks:
        cl = replicate(base, k)
        spec = spec0.model_copy(
            update={"n_jobs": jobs_per_replica * k, "arrival_rate_per_s": spec0.arrival_rate_per_s * k}
        )
        for s in seeds:
            jobs = generate(spec, cl, s)
            for p in ("eft", "seas"):
                m = compute_metrics(simulate(cl, jobs, make(p), record_decisions=False))
                rows.append(
                    {
                        "nodes": len(cl.nodes),
                        "jobs": len(jobs),
                        "seed": s,
                        "policy": p,
                        "sched_mean_us": m["sched_mean_us"],
                        "sched_p95_us": m["sched_p95_us"],
                        "decision_points": m["decision_points"],
                        "miss_rate": m["miss_rate"],
                    }
                )
                d = Path(out_root) / "scaling"
                d.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(rows).to_csv(d / "runs.csv", index=False)  # written incrementally
    return pd.DataFrame(rows)
