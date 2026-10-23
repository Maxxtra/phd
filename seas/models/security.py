"""Security-capability model (SIMULATED eligibility only — see docs/methodology_decisions.md MD-3).

Nodes *declare* capabilities; jobs *require* capabilities. A job is eligible on a node
iff every required capability is declared by the node (set inclusion) and the node has
enough memory. No ordering between capabilities is assumed.

Semantics (documented, not enforced by any real mechanism in Stage 1):
  ENC_AT_REST     data encrypted at rest on the node
  ENC_IN_TRANSIT  data encrypted in transit to/from the node
  TEE_CPU         job must run inside a CPU confidential VM / enclave
  TEE_GPU         job's GPU memory must be protected by GPU confidential computing
  ATTESTED        node can present remote attestation evidence
"""

from __future__ import annotations

from enum import StrEnum


class Cap(StrEnum):
    ENC_AT_REST = "ENC_AT_REST"
    ENC_IN_TRANSIT = "ENC_IN_TRANSIT"
    TEE_CPU = "TEE_CPU"
    TEE_GPU = "TEE_GPU"
    ATTESTED = "ATTESTED"


TEE_CAPS: frozenset[Cap] = frozenset({Cap.TEE_CPU, Cap.TEE_GPU})


def is_eligible(required: frozenset[Cap], offered: frozenset[Cap], mem_req_gb: float, mem_node_gb: float) -> bool:
    """Security-capability inclusion and memory fit."""
    return required <= offered and mem_req_gb <= mem_node_gb


def needs_protection(required: frozenset[Cap]) -> bool:
    """True if the job requires protected (TEE) execution, which incurs the modelled slowdown."""
    return bool(required & TEE_CAPS)
