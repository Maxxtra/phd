"""A-priori arrival-rate setting (MD-2): uses only workload and cluster parameters.

Offered GPU-pool load = lambda * E[T_best * 1{fastest eligible node is a GPU}] / (#GPU slots).
lambda is chosen so that this equals the target (0.70). No scheduling policy is executed.
Development seeds (>= 1000) are used for the Monte-Carlo expectation.
"""

from __future__ import annotations

import numpy as np

from seas.estimators import exec_time
from seas.models import Cluster, NodeClass, is_eligible
from seas.models.io import WorkloadSpec
from seas.workloads import generate


def expected_gpu_best_time(spec: WorkloadSpec, cluster: Cluster, seeds: range = range(1000, 1050)) -> float:
    vals = []
    probe = spec.model_copy(update={"arrival_rate_per_s": 1.0})
    for s in seeds:
        for j in generate(probe, cluster, s):
            elig = [n for n in cluster.nodes if is_eligible(j.required, n.capabilities, j.memory_gb, n.memory_gb)]
            if not elig:
                vals.append(0.0)
                continue
            best = min(elig, key=lambda n: (exec_time(j, n, cluster), n.id))
            vals.append(exec_time(j, best, cluster) if best.cls == NodeClass.GPU else 0.0)
    return float(np.mean(vals))


def rate_for_target(spec: WorkloadSpec, cluster: Cluster, target: float = 0.70) -> tuple[float, float]:
    gpu_slots = sum(n.capacity for n in cluster.nodes if n.cls == NodeClass.GPU)
    m = expected_gpu_best_time(spec, cluster)
    return target * gpu_slots / m, m
