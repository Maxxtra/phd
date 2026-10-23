"""Scheduling policies and registry."""

from __future__ import annotations

from collections.abc import Callable

from seas.policies.base import Policy
from seas.policies.baselines import EFT, EFTSlack, EnergyGreedy, FifoFirstFit
from seas.policies.seas_policy import SEAS, SEASEps

REGISTRY: dict[str, Callable[..., Policy]] = {
    "fifo-ff": FifoFirstFit,
    "eft": EFT,
    "eft-slack": EFTSlack,
    "energy-greedy": EnergyGreedy,
    "seas": SEAS,
    "seas-eps": SEASEps,
}

ALL = ["fifo-ff", "eft", "eft-slack", "energy-greedy", "seas", "seas-eps"]


def make(name: str, **params: float) -> Policy:
    if name not in REGISTRY:
        raise KeyError(f"unknown policy {name!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[name](**params)


__all__ = ["ALL", "REGISTRY", "Policy", "make"]
