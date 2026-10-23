"""Experiment grid runner: scenario x sweep point x seed x policy.

Jobs are generated once per (sweep point, seed) and shared by every policy (paired design,
common random numbers). Outputs per run:
  results/<scenario>/<point>/<policy>/seed_<k>/{metrics.json, events.jsonl[, decisions.jsonl], trace.sha256}
and an aggregate results/<scenario>/runs.csv (one row per run).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import platform
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

import seas
from seas.experiments.metrics import compute_metrics
from seas.models import Cluster
from seas.models.io import Dist, NoiseSpec, Scenario, WorkloadSpec, file_sha256, load_cluster, load_workload
from seas.policies import make
from seas.sim.engine import simulate
from seas.workloads import generate

_SPEC = re.compile(r"^([a-z\-]+)(?:\((.*)\))?$")


def parse_policy(spec: str) -> tuple[str, dict[str, float]]:
    m = _SPEC.match(spec.replace(" ", ""))
    if not m:
        raise ValueError(f"bad policy spec {spec!r}")
    params: dict[str, float] = {}
    if m.group(2):
        for kv in m.group(2).split(","):
            k, v = kv.split("=")
            params[k] = float(v)
    return m.group(1), params


def git_sha() -> str:
    """HEAD commit; suffixed with '+dirty' if code or configs differ from it (provenance)."""
    root = Path(__file__).resolve().parents[2]
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=root
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", "seas", "configs", "pyproject.toml"],
            capture_output=True,
            text=True,
            check=True,
            cwd=root,
        ).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def sweep_points(sc: Scenario) -> list[dict[str, Any]]:
    if not sc.sweep:
        return [{}]
    keys = list(sc.sweep)
    return [dict(zip(keys, vals, strict=True)) for vals in itertools.product(*(sc.sweep[k] for k in keys))]


def point_label(point: dict[str, Any]) -> str:
    if not point:
        return "base"
    return ",".join(f"{k}={Path(str(v)).stem if k == 'cluster' else v}" for k, v in point.items())


def apply_point(sc: Scenario, point: dict[str, Any]) -> tuple[Cluster, WorkloadSpec, NoiseSpec | None, str]:
    cluster_path = str(point.get("cluster", sc.cluster))
    cluster = load_cluster(cluster_path)
    spec = load_workload(sc.workload)
    upd: dict[str, Any] = dict(sc.overrides)
    if "security_fraction" in point:
        upd["security_fraction"] = float(point["security_fraction"])
    if "alpha" in point:
        upd["alpha"] = float(point["alpha"])
    rate_scale = float(point.get("arrival_scale", upd.pop("arrival_scale", 1.0)))
    upd["arrival_rate_per_s"] = spec.arrival_rate_per_s * rate_scale
    slack_scale = float(point.get("slack_scale", upd.pop("slack_scale", 1.0)))
    if slack_scale != 1.0:
        d = spec.deadline_slack
        upd["deadline_slack"] = Dist(
            dist=d.dist,
            value=None if d.value is None else d.value * slack_scale,
            lo=None if d.lo is None else d.lo * slack_scale,
            hi=None if d.hi is None else d.hi * slack_scale,
        )
    if "n_jobs" in point:
        upd["n_jobs"] = int(point["n_jobs"])
    spec = spec.model_copy(update=upd)
    noise = sc.noise
    if "noise_sigma" in point:
        noise = NoiseSpec(sigma=float(point["noise_sigma"]))
    return cluster, spec, noise, cluster_path


def _run_seed(args: tuple[Scenario, dict[str, Any], int, str, bool]) -> list[dict[str, Any]]:
    sc, point, seed, out_root, keep_traces = args
    cluster, spec, noise, cluster_path = apply_point(sc, point)
    jobs = generate(spec, cluster, seed, noise)
    rows = []
    for pspec in sc.policies:
        name, params = parse_policy(pspec)
        res = simulate(cluster, jobs, make(name, **params), record_decisions=keep_traces)
        m = compute_metrics(res)
        ev = res.events_jsonl()
        trace_hash = hashlib.sha256(ev.encode()).hexdigest()
        run_dir = Path(out_root) / sc.id / point_label(point) / pspec / f"seed_{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "scenario": sc.id,
            "status": sc.status,
            "point": point_label(point),
            "policy_spec": pspec,
            "seed": seed,
            "trace_sha256": trace_hash,
        }
        (run_dir / "metrics.json").write_text(json.dumps({**meta, **m}, indent=1, sort_keys=True))
        (run_dir / "trace.sha256").write_text(trace_hash + "\n")
        if keep_traces:
            (run_dir / "events.jsonl").write_text(ev)
            (run_dir / "decisions.jsonl").write_text(res.decisions_jsonl())
        row = {**meta, **{k: v for k, v in m.items() if k != "reasons"}}
        for k, v in m["reasons"].items():
            row[f"reason_{k}"] = v
        row["cluster_path"] = cluster_path
        row["P_idle_total_W"] = sum(n.power_idle_w for n in cluster.nodes)
        rows.append(row)
    return rows


def run_scenario(
    sc: Scenario,
    scenario_path: str,
    out_root: str = "results",
    workers: int = 2,
    trace_seeds: int = 1,
    seeds: list[int] | None = None,
) -> pd.DataFrame:
    seed_list = seeds if seeds is not None else sc.seeds
    tasks = [(sc, p, s, out_root, i < trace_seeds) for p in sweep_points(sc) for i, s in enumerate(seed_list)]
    rows: list[dict[str, Any]] = []
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(_run_seed, tasks, chunksize=1):
                rows.extend(r)
    else:
        for t in tasks:
            rows.extend(_run_seed(t))
    df = pd.DataFrame(rows).sort_values(["point", "policy_spec", "seed"]).reset_index(drop=True)
    sc_dir = Path(out_root) / sc.id
    sc_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(sc_dir / "runs.csv", index=False)
    resolved = {
        "scenario": sc.model_dump(mode="json"),
        "scenario_file": scenario_path,
        "scenario_sha256": file_sha256(scenario_path),
        "workload_sha256": file_sha256(sc.workload),
        "cluster_sha256": file_sha256(sc.cluster),
        "seeds_run": seed_list,
        "git_sha": git_sha(),
        "seas_version": seas.__version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    (sc_dir / "config.resolved.yaml").write_text(yaml.safe_dump(resolved, sort_keys=False))
    return df
