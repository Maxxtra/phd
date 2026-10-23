"""Validation gates. Every check is independent of the policy code: traces are replayed against
the cluster configuration, and determinism is checked by re-running seeds and comparing hashes."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import yaml

from seas.experiments.runner import apply_point, parse_policy, point_label, sweep_points
from seas.models.io import REPO_ROOT, file_sha256, load_cluster, load_scenario
from seas.policies import make
from seas.sim.engine import simulate
from seas.workloads import generate

EPS = 1e-6


def preregistered_hashes() -> dict[str, str]:
    text = (REPO_ROOT / "docs" / "preregistration.md").read_text()
    return dict(re.findall(r"^\| (configs/\S+) \| ([0-9a-f]{64}) \|$", text, flags=re.M))


def replay_trace(events_path: Path, cluster_path: str) -> list[str]:
    errors: list[str] = []
    cl = load_cluster(cluster_path)
    caps = {n.id: n.capabilities for n in cl.nodes}
    active: dict[str, dict[str, float]] = {n.id: {} for n in cl.nodes}
    counts = {"ARRIVE": 0, "REJECT": 0, "EXPIRE": 0, "START": 0, "FINISH": 0}
    for line in events_path.read_text().splitlines():
        e = json.loads(line)
        counts[e["type"]] += 1
        if e["type"] == "START":
            nid = e["node"]
            if not set(e["req"]) <= {c.value for c in caps[nid]}:
                errors.append(f"{events_path}: eligibility violation {e['job']} on {nid}")
            active[nid][e["job"]] = e["mem"]
            node = cl.node(nid)
            if len(active[nid]) > node.capacity:
                errors.append(f"{events_path}: capacity exceeded on {nid} at t={e['t']}")
            if sum(active[nid].values()) > node.memory_gb + EPS:
                errors.append(f"{events_path}: memory exceeded on {nid} at t={e['t']}")
        elif e["type"] == "FINISH":
            active[e["node"]].pop(e["job"], None)
    if counts["ARRIVE"] != counts["REJECT"] + counts["EXPIRE"] + counts["START"]:
        errors.append(f"{events_path}: conservation violated {counts}")
    if counts["START"] != counts["FINISH"]:
        errors.append(f"{events_path}: START/FINISH mismatch {counts}")
    stored = (events_path.parent / "trace.sha256").read_text().strip()
    if hashlib.sha256(events_path.read_bytes()).hexdigest() != stored:
        errors.append(f"{events_path}: stored trace hash mismatch")
    return errors


def verify_scenario(sc_dir: Path, rerun: bool = True) -> list[str]:
    errors: list[str] = []
    resolved = yaml.safe_load((sc_dir / "config.resolved.yaml").read_text())
    sc_file = resolved["scenario_file"]
    sc = load_scenario(sc_file)
    if sc.status == "confirmatory":
        pre = preregistered_hashes()
        for f in (sc_file, sc.workload, sc.cluster):
            key = f if f.startswith("configs/") else str(Path(f).relative_to(REPO_ROOT))
            if key not in pre:
                errors.append(f"{sc.id}: {key} not in preregistration")
            elif pre[key] != file_sha256(f):
                errors.append(f"{sc.id}: {key} changed since preregistration")
    df = pd.read_csv(sc_dir / "runs.csv")
    if (df["eligibility_violations"] != 0).any():
        errors.append(f"{sc.id}: eligibility violations in runs.csv")
    bad = df[df["submitted"] != df["rejected_ineligible"] + df["expired"] + df["completed"]]
    if len(bad):
        errors.append(f"{sc.id}: {len(bad)} runs violate job conservation")
    if "reason_STARVED" in df.columns and df["reason_STARVED"].fillna(0).sum() > 0:
        errors.append(f"{sc.id}: starved jobs present")
    for ev in sc_dir.glob("*/*/seed_*/events.jsonl"):
        row = df[(df["point"] == ev.parts[-4]) & (df["policy_spec"] == ev.parts[-3])].iloc[0]
        errors.extend(replay_trace(ev, row["cluster_path"]))
    if rerun:
        seed = resolved["seeds_run"][0]
        for point in sweep_points(sc):
            cluster, spec, noise, _ = apply_point(sc, point)
            jobs = generate(spec, cluster, seed, noise)
            for pspec in sc.policies:
                name, params = parse_policy(pspec)
                res = simulate(cluster, jobs, make(name, **params), record_decisions=False)
                h = hashlib.sha256(res.events_jsonl().encode()).hexdigest()
                row = df[(df["point"] == point_label(point)) & (df["policy_spec"] == pspec) & (df["seed"] == seed)]
                if row.empty or row["trace_sha256"].iloc[0] != h:
                    errors.append(f"{sc.id}/{point_label(point)}/{pspec}: non-deterministic trace for seed {seed}")
    return errors
