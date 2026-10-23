"""Per-run metrics (definitions: docs/methodology_decisions.md MD-4, MD-5)."""

from __future__ import annotations

from typing import Any

import numpy as np

from seas.estimators import dyn_energy
from seas.models import NodeClass
from seas.sim.engine import SimResult, eligible_nodes


def _union_length(intervals: list[tuple[float, float]]) -> float:
    total, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(intervals):
        if cur_e is None or s > cur_e:
            if cur_e is not None and cur_s is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None and cur_s is not None:
        total += cur_e - cur_s
    return total


def compute_metrics(res: SimResult) -> dict[str, Any]:
    cl = res.cluster
    recs = list(res.records.values())
    submitted = len(res.jobs)
    rej = [r for r in recs if r.status == "REJECTED"]
    exp = [r for r in recs if r.status == "EXPIRED"]
    comp = [r for r in recs if r.status == "COMPLETED"]
    late = [r for r in comp if r.late]
    eligible_sub = submitted - len(rej)
    e_dyn = float(sum(r.energy_dyn_j for r in comp))
    work = float(sum(r.job.work for r in comp))
    # relaxation bound: each completed job on its minimum-energy eligible node (ignores capacity/deadlines)
    e_lb = float(sum(min(dyn_energy(r.job, cl.node(n)) for n in eligible_nodes(r.job, cl)) for r in comp))
    last_end = max((r.end for r in comp if r.end is not None), default=res.first_arrival)
    horizon = last_end - res.first_arrival
    idle_own = sum(n.power_idle_w for n in cl.nodes) * horizon
    idle_busy = sum(n.power_idle_w * _union_length(res.busy_intervals[n.id]) for n in cl.nodes)
    util: dict[str, float] = {}
    for cls in NodeClass:
        nodes = [n for n in cl.nodes if n.cls == cls]
        cap_s = sum(n.capacity for n in nodes) * horizon
        busy = sum(
            r.end - r.start
            for r in comp
            if r.node_id and r.end is not None and r.start is not None and cl.node(r.node_id).cls == cls
        )
        util[f"util_{cls.value}"] = busy / cap_s if cap_s > 0 else 0.0
    resp = [r.end - r.job.release for r in comp if r.end is not None]
    wait = [r.start - r.job.release for r in comp if r.start is not None]
    on_gpu = sum(1 for r in comp if r.node_id and cl.node(r.node_id).cls == NodeClass.GPU)
    elig_counts = [len(eligible_nodes(j, cl)) for j in res.jobs]
    eligible_jobs = [c for c in elig_counts if c > 0]
    ns = np.array(res.decision_ns, dtype=float) / 1000.0
    reasons: dict[str, int] = {}
    for r in rej + exp:
        reasons[r.reason or "UNKNOWN"] = reasons.get(r.reason or "UNKNOWN", 0) + 1
    return {
        "policy": res.policy,
        "submitted": submitted,
        "rejected_ineligible": len(rej),
        "eligible_submitted": eligible_sub,
        "expired": len(exp),
        "completed": len(comp),
        "late": len(late),
        "on_time": len(comp) - len(late),
        "miss_rate": (len(late) + len(exp)) / eligible_sub if eligible_sub else 0.0,
        "expire_rate": len(exp) / eligible_sub if eligible_sub else 0.0,
        "late_rate": len(late) / eligible_sub if eligible_sub else 0.0,
        "energy_dyn_J": e_dyn,
        "energy_dyn_est_J": float(sum(r.est_energy_j for r in comp)),
        "energy_lb_J": e_lb,
        "work_completed": work,
        "energy_per_work_J": e_dyn / work if work > 0 else float("nan"),
        "last_end_s": last_end,
        "makespan_s": horizon,
        "energy_idle_own_J": idle_own,
        "energy_idle_busy_J": idle_busy,
        **util,
        "gpu_share": on_gpu / len(comp) if comp else 0.0,
        "mean_response_s": float(np.mean(resp)) if resp else float("nan"),
        "mean_wait_s": float(np.mean(wait)) if wait else float("nan"),
        "no_choice_fraction": (sum(1 for c in eligible_jobs if c == 1) / len(eligible_jobs)) if eligible_jobs else 0.0,
        "eligibility_violations": res.eligibility_violations,
        "waits": res.waits,
        "sched_mean_us": float(ns.mean()) if ns.size else 0.0,
        "sched_p95_us": float(np.percentile(ns, 95)) if ns.size else 0.0,
        "decision_points": int(ns.size),
        "reasons": reasons,
    }
