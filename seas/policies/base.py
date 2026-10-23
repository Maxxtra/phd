"""Policy interface.

A policy never sees ineligible nodes: the engine passes only security- and
memory-eligible candidates (fairness rule, MD-3). A policy decides (a) the order in
which waiting jobs are considered and (b) for each job, which node it wants — or None
to keep waiting without a target. The engine places the job iff that node can host it
now.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from seas.models import Job

if TYPE_CHECKING:
    from seas.sim.state import Candidate


class Policy(Protocol):
    name: str

    def order(self, waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]: ...

    def choose(self, job: Job, cands: list[Candidate], now: float) -> str | None: ...


def by_release(waiting: list[Job]) -> list[Job]:
    return sorted(waiting, key=lambda j: (j.release, j.id))


def by_slack(waiting: list[Job], now: float, min_T: dict[str, float]) -> list[Job]:
    return sorted(waiting, key=lambda j: (j.deadline - now - min_T[j.id], j.release, j.id))
