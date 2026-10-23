"""The proposed policy family.

seas  — least-slack-first; among deadline-feasible eligible nodes minimise
        alpha * E_hat + (1 - alpha) * R_hat, where E_hat is energy normalised by the
        job's minimum over eligible nodes and R_hat is predicted response time
        (wait + execution) normalised by its minimum over feasible nodes. If no node
        is feasible, fall back to the EFT choice (the job will be late or expire).
        This is a greedy per-decision heuristic (MD-5): no optimality guarantee.
seas-eps — epsilon-constraint variant: minimum energy among feasible nodes whose
        response time is within (1 + eps) of the best feasible response time.
"""

from __future__ import annotations

from seas.models import Job
from seas.policies.base import by_slack
from seas.policies.baselines import eft_choice
from seas.sim.state import Candidate


class SEAS:
    name = "seas"

    def __init__(self, alpha: float | None = None) -> None:
        if alpha is not None and not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        self.alpha_override = alpha

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
        return by_slack(waiting, now, min_T)

    def score(self, job: Job, c: Candidate) -> float:
        a = job.alpha if self.alpha_override is None else self.alpha_override
        return a * c.E_hat + (1.0 - a) * c.R_hat

    def choose(self, job: Job, cands: list[Candidate], now: float) -> str | None:
        feasible = [c for c in cands if c.feasible]
        if not feasible:
            return eft_choice(cands)
        return min(feasible, key=lambda c: (self.score(job, c), c.est, c.node_id)).node_id


class SEASEps:
    name = "seas-eps"

    def __init__(self, eps: float = 0.25) -> None:
        if eps < 0:
            raise ValueError("eps must be >= 0")
        self.eps = eps

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
        return by_slack(waiting, now, min_T)

    def choose(self, job: Job, cands: list[Candidate], now: float) -> str | None:
        feasible = [c for c in cands if c.feasible]
        if not feasible:
            return eft_choice(cands)
        best_resp = min(c.resp for c in feasible)
        ok = [c for c in feasible if c.resp <= (1.0 + self.eps) * best_resp + 1e-12]
        return min(ok, key=lambda c: (c.E, c.resp, c.node_id)).node_id
