"""Command-line interface: `seas --help`."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import typer

from seas.experiments import stats
from seas.models.io import load_cluster, load_scenario, load_workload

app = typer.Typer(add_completion=False, help="Security-Eligible, Energy-Aware Scheduler — Stage-1 research prototype.")


@app.command("offered-load")
def offered_load(
    cluster: str = "configs/clusters/C-B.yaml",
    workload: str = "configs/workloads/baseline-mix.yaml",
    target: float = 0.70,
    write: bool = False,
) -> None:
    """A-priori arrival rate for a target GPU-pool offered load (no policy executed; MD-2)."""
    from seas.experiments.load import rate_for_target

    lam, m = rate_for_target(load_workload(workload), load_cluster(cluster), target)
    typer.echo(f"E[GPU best-case time] = {m:.4f} s -> arrival_rate_per_s = {lam:.5f}")
    if write:
        p = Path(workload)
        text = re.sub(r"arrival_rate_per_s: [0-9.]+", f"arrival_rate_per_s: {lam:.5f}", p.read_text(), count=1)
        p.write_text(text)


@app.command()
def run(
    scenario: str,
    out: str = "results",
    workers: int = 2,
    trace_seeds: int = 1,
    seeds: str = typer.Option("", help="override, e.g. '1000,1001' (development only)"),
) -> None:
    """Run a scenario grid (all policies x sweep points x seeds)."""
    from seas.experiments.runner import run_scenario

    sc = load_scenario(scenario)
    seed_list = [int(s) for s in seeds.split(",")] if seeds else None
    if sc.status == "confirmatory" and seed_list is not None:
        raise typer.BadParameter("confirmatory scenarios must run their preregistered seeds")
    df = run_scenario(sc, scenario, out, workers, trace_seeds, seed_list)
    typer.echo(f"{sc.id}: {len(df)} runs -> {out}/{sc.id}/runs.csv")


@app.command()
def analyze(results: str = typer.Argument("results", help="results directory")) -> None:
    """Summaries and secondary pairwise tests for every scenario; confirmatory evaluation."""
    root = Path(results)
    for f in sorted(root.glob("*/runs.csv")):
        if f.parent.name == "scaling":
            continue
        df = stats.add_common_idle(pd.read_csv(f))
        stats.summarize(df).to_csv(f.parent / "summary.csv", index=False)
        stats.pairwise(df).to_csv(f.parent / "pairwise.csv", index=False)
        typer.echo(f"analysed {f.parent.name}")
    if all((root / s / "runs.csv").exists() for s in ("S1", "S4", "S7")):
        conf = stats.evaluate_confirmatory(root)
        (root / "CONFIRMATORY.json").write_text(json.dumps(conf, indent=1, default=float))
        for k, v in conf["summary"].items():
            typer.echo(
                f"{k}: p={v['p']:.4g} p_holm={v['p_holm']:.4g} -> {'supported' if v['supported'] else 'NOT supported'}"
            )


@app.command()
def report(results: str = typer.Argument("results", help="results directory"), poster: str = "poster") -> None:
    """Write results/RESULTS.md and poster/generated/results.tex."""
    from seas.experiments.report import write_report

    conf = json.loads((Path(results) / "CONFIRMATORY.json").read_text())
    write_report(Path(results), conf, Path(poster))
    typer.echo("wrote results/RESULTS.md and poster/generated/results.tex")


@app.command()
def verify(results: str = typer.Argument("results", help="results directory"), rerun: bool = True) -> None:
    """Validation gates: eligibility, capacity, memory, conservation, hashes, determinism."""
    from seas.experiments.verify import verify_scenario

    errors: list[str] = []
    for d in sorted(Path(results).glob("*/config.resolved.yaml")):
        e = verify_scenario(d.parent, rerun=rerun)
        typer.echo(f"{d.parent.name}: {'OK' if not e else f'{len(e)} error(s)'}")
        errors += e
    for msg in errors[:50]:
        typer.echo("  " + msg)
    if errors:
        raise typer.Exit(code=1)
    typer.echo("eligibility_violations_total=0 conservation=OK capacity=OK determinism=OK")


@app.command()
def scaling(out: str = "results") -> None:
    """Exploratory decision-latency scaling benchmark (wall-clock; machine-dependent)."""
    from seas.experiments.scaling import run_scaling

    df = run_scaling(out)
    typer.echo(df.groupby(["nodes", "policy"])[["sched_mean_us", "sched_p95_us"]].mean().round(0).to_string())


@app.command()
def plot(results: str = typer.Argument("results", help="results directory"), out: str = "figures") -> None:
    """Regenerate every figure from results/ and write figures/MANIFEST.md."""
    from seas.experiments.runner import git_sha
    from seas.viz import figures as F

    root, o = Path(results), Path(out)
    conf = json.loads((root / "CONFIRMATORY.json").read_text())
    made: list[tuple[str, str]] = []
    for fn, src in (
        (F.fig_s1_energy_miss, "results/S1/runs.csv"),
        (F.fig_s1_rel_energy, "results/S1/runs.csv"),
        (F.fig_energy_budget, "results/S1/runs.csv"),
        (F.fig_s7_robustness, "results/S7/runs.csv"),
        (F.fig_gantt, "results/S1/base/{eft,seas}/seed_0/"),
        (F.fig_s2_tradeoff, "results/S2/runs.csv"),
        (F.fig_scaling, "results/scaling/runs.csv"),
    ):
        for p in fn(root, o):
            made.append((str(p), src))
    for p in F.fig_s4_gain(root, o, conf):
        made.append((str(p), "results/CONFIRMATORY.json (H2)"))
    paths, rec = F.fig_explanation(root, o)
    for p in paths:
        made.append((str(p), f"results/S1/base/seas/seed_0/decisions.jsonl job {rec['job']}"))
    sha = git_sha()
    lines = [
        "# Figure manifest (generated by `seas plot`)",
        "",
        f"Code commit: `{sha}`",
        "",
        "| figure | source data |",
        "|---|---|",
    ] + [f"| `{a}` | `{b}` |" for a, b in made if a.endswith(".pdf")]
    (o / "MANIFEST.md").write_text("\n".join(lines) + "\n")
    typer.echo(f"{len(made)} files written to {out}/")


@app.command()
def explain(run_dir: str, job: str = typer.Option(..., "--job", help="job id, e.g. j0006")) -> None:
    """Print the decision record of one job."""
    for line in (Path(run_dir) / "decisions.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["job"] == job:
            typer.echo(json.dumps(r, indent=2))


if __name__ == "__main__":
    app()
