"""Statistical analysis (plan: docs/preregistration.md; non-inferiority per MD-1).

All comparisons are paired by seed. Effect size for paired data: matched-pairs
rank-biserial correlation r_rb = (W+ - W-) / (W+ + W-) over non-zero differences
(negative = first policy lower).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

BOOT = 10_000
BOOT_SEED = 20261023
NI_MARGIN = 0.02
ALPHA = 0.05


def bootstrap_ci(x: np.ndarray, fn: Any = np.mean, level: float = 0.95, seed: int = BOOT_SEED) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(BOOT, x.size))
    vals = fn(x[idx], axis=1)
    lo, hi = np.percentile(vals, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def bootstrap_upper(x: np.ndarray, level: float = 0.95, seed: int = BOOT_SEED) -> float:
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    vals = x[rng.integers(0, x.size, size=(BOOT, x.size))].mean(axis=1)
    return float(np.percentile(vals, level * 100))


def wilcoxon_p(d: np.ndarray, alternative: str) -> float:
    """One-sided Wilcoxon signed-rank p-value; 1.0 if all differences are zero."""
    d = np.asarray(d, dtype=float)
    if np.allclose(d, 0.0):
        return 1.0
    return float(stats.wilcoxon(d, alternative=alternative, zero_method="wilcox").pvalue)


def rank_biserial(d: np.ndarray) -> float:
    d = np.asarray(d, dtype=float)
    d = d[d != 0]
    if d.size == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d))
    wp, wm = ranks[d > 0].sum(), ranks[d < 0].sum()
    return float((wp - wm) / (wp + wm))


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj: dict[str, float] = {}
    running = 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[k] = running
    return adj


def non_inferiority(d: np.ndarray, margin: float = NI_MARGIN) -> dict[str, float]:
    """H0: E[d] >= margin vs H1: E[d] < margin (one-sided paired t-test), plus sensitivity analyses."""
    d = np.asarray(d, dtype=float)
    n = d.size
    mean = float(d.mean())
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    se = sd / np.sqrt(n) if n > 0 else float("nan")
    if se == 0:
        p_t = 0.0 if mean < margin else 1.0
        upper = mean
    else:
        tstat = (mean - margin) / se
        p_t = float(stats.t.cdf(tstat, df=n - 1))
        upper = mean + float(stats.t.ppf(0.95, df=n - 1)) * se
    return {
        "mean_diff": mean,
        "upper95_t": upper,
        "p_ni_t": p_t,
        "upper95_boot": bootstrap_upper(d),
        "p_ni_wilcoxon": wilcoxon_p(d - margin, "less"),
        "margin": margin,
        "n": float(n),
    }


def add_common_idle(df: pd.DataFrame) -> pd.DataFrame:
    """Always-on idle energy over the common horizon (latest completion over all policies), MD-4."""
    df = df.copy()
    keys = ["scenario", "point", "seed"]
    if "cluster_path" in df.columns:
        keys.append("cluster_path")
    horizon = df.groupby(keys)["makespan_s"].transform("max")
    df["horizon_common_s"] = horizon
    df["energy_idle_common_J"] = df["P_idle_total_W"] * horizon
    df["energy_total_common_J"] = df["energy_dyn_J"] + df["energy_idle_common_J"]
    df["energy_total_gated_J"] = df["energy_dyn_J"] + df["energy_idle_busy_J"]
    return df


SUMMARY_METRICS = [
    "energy_dyn_J",
    "miss_rate",
    "late_rate",
    "expire_rate",
    "rejected_ineligible",
    "energy_per_work_J",
    "energy_idle_common_J",
    "energy_total_common_J",
    "energy_idle_busy_J",
    "energy_total_gated_J",
    "makespan_s",
    "mean_response_s",
    "util_CPU",
    "util_GPU",
    "gpu_share",
    "no_choice_fraction",
    "energy_lb_J",
    "sched_mean_us",
    "sched_p95_us",
    "eligibility_violations",
]


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (point, pol), g in df.groupby(["point", "policy_spec"], sort=False):
        for m in SUMMARY_METRICS:
            if m not in g.columns:
                continue
            x = g.sort_values("seed")[m].to_numpy(dtype=float)
            lo, hi = bootstrap_ci(x)
            rows.append(
                {
                    "scenario": g["scenario"].iloc[0],
                    "status": g["status"].iloc[0],
                    "point": point,
                    "policy": pol,
                    "metric": m,
                    "mean": float(np.mean(x)),
                    "sd": float(np.std(x, ddof=1)) if x.size > 1 else 0.0,
                    "ci_lo": lo,
                    "ci_hi": hi,
                    "n": int(x.size),
                }
            )
    return pd.DataFrame(rows)


def paired(df: pd.DataFrame, point: str, a: str, b: str, metric: str) -> np.ndarray:
    g = df[df["point"] == point]
    xa = g[g["policy_spec"] == a].set_index("seed")[metric]
    xb = g[g["policy_spec"] == b].set_index("seed")[metric]
    common = xa.index.intersection(xb.index)
    return (xa.loc[common] - xb.loc[common]).to_numpy(dtype=float)


def paired_rel(df: pd.DataFrame, point: str, a: str, b: str, metric: str) -> np.ndarray:
    g = df[df["point"] == point]
    xa = g[g["policy_spec"] == a].set_index("seed")[metric]
    xb = g[g["policy_spec"] == b].set_index("seed")[metric]
    common = xa.index.intersection(xb.index)
    return (xa.loc[common] / xb.loc[common] - 1.0).to_numpy(dtype=float)


def pairwise(df: pd.DataFrame, focal: str = "seas") -> pd.DataFrame:
    """Secondary comparisons: focal vs every other policy, per point, for energy and miss rate."""
    rows = []
    for point in df["point"].unique():
        pols = [p for p in df[df["point"] == point]["policy_spec"].unique() if p != focal]
        if focal not in set(df[df["point"] == point]["policy_spec"]):
            continue
        for other in pols:
            for metric in ("energy_dyn_J", "miss_rate"):
                d = paired(df, point, focal, other, metric)
                rel = paired_rel(df, point, focal, other, metric) if metric == "energy_dyn_J" else d
                lo, hi = bootstrap_ci(d)
                rlo, rhi = bootstrap_ci(rel)
                rows.append(
                    {
                        "point": point,
                        "a": focal,
                        "b": other,
                        "metric": metric,
                        "n": d.size,
                        "mean_diff": float(d.mean()),
                        "median_diff": float(np.median(d)),
                        "ci_lo": lo,
                        "ci_hi": hi,
                        "mean_rel": float(rel.mean()),
                        "rel_ci_lo": rlo,
                        "rel_ci_hi": rhi,
                        "p_less": wilcoxon_p(d, "less"),
                        "p_greater": wilcoxon_p(d, "greater"),
                        "r_rb": rank_biserial(d),
                    }
                )
    out = pd.DataFrame(rows)
    if not out.empty:
        for col in ("p_less", "p_greater"):
            adj = holm({str(i): float(p) for i, p in out[col].items()})
            out[col + "_holm"] = [adj[str(i)] for i in out.index]
    return out


@dataclass
class HypothesisResult:
    name: str
    p: float
    p_holm: float
    supported: bool
    details: dict[str, Any]


def evaluate_confirmatory(results_root: str | Path) -> dict[str, Any]:
    root = Path(results_root)
    out: dict[str, Any] = {}
    p: dict[str, float] = {}

    s1 = add_common_idle(pd.read_csv(root / "S1" / "runs.csv"))
    dE = paired(s1, "base", "seas", "eft", "energy_dyn_J")
    relE = paired_rel(s1, "base", "seas", "eft", "energy_dyn_J")
    dM = paired(s1, "base", "seas", "eft", "miss_rate")
    p_a = wilcoxon_p(dE, "less")
    ni = non_inferiority(dM)
    h1 = {
        "energy_mean_diff_J": float(dE.mean()),
        "energy_diff_ci": bootstrap_ci(dE),
        "energy_rel_mean": float(relE.mean()),
        "energy_rel_ci": bootstrap_ci(relE),
        "energy_rel_median": float(np.median(relE)),
        "p_energy": p_a,
        "r_rb_energy": rank_biserial(dE),
        "miss_seas_mean": float(s1[(s1.policy_spec == "seas")]["miss_rate"].mean()),
        "miss_eft_mean": float(s1[(s1.policy_spec == "eft")]["miss_rate"].mean()),
        **{f"ni_{k}": v for k, v in ni.items()},
    }
    # ablation: ordering vs energy term
    dE_abl = paired(s1, "base", "seas", "eft-slack", "energy_dyn_J")
    relE_abl = paired_rel(s1, "base", "seas", "eft-slack", "energy_dyn_J")
    relE_ord = paired_rel(s1, "base", "eft-slack", "eft", "energy_dyn_J")
    h1["ablation_seas_vs_eftslack_rel_mean"] = float(relE_abl.mean())
    h1["ablation_seas_vs_eftslack_rel_ci"] = bootstrap_ci(relE_abl)
    h1["ablation_seas_vs_eftslack_p_less"] = wilcoxon_p(dE_abl, "less")
    h1["ablation_eftslack_vs_eft_rel_mean"] = float(relE_ord.mean())
    h1["ablation_eftslack_vs_eft_rel_ci"] = bootstrap_ci(relE_ord)
    p["H1"] = max(p_a, ni["p_ni_t"])
    out["H1"] = h1

    # H4 descriptive
    dG = paired(s1, "base", "energy-greedy", "seas", "miss_rate")
    out["H4"] = {
        "mean_diff_greedy_minus_seas": float(dG.mean()),
        "ci": bootstrap_ci(dG),
        "binding": bool(dG.mean() >= 0.05),
        "greedy_energy_rel_vs_seas": float(paired_rel(s1, "base", "energy-greedy", "seas", "energy_dyn_J").mean()),
    }

    s4 = pd.read_csv(root / "S4" / "runs.csv")
    levels = sorted({float(x.split("=")[1]) for x in s4["point"].unique()})
    gains = []
    for f in levels:
        pt = f"security_fraction={f}"
        gains.append(-paired_rel(s4, pt, "seas", "eft", "energy_dyn_J"))  # (E_eft - E_seas)/E_eft == -(seas/eft - 1)
    G = np.vstack(gains)  # levels x seeds
    fx = np.array(levels)
    slopes = np.array([np.polyfit(fx, G[:, i], 1)[0] for i in range(G.shape[1])])
    p["H2"] = wilcoxon_p(slopes, "greater")
    out["H2"] = {
        "levels": levels,
        "mean_gain_by_level": G.mean(axis=1).tolist(),
        "gain_ci_by_level": [bootstrap_ci(G[k]) for k in range(len(levels))],
        "slope_mean": float(slopes.mean()),
        "slope_ci": bootstrap_ci(slopes),
        "p_slope_greater": p["H2"],
        "r_rb": rank_biserial(slopes),
    }

    s7 = pd.read_csv(root / "S7" / "runs.csv")
    h3: dict[str, Any] = {}
    for pt in sorted(s7["point"].unique()):
        dE7 = paired(s7, pt, "seas", "eft", "energy_dyn_J")
        dM7 = paired(s7, pt, "seas", "energy-greedy", "miss_rate")
        h3[pt] = {
            "energy_rel_mean": float(paired_rel(s7, pt, "seas", "eft", "energy_dyn_J").mean()),
            "energy_rel_ci": bootstrap_ci(paired_rel(s7, pt, "seas", "eft", "energy_dyn_J")),
            "p_energy_less": wilcoxon_p(dE7, "less"),
            "miss_diff_vs_greedy_mean": float(dM7.mean()),
            "miss_diff_ci": bootstrap_ci(dM7),
            "p_miss_less_vs_greedy": wilcoxon_p(dM7, "less"),
            "miss_diff_vs_eft_mean": float(paired(s7, pt, "seas", "eft", "miss_rate").mean()),
        }
    key = "noise_sigma=0.25"
    p["H3"] = max(h3[key]["p_energy_less"], h3[key]["p_miss_less_vs_greedy"])
    out["H3"] = h3

    adj = holm(p)
    out["summary"] = {k: {"p": p[k], "p_holm": adj[k], "supported": bool(adj[k] < ALPHA)} for k in p}
    return out
