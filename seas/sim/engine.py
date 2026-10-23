"""Deterministic discrete-event simulator (semantics: docs/methodology_decisions.md MD-5).

Event processing at a time instant t:
  1. all FINISH events at t (free capacity), then all ARRIVE events at t;
     arriving jobs with no eligible node are rejected immediately (reason-coded);
  2. expiry: waiting jobs that cannot meet their deadline even if started now on their
     fastest eligible node are dropped (same rule for every policy);
  3. the policy orders waiting jobs; for each job in that order the engine builds the
     eligible candidates from the *current* state, asks the policy for a node, and
     places the job iff that node has a free slot and enough memory now. Otherwise the
     job keeps waiting (no reservations).
"""

from __future__ import annotations

import heapq
import json
import time
from dataclasses import dataclass, field
from typing import Any

from seas.estimators import actual_compute_time, actual_dyn_energy, actual_exec_time, dyn_energy, exec_time
from seas.models import Cluster, Job, is_eligible
from seas.policies.base import Policy
from seas.sim.state import EPS, Candidate, ClusterState, Running

FINISH, ARRIVE = 0, 1  # FINISH sorts before ARRIVE at equal times


def _r(x: float) -> float:
    """Round for stable serialisation (removes last-ulp platform noise in traces)."""
    return round(x, 9)


@dataclass
class JobRecord:
    job: Job
    status: str  # COMPLETED | EXPIRED | REJECTED
    node_id: str | None = None
    start: float | None = None
    end: float | None = None
    energy_dyn_j: float = 0.0
    est_energy_j: float = 0.0
    reason: str | None = None
    n_eligible: int = 0

    @property
    def late(self) -> bool:
        return self.status == "COMPLETED" and self.end is not None and self.end > self.job.deadline + EPS


@dataclass
class SimResult:
    policy: str
    cluster: Cluster
    jobs: list[Job]
    records: dict[str, JobRecord]
    events: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    decision_ns: list[int]
    eligibility_violations: int
    waits: int
    makespan: float
    first_arrival: float
    busy_intervals: dict[str, list[tuple[float, float]]] = field(default_factory=dict)

    def events_jsonl(self) -> str:
        return "".join(json.dumps(e, sort_keys=True) + "\n" for e in self.events)

    def decisions_jsonl(self) -> str:
        return "".join(json.dumps(d, sort_keys=True) + "\n" for d in self.decisions)


def eligible_nodes(job: Job, cluster: Cluster) -> list[str]:
    return [n.id for n in cluster.nodes if is_eligible(job.required, n.capabilities, job.memory_gb, n.memory_gb)]


def build_candidates(job: Job, elig: list[str], state: ClusterState, now: float) -> list[Candidate]:
    cl = state.cluster
    raw = []
    for nid in elig:
        node = cl.node(nid)
        T = exec_time(job, node, cl)
        E = dyn_energy(job, node)
        est = state.earliest_start(nid, job.memory_gb, now)
        raw.append(
            (nid, T, E, est, est - now + T, est + T, est + T <= job.deadline + EPS, state.fits_now(nid, job.memory_gb))
        )
    e_min = min(r[2] for r in raw)
    t_min = min(r[1] for r in raw)
    feas = [r for r in raw if r[6]]
    r_min = min(r[4] for r in (feas or raw))
    return [
        Candidate(
            node_id=nid,
            T=T,
            E=E,
            est=est,
            resp=resp,
            finish=fin,
            feasible=ok,
            free_now=free,
            E_hat=E / e_min,
            R_hat=resp / r_min,
            T_hat=T / t_min,
        )
        for (nid, T, E, est, resp, fin, ok, free) in raw
    ]


def _cand_dict(c: Candidate, chosen: str | None) -> dict[str, Any]:
    return {
        "node": c.node_id,
        "T": _r(c.T),
        "E": _r(c.E),
        "est": _r(c.est),
        "resp": _r(c.resp),
        "feasible": c.feasible,
        "free_now": c.free_now,
        "E_hat": _r(c.E_hat),
        "R_hat": _r(c.R_hat),
        "chosen": c.node_id == chosen,
    }


