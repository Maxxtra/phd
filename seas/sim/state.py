"""Cluster state and placement candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

from seas.models import Cluster, Job

EPS = 1e-9


@dataclass(frozen=True)
class Running:
    job: Job
    node_id: str
    start: float
    est_end: float  # end predicted from estimates (what policies may know)
    end: float  # actual end (what the simulator executes)


@dataclass
class ClusterState:
    cluster: Cluster
    running: dict[str, list[Running]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for n in self.cluster.nodes:
            self.running.setdefault(n.id, [])

    def free_slots(self, node_id: str) -> int:
        return self.cluster.node(node_id).capacity - len(self.running[node_id])

    def free_mem(self, node_id: str) -> float:
        node = self.cluster.node(node_id)
        return node.memory_gb - sum(r.job.memory_gb for r in self.running[node_id])

    def fits_now(self, node_id: str, mem_gb: float) -> bool:
        return self.free_slots(node_id) >= 1 and self.free_mem(node_id) + EPS >= mem_gb

    def earliest_start(self, node_id: str, mem_gb: float, now: float) -> float:
        """Predicted earliest time a slot with enough memory frees on node_id.

        Uses *estimated* end times of running jobs (policies are not clairvoyant about
        noise). Does not account for other waiting jobs (no reservations, MD-5).
        """
        if self.fits_now(node_id, mem_gb):
            return now
        node = self.cluster.node(node_id)
        slots = self.free_slots(node_id)
        mem = self.free_mem(node_id)
        for r in sorted(self.running[node_id], key=lambda x: (x.est_end, x.job.id)):
            slots += 1
            mem += r.job.memory_gb
            if slots >= 1 and mem + EPS >= mem_gb:
                return max(now, r.est_end)
        # Unreachable when the job's memory fits the node (eligibility guarantees it).
        raise RuntimeError(f"job memory {mem_gb} can never fit node {node.id}")


@dataclass(frozen=True)
class Candidate:
    """One eligible (job, node) option as seen by a policy at decision time `now`."""

    node_id: str
    T: float  # estimated execution time
    E: float  # estimated dynamic energy
    est: float  # predicted earliest start
    resp: float  # predicted response time from now = est - now + T
    finish: float  # est + T
    feasible: bool  # finish <= deadline
    free_now: bool  # slot and memory available now
    E_hat: float  # E / min_eligible E
    R_hat: float  # resp / min_{feasible (or eligible if none feasible)} resp
    T_hat: float  # T / min_eligible T (informational)
