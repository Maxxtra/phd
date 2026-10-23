"""Seeded synthetic workload generator with common random numbers (CRN).

Independent random streams are spawned from the seed for each attribute, so a sweep
over one parameter (e.g. the secure-job fraction) leaves all other attributes of the
job stream unchanged. Security assignment is monotone in the secure fraction: the set
of secure jobs at fraction f is a subset of the set at any f' > f.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from seas.estimators import exec_time
from seas.models import Cap, Cluster, Job, JobType, is_eligible
from seas.models.io import Dist, NoiseSpec, WorkloadSpec

_STREAMS = ("arrival", "type", "work", "data", "slack", "sec_u", "sec_v", "noise")


def _rngs(seed: int) -> dict[str, np.random.Generator]:
    children = np.random.SeedSequence(seed).spawn(len(_STREAMS))
    return {name: np.random.default_rng(s) for name, s in zip(_STREAMS, children, strict=True)}


def _draw(d: Dist, rng: np.random.Generator, n: int) -> np.ndarray:
    if d.dist == "fixed":
        assert d.value is not None
        return np.full(n, float(d.value))
    if d.dist == "uniform":
        assert d.lo is not None and d.hi is not None
        return rng.uniform(d.lo, d.hi, n)
    assert d.mu is not None and d.sigma is not None
    return rng.lognormal(d.mu, d.sigma, n)


def best_case_time(job: Job, cluster: Cluster) -> float:
    """Fastest estimated execution time over eligible nodes (over all nodes if none eligible)."""
    elig = [n for n in cluster.nodes if is_eligible(job.required, n.capabilities, job.memory_gb, n.memory_gb)]
    pool = elig or list(cluster.nodes)
    return min(exec_time(job, n, cluster) for n in pool)


def generate(spec: WorkloadSpec, cluster: Cluster, seed: int, noise: NoiseSpec | None = None) -> list[Job]:
    r = _rngs(seed)
    n = spec.n_jobs
    types = list(spec.type_mix)
    probs = np.array([spec.type_mix[t] for t in types], dtype=float)
    probs = probs / probs.sum()

    inter = r["arrival"].exponential(1.0 / spec.arrival_rate_per_s, n)
    releases = np.cumsum(inter) - inter[0]  # first job at t = 0
    type_idx = r["type"].choice(len(types), size=n, p=probs)
    # Draw every per-type quantity for all jobs from fixed streams (CRN across type mixes).
    work_all = {t: _draw(spec.work[t], r["work"], n) for t in JobType}
    data_all = {t: _draw(spec.data_gb[t], r["data"], n) for t in JobType}
    slack = _draw(spec.deadline_slack, r["slack"], n)
    sec_u = r["sec_u"].uniform(0.0, 1.0, n)
    sec_v = r["sec_v"].uniform(0.0, 1.0, n)
    eta = r["noise"].normal(0.0, 1.0, n)

    secure_classes = list(spec.secure_mix)
    cum = np.cumsum([spec.secure_mix[c] for c in secure_classes], dtype=float)
    cum = cum / cum[-1]

    jobs: list[Job] = []
    for i in range(n):
        t = types[int(type_idx[i])]
        if sec_u[i] < spec.security_fraction:
            cls = secure_classes[int(np.searchsorted(cum, sec_v[i], side="right").clip(0, len(cum) - 1))]
            required = frozenset(Cap(c) for c in spec.security_classes[cls])
        else:
            required = frozenset()
        noise_val = 0.0
        if noise is not None and noise.sigma > 0:
            noise_val = max(noise.floor, noise.sigma * float(eta[i]))
        provisional = Job(
            id=f"j{i:04d}",
            type=t,
            work=float(work_all[t][i]),
            memory_gb=float(spec.memory_gb[t]),
            release=float(releases[i]),
            deadline=float(releases[i]) + 1.0,
            required=required,
            alpha=spec.alpha,
            data_gb=float(data_all[t][i]),
            noise=noise_val,
        )
        tb = best_case_time(provisional, cluster)
        deadline = float(releases[i]) + spec.deadline_floor_s + float(slack[i]) * tb
        jobs.append(provisional.model_copy(update={"deadline": deadline}))
    return jobs


def load_csv(path: str | Path) -> list[Job]:
    """Load an external job trace (columns = Job fields; 'required' is ';'-separated)."""
    jobs: list[Job] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            req = frozenset(Cap(c) for c in row.get("required", "").split(";") if c)
            jobs.append(
                Job(
                    id=row["id"],
                    type=JobType(row["type"]),
                    work=float(row["work"]),
                    memory_gb=float(row["memory_gb"]),
                    release=float(row["release"]),
                    deadline=float(row["deadline"]),
                    required=req,
                    alpha=float(row.get("alpha") or 0.5),
                    data_gb=float(row.get("data_gb") or 0.0),
                )
            )
    return sorted(jobs, key=lambda j: (j.release, j.id))