def simulate(cluster: Cluster, jobs: list[Job], policy: Policy, record_decisions: bool = True) -> SimResult:
    state = ClusterState(cluster)
    records: dict[str, JobRecord] = {}
    events: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    decision_ns: list[int] = []
    busy: dict[str, list[tuple[float, float]]] = {n.id: [] for n in cluster.nodes}
    elig_cache: dict[str, list[str]] = {}
    min_T: dict[str, float] = {}
    waiting: list[Job] = []
    violations = 0
    waits = 0

    heap: list[tuple[float, int, int, str, str]] = []
    seq = 0
    for j in sorted(jobs, key=lambda x: (x.release, x.id)):
        heapq.heappush(heap, (j.release, ARRIVE, seq, j.id, ""))
        seq += 1
    by_id = {j.id: j for j in jobs}

    while heap:
        now = heap[0][0]
        batch = []
        while heap and heap[0][0] <= now + EPS:
            batch.append(heapq.heappop(heap))
        for _, kind, _, jid, nid in batch:
            job = by_id[jid]
            if kind == FINISH:
                state.running[nid] = [r for r in state.running[nid] if r.job.id != jid]
                rec = records[jid]
                events.append({"t": _r(now), "type": "FINISH", "job": jid, "node": nid, "late": rec.late})
            else:
                elig = eligible_nodes(job, cluster)
                elig_cache[jid] = elig
                events.append({"t": _r(now), "type": "ARRIVE", "job": jid})
                if not elig:
                    sec_ok = [n for n in cluster.nodes if job.required <= n.capabilities]
                    reason = "NO_ELIGIBLE_NODE_SECURITY" if not sec_ok else "NO_ELIGIBLE_NODE_MEMORY"
                    records[jid] = JobRecord(job, "REJECTED", reason=reason)
                    events.append({"t": _r(now), "type": "REJECT", "job": jid, "reason": reason})
                    decisions.append(
                        {
                            "t": _r(now),
                            "job": jid,
                            "policy": policy.name,
                            "action": "REJECT",
                            "reason": reason,
                            "required": sorted(job.required),
                            "candidates": [],
                        }
                    )
                    continue
                min_T[jid] = min(exec_time(job, cluster.node(n), cluster) for n in elig)
                waiting.append(job)

        t0 = time.perf_counter_ns()
        # Expiry rule (uniform across policies).
        still = []
        for job in waiting:
            if now + min_T[job.id] > job.deadline + EPS:
                reason = "DEADLINE_EXPIRED_WHILE_WAITING"
                records[job.id] = JobRecord(job, "EXPIRED", reason=reason, n_eligible=len(elig_cache[job.id]))
                events.append({"t": _r(now), "type": "EXPIRE", "job": job.id, "reason": reason})
                if record_decisions:
                    decisions.append(
                        {
                            "t": _r(now),
                            "job": job.id,
                            "policy": policy.name,
                            "action": "EXPIRE",
                            "reason": reason,
                            "required": sorted(job.required),
                            "candidates": [],
                        }
                    )
            else:
                still.append(job)
        waiting = still

        placed: set[str] = set()
        for job in policy.order(waiting, now, min_T):
            elig = elig_cache[job.id]
            cands = build_candidates(job, elig, state, now)
            choice = policy.choose(job, cands, now)
            target = next((c for c in cands if c.node_id == choice), None)
            if target is None or not target.free_now:
                waits += 1
                continue
            node = cluster.node(target.node_id)
            t_est = exec_time(job, node, cluster)
            t_act = actual_exec_time(job, node, cluster)
            if not is_eligible(job.required, node.capabilities, job.memory_gb, node.memory_gb):
                violations += 1  # cannot happen: candidates are eligible by construction
            run = Running(job=job, node_id=node.id, start=now, est_end=now + t_est, end=now + t_act)
            state.running[node.id].append(run)
            busy[node.id].append((now, now + t_act))
            e_act = actual_dyn_energy(job, node)
            records[job.id] = JobRecord(
                job,
                "COMPLETED",
                node_id=node.id,
                start=now,
                end=now + t_act,
                energy_dyn_j=e_act,
                est_energy_j=dyn_energy(job, node),
                n_eligible=len(elig),
            )
            heapq.heappush(heap, (now + t_act, FINISH, seq, job.id, node.id))
            seq += 1
            placed.add(job.id)
            events.append(
                {
                    "t": _r(now),
                    "type": "START",
                    "job": job.id,
                    "node": node.id,
                    "end": _r(now + t_act),
                    "compute_s": _r(actual_compute_time(job, node)),
                    "mem": job.memory_gb,
                    "req": sorted(job.required),
                    "deadline": _r(job.deadline),
                }
            )
            if record_decisions:
                decisions.append(
                    {
                        "t": _r(now),
                        "job": job.id,
                        "type": job.type.value,
                        "policy": policy.name,
                        "action": "PLACE",
                        "node": node.id,
                        "start": _r(now),
                        "end_est": _r(now + t_est),
                        "deadline": _r(job.deadline),
                        "alpha": job.alpha,
                        "required": sorted(job.required),
                        "work": _r(job.work),
                        "data_gb": _r(job.data_gb),
                        "memory_gb": job.memory_gb,
                        "candidates": [_cand_dict(c, node.id) for c in cands],
                        "ineligible": [n.id for n in cluster.nodes if n.id not in elig],
                    }
                )
        waiting = [j for j in waiting if j.id not in placed]
        decision_ns.append(time.perf_counter_ns() - t0)

        if not heap and waiting:  # defensive: should be impossible (MD-5)
            for job in waiting:
                records[job.id] = JobRecord(job, "EXPIRED", reason="STARVED", n_eligible=len(elig_cache[job.id]))
                events.append({"t": _r(now), "type": "EXPIRE", "job": job.id, "reason": "STARVED"})
            waiting = []

    ends = [r.end for r in records.values() if r.end is not None]
    first = min(j.release for j in jobs) if jobs else 0.0
    return SimResult(
        policy=policy.name,
        cluster=cluster,
        jobs=jobs,
        records=records,
        events=events,
        decisions=decisions,
        decision_ns=decision_ns,
        eligibility_violations=violations,
        waits=waits,
        makespan=(max(ends) - first) if ends else 0.0,
        first_arrival=first,
        busy_intervals=busy,
    )
