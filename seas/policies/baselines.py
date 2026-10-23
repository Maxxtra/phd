"""Baseline policies. All of them see only eligible candidates."""

from __future__ import annotations

from seas.models import Job
from seas.policies.base import by_release, by_slack
from seas.sim.state import Candidate


class FifoFirstFit:
    """Release order; first eligible node (cluster order) with a free slot now; else wait."""

    name = "fifo-ff"

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
        return by_release(waiting)

    def choose(self, job: Job, cands: list[Candidate], now: float) -> str | None:
        for c in cands:  # candidates are in cluster order
            if c.free_now:
                return c.node_id
        return None


def eft_choice(cands: list[Candidate]) -> str:
    """Earliest predicted finish (HEFT insertion rule for independent jobs); ties by node id."""
    return min(cands, key=lambda c: (c.finish, c.node_id)).node_id


class EFT:
    """Release order; node with the earliest predicted finish time (may wait for it)."""

    name = "eft"

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
        return by_release(waiting)

    def choose(self, job: Job, cands: list[Candidate], now: float) -> str | None:
        return eft_choice(cands)


class EFTSlack(EFT):
    """Ablation: EFT node choice with least-slack-first job ordering (as used by seas)."""

    name = "eft-slack"

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
        return by_slack(waiting, now, min_T)


class EnergyGreedy:
    """Negative control: always wait for the minimum-energy eligible node; ignores deadlines."""

    name = "energy-greedy"

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
        return by_release(waiting)

    def choose(self, job: Job, cands: list[Candidate], now: float) -> str | None:
        return min(cands, key=lambda c: (c.E, c.node_id)).node_id
