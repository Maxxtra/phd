"""Time and energy estimators (MODELLED; see docs/methodology_decisions.md MD-4).

rho_jn      = sigma_n if job needs protected execution else 1
compute_jn  = rho_jn * w_j / theta_{n,type}
transfer_jn = 8 * data_gb / bandwidth_gbps          (slot occupied, no incremental power)
T_jn        = compute_jn + transfer_jn               (estimated execution time)
E_jn        = (P_load - P_idle)_{n,type} * compute_jn (estimated dynamic energy)
"""

from __future__ import annotations

from seas.models import Cluster, Job, Node, needs_protection


def rho(job: Job, node: Node) -> float:
    return node.sigma_protected if needs_protection(job.required) else 1.0


def compute_time(job: Job, node: Node) -> float:
    return rho(job, node) * job.work / node.profile[job.type].throughput


def transfer_time(job: Job, cluster: Cluster) -> float:
    return 8.0 * job.data_gb / cluster.default_bandwidth_gbps


def exec_time(job: Job, node: Node, cluster: Cluster) -> float:
    """Estimated wall time the job occupies a slot."""
    return compute_time(job, node) + transfer_time(job, cluster)


def dyn_energy(job: Job, node: Node) -> float:
    """Estimated incremental (dynamic) energy in joules."""
    return node.delta_power(job.type) * compute_time(job, node)


def actual_compute_time(job: Job, node: Node) -> float:
    """Compute time actually charged by the simulator (estimate scaled by the job's noise)."""
    return compute_time(job, node) * (1.0 + job.noise)


def actual_exec_time(job: Job, node: Node, cluster: Cluster) -> float:
    return actual_compute_time(job, node) + transfer_time(job, cluster)


def actual_dyn_energy(job: Job, node: Node) -> float:
    return node.delta_power(job.type) * actual_compute_time(job, node)
