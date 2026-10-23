"""Vector figures generated from committed results (never from hand-typed numbers).

Each figure is drawn at its printed size on the A0 poster (mm), so font sizes are the
sizes on paper. Output: PDF (Type 42 fonts embedded) and SVG.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle  # noqa: E402

from seas.estimators import dyn_energy, exec_time  # noqa: E402
from seas.experiments.stats import add_common_idle, bootstrap_ci, paired_rel  # noqa: E402
from seas.models import Job, JobType  # noqa: E402
from seas.models.io import load_cluster  # noqa: E402

MM = 1 / 25.4
NAVY = "#1B365D"
TEXT = "#1A1A1A"
GREY = "#6B6B6B"
COL = {
    "fifo-ff": "#999999",
    "eft": "#0072B2",
    "eft-slack": "#56B4E9",
    "energy-greedy": "#E69F00",
    "seas": "#009E73",
    "seas-eps": NAVY,
}
ORDER = ["fifo-ff", "eft", "eft-slack", "energy-greedy", "seas", "seas-eps"]
LABEL = {
    "fifo-ff": "FIFO-FF",
    "eft": "EFT",
    "eft-slack": "EFT-slack",
    "energy-greedy": "Energy-greedy",
    "seas": "seas",
    "seas-eps": "seas-ε",
}
TYPE_COL = {
    "prep": "#CC79A7",
    "infer_small": "#56B4E9",
    "infer_large": "#0072B2",
    "finetune": "#D55E00",
    "pipe_stage": "#F0E442",
}


def style(base: float = 20.0) -> None:
    plt.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "path",
            "font.family": "sans-serif",
            "font.sans-serif": ["Liberation Sans", "Arial", "DejaVu Sans"],
            "font.size": base,
            "axes.titlesize": base,
            "axes.labelsize": base,
            "xtick.labelsize": base - 2,
            "ytick.labelsize": base - 2,
            "legend.fontsize": base - 2,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": TEXT,
            "axes.labelcolor": TEXT,
            "text.color": TEXT,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "axes.linewidth": 1.2,
            "lines.linewidth": 2.4,
            "mathtext.fontset": "dejavusans",
        }
    )


def save(fig: Figure, out: Path, name: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.pdf", out / f"{name}.svg"]
    for p in paths:
        fig.savefig(
            p,
            bbox_inches=None,
            metadata={"Creator": "seas viz", "CreationDate": None}
            if p.suffix == ".pdf"
            else {"Creator": "seas viz", "Date": None},
        )
    plt.close(fig)
    return paths


def _runs(root: Path, sc: str) -> pd.DataFrame:
    return add_common_idle(pd.read_csv(root / sc / "runs.csv"))


def _ci_bar(ax: Any, x: float, vals: np.ndarray, color: str, width: float = 0.72, scale: float = 1.0) -> None:
    m = float(np.mean(vals)) * scale
    lo, hi = bootstrap_ci(vals * scale)
    ax.bar(x, m, width=width, color=color, edgecolor="none")
    ax.errorbar(x, m, yerr=[[m - lo], [hi - m]], fmt="none", ecolor=TEXT, capsize=6, lw=1.8)


def fig_s1_energy_miss(root: Path, out: Path) -> list[Path]:
    """Figure B (S1, confirmatory): deadline-miss rate per policy (mean, 95 % bootstrap CI) and
    modelled dynamic energy relative to EFT, paired per seed (dots = seeds, diamond = mean, 95 % CI).
    FIFO-FF is far off the energy scale; its paired mean is printed instead of plotted."""
    style(22)
    df = _runs(root, "S1")
    df = df[df.point == "base"]
    pols = [p for p in ORDER if p in set(df.policy_spec)]
    fig, axes = plt.subplots(1, 2, figsize=(296 * MM, 150 * MM), gridspec_kw={"width_ratios": [1.0, 1.25]})
    fig.subplots_adjust(left=0.085, right=0.985, bottom=0.25, top=0.86, wspace=0.42)
    for i, p in enumerate(pols):
        g = df[df.policy_spec == p].sort_values("seed")
        _ci_bar(axes[0], i, g.miss_rate.to_numpy(), COL[p], scale=100)
    axes[0].set_xticks(range(len(pols)), [LABEL[p] for p in pols], rotation=35, ha="right")
    axes[0].set_ylabel("Missed deadlines (%)")
    axes[0].set_title("Missed deadlines", loc="left", fontweight="bold", color=NAVY)
    rel_pols = [p for p in ["eft-slack", "energy-greedy", "seas", "seas-eps"] if p in set(df.policy_spec)][::-1]
    ax = axes[1]
    for i, p in enumerate(rel_pols):
        rel = paired_rel(df, "base", p, "eft", "energy_dyn_J") * 100
        rng = np.random.default_rng(i)
        ax.scatter(rel, i + rng.uniform(-0.2, 0.2, rel.size), s=26, color=COL[p], alpha=0.6, edgecolors="none")
        lo, hi = bootstrap_ci(rel)
        m = float(rel.mean())
        ax.errorbar(m, i, xerr=[[m - lo], [hi - m]], fmt="D", color=TEXT, ms=10, capsize=7, lw=2.2)
    ax.axvline(0, color=COL["eft"], lw=1.8, ls="--")
    ax.text(0.2, len(rel_pols) - 0.3, "EFT", color=COL["eft"], fontsize=18, va="bottom", ha="left")
    ax.set_yticks(range(len(rel_pols)), [LABEL[p] for p in rel_pols])
    ax.set_ylim(-0.6, len(rel_pols) + 0.1)
    ax.set_xlabel("vs EFT (%, paired by seed)")
    ax.set_title("Modelled dynamic energy", loc="left", fontweight="bold", color=NAVY)
    if "fifo-ff" in pols:
        f = paired_rel(df, "base", "fifo-ff", "eft", "energy_dyn_J").mean() * 100
        ax.text(
            1.0,
            -0.33,
            f"FIFO-FF: {f:+.0f} % (off scale)",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=17,
            color=GREY,
        )
    return save(fig, out, "figB_S1_energy_miss")


def fig_energy_budget(root: Path, out: Path) -> list[Path]:
    """Where seas's modelled energy goes (S1 mean over seeds): the dynamic-energy floor that any
    placement must pay (relaxation bound for the jobs seas completed), the part placement can still
    change (seas above that floor), idle power while nodes run jobs, and idle power while nodes
    are empty (avoidable only by power-state control; ideal gating, no wake-up cost)."""
    style(21)
    g = _runs(root, "S1")
    g = g[(g.point == "base") & (g.policy_spec == "seas")]
    floor = g.energy_lb_J.mean() / 1e3
    head = (g.energy_dyn_J - g.energy_lb_J).mean() / 1e3
    busy = g.energy_idle_busy_J.mean() / 1e3
    empty = (g.energy_idle_window_J - g.energy_idle_busy_J).mean() / 1e3
    tot = floor + head + busy + empty
    segs = [
        (floor, "#9DB3CF", "Dynamic-energy floor\n(unavoidable for this work)"),
        (head, COL["seas"], "Remaining placement headroom"),
        (busy, "#C9D3DF", "Idle while\nbusy"),
        (empty, "#E69F00", "Idle while empty\n(power-state lever)"),
    ]
    fig, ax = plt.subplots(figsize=(222 * MM, 108 * MM))
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.03, top=0.97)
    x = 0.0
    for v, c, _ in segs:
        ax.barh(0, v, left=x, height=0.62, color=c, edgecolor="white", lw=2)
        x += v
    ax.set_xlim(0, tot)
    ax.set_ylim(-1.45, 1.3)
    ax.axis("off")
    x = 0.0
    for k, (v, _c, lab) in enumerate(segs):
        mid = x + v / 2
        pct = v / tot * 100
        val = f"{pct:.1f} %" if pct < 1 else f"{pct:.0f} %"
        if k == 1:
            ax.annotate(
                f"{lab}: ≤ {val} of total",
                xy=(x + v / 2, 0.3),
                xytext=(tot * 0.12, 1.0),
                fontsize=21,
                fontweight="bold",
                color=COL["seas"],
                va="center",
                ha="left",
                arrowprops={"arrowstyle": "-", "color": COL["seas"], "lw": 2},
            )
        else:
            ax.text(mid, 0, val, ha="center", va="center", fontsize=26, fontweight="bold", color=TEXT)
            ax.text(mid, -0.45, lab, ha="center", va="top", fontsize=19, color=TEXT, linespacing=1.1)
        x += v
    return save(fig, out, "figE_energy_budget")


def fig_s1_rel_energy(root: Path, out: Path) -> list[Path]:
    """Paired relative dynamic energy vs EFT (S1), per seed + mean with 95% CI."""
    style(21)
    df = _runs(root, "S1")
    pols = [p for p in ["eft-slack", "energy-greedy", "seas", "seas-eps"] if p in set(df.policy_spec)]
    fig, ax = plt.subplots(figsize=(290 * MM, 95 * MM))
    fig.subplots_adjust(left=0.2, right=0.98, bottom=0.24, top=0.95)
    for i, p in enumerate(pols):
        rel = paired_rel(df, "base", p, "eft", "energy_dyn_J") * 100
        rng = np.random.default_rng(i)
        ax.scatter(rel, i + rng.uniform(-0.18, 0.18, rel.size), s=22, color=COL[p], alpha=0.55, edgecolors="none")
        lo, hi = bootstrap_ci(rel)
        ax.errorbar(
            rel.mean(), i, xerr=[[rel.mean() - lo], [hi - rel.mean()]], fmt="D", color=TEXT, ms=9, capsize=6, lw=2
        )
    ax.axvline(0, color=GREY, lw=1.4, ls="--")
    ax.set_yticks(range(len(pols)), [LABEL[p] for p in pols])
    ax.set_xlabel("Dynamic energy relative to EFT (%, modelled; paired per seed)")
    return save(fig, out, "figB2_S1_rel_energy")


def fig_s4_gain(root: Path, out: Path, conf: dict[str, Any]) -> list[Path]:
    style(21)
    h2 = conf["H2"]
    x = np.array(h2["levels"]) * 100
    m = np.array(h2["mean_gain_by_level"]) * 100
    ci = np.array(h2["gain_ci_by_level"]) * 100
    fig, ax = plt.subplots(figsize=(180 * MM, 140 * MM))
    fig.subplots_adjust(left=0.21, right=0.97, bottom=0.2, top=0.95)
    ax.fill_between(x, ci[:, 0], ci[:, 1], color=COL["seas"], alpha=0.22, lw=0)
    ax.plot(x, m, "-o", color=COL["seas"], ms=9)
    ax.axhline(0, color=GREY, lw=1.4, ls="--")
    ax.set_xlabel("Jobs with security requirements (%)")
    ax.set_ylabel("Energy saved vs EFT (%)")
    return save(fig, out, "figS4_gain_vs_security")


def fig_s7_robustness(root: Path, out: Path) -> list[Path]:
    """S7 (confirmatory H3): paired energy relative to EFT and miss rate vs estimation error."""
    style(20)
    df = _runs(root, "S7")
    pts = sorted(df.point.unique(), key=lambda s: float(s.split("=")[1]))
    sig = np.array([float(s.split("=")[1]) for s in pts])
    fig, axes = plt.subplots(1, 2, figsize=(290 * MM, 105 * MM))
    fig.subplots_adjust(left=0.115, right=0.99, bottom=0.2, top=0.95, wspace=0.34)
    for k, p in enumerate(["energy-greedy", "seas"]):
        ms, lo, hi = [], [], []
        for pt in pts:
            r = paired_rel(df, pt, p, "eft", "energy_dyn_J") * 100
            ms.append(r.mean())
            a, b = bootstrap_ci(r)
            lo.append(a)
            hi.append(b)
        off = (k - 0.5) * 0.012
        axes[0].errorbar(
            sig + off,
            ms,
            yerr=[np.subtract(ms, lo), np.subtract(hi, ms)],
            fmt="-o",
            color=COL[p],
            capsize=5,
            ms=8,
            label=LABEL[p],
        )
    axes[0].axhline(0, color=COL["eft"], lw=1.6, ls="--")
    axes[0].text(sig[0], 0.25, "EFT = 0", color=COL["eft"], ha="left", va="bottom", fontsize=16)
    for p in ["eft", "energy-greedy", "seas"]:
        ms, lo, hi = [], [], []
        for pt in pts:
            v = df[(df.point == pt) & (df.policy_spec == p)].sort_values("seed").miss_rate.to_numpy() * 100
            ms.append(v.mean())
            a, b = bootstrap_ci(v)
            lo.append(a)
            hi.append(b)
        axes[1].fill_between(sig, lo, hi, color=COL[p], alpha=0.18, lw=0)
        axes[1].plot(sig, ms, "-o", color=COL[p], label=LABEL[p], ms=8)
    axes[0].set_ylabel("Energy vs EFT (%, modelled)")
    axes[1].set_ylabel("Deadline-miss rate (%)")
    for ax in axes:
        ax.set_xlabel("Estimation error σ")
        ax.set_xticks(sig)
    axes[1].legend(frameon=False, loc="upper left", fontsize=16)
    axes[0].legend(frameon=False, loc="lower left", fontsize=16)
    return save(fig, out, "figS7_robustness")


def fig_s2_tradeoff(root: Path, out: Path) -> list[Path]:
    """Exploratory S2: energy vs deadline-miss rate for the alpha / epsilon sweeps (2-D 95% CIs).
    Configurations with identical outcomes are merged into one labelled marker."""
    style(19)
    df = _runs(root, "S2")
    fig, ax = plt.subplots(figsize=(205 * MM, 125 * MM))
    fig.subplots_adjust(left=0.2, right=0.98, bottom=0.17, top=0.96)
    pts: dict[tuple[float, float], list[str]] = {}
    stats_: dict[str, tuple[float, float, tuple[float, float], tuple[float, float]]] = {}
    for spec in [x for x in df.policy_spec.unique() if x != "fifo-ff"]:
        g = df[df.policy_spec == spec].sort_values("seed")
        x = g.miss_rate.to_numpy() * 100
        y = paired_rel(df, "base", spec, "eft", "energy_dyn_J") * 100
        stats_[spec] = (x.mean(), y.mean(), bootstrap_ci(x), bootstrap_ci(y))
        pts.setdefault((round(x.mean() * 4) / 4, round(y.mean() * 4) / 4), []).append(spec)
    for (_, _), specs in pts.items():
        spec = specs[0]
        xm, ym, (xl, xh), (yl, yh) = stats_[spec]
        base = spec.split("(")[0]
        col = COL.get(base, GREY)
        marker = "o" if base.startswith("seas") else "s"
        ax.errorbar(
            xm,
            ym,
            xerr=[[xm - xl], [xh - xm]],
            yerr=[[ym - yl], [yh - ym]],
            fmt=marker,
            color=col,
            ms=10,
            capsize=4,
            lw=1.4,
        )
        labels = []
        for sp in specs:
            if "(" in sp:
                k, v = sp.split("(")[1].rstrip(")").split("=")
                labels.append(("α" if k == "alpha" else "ε") + "=" + v)
            else:
                labels.append(LABEL[sp])
        ax.annotate(
            "\n".join(", ".join(labels[i : i + 3]) for i in range(0, len(labels), 3)),
            (xm, ym),
            textcoords="offset points",
            xytext=(12, -6),
            fontsize=13,
            color=col,
            va="top",
        )
    ax.set_xlim(0, None)
    ax.axhline(0, color=GREY, lw=1.2, ls="--")
    ax.set_xlabel("Deadline-miss rate (%)")
    ax.set_ylabel("Energy vs EFT (%, modelled, paired)")
    return save(fig, out, "figD_S2_tradeoff")


def _lanes(starts_ends: list[tuple[float, float, str]], capacity: int) -> dict[str, int]:
    free = [0.0] * capacity
    lane: dict[str, int] = {}
    for s, e, jid in sorted(starts_ends):
        k = next((i for i, f in enumerate(free) if f <= s + 1e-9), int(np.argmin(free)))
        lane[jid] = k
        free[k] = e
    return lane


def fig_gantt(root: Path, out: Path, window: float = 300.0) -> list[Path]:
    """Figure F: S1 seed 0, EFT vs seas, first `window` seconds. Hatched = requires TEE (simulated)."""
    style(17)
    cl = load_cluster("configs/clusters/C-B.yaml")
    fig, axes = plt.subplots(2, 1, figsize=(290 * MM, 175 * MM), sharex=True)
    fig.subplots_adjust(left=0.13, right=0.99, bottom=0.17, top=0.95, hspace=0.25)
    for ax, pol in zip(axes, ["eft", "seas"], strict=True):
        ev = [json.loads(x) for x in (root / "S1" / "base" / pol / "seed_0" / "events.jsonl").read_text().splitlines()]
        starts = [e for e in ev if e["type"] == "START"]
        ylabels, y = [], 0.0
        for node in cl.nodes:
            lh = 1.5 if node.cls.value == "GPU" else 0.55
            ss = [(e["t"], e["end"], e["job"]) for e in starts if e["node"] == node.id]
            lane = _lanes(ss, node.capacity)
            for e in [x for x in starts if x["node"] == node.id]:
                if e["t"] > window:
                    continue
                yy = y + lane[e["job"]] * lh
                tee = any(r in ("TEE_CPU", "TEE_GPU") for r in e["req"])
                jtype = _job_type_lookup(root, pol, e["job"])
                ax.add_patch(
                    Rectangle(
                        (e["t"], yy + 0.08 * lh),
                        min(e["end"], window) - e["t"],
                        0.84 * lh,
                        facecolor=TYPE_COL[jtype],
                        edgecolor=TEXT,
                        lw=0.4,
                        hatch="////" if tee else None,
                    )
                )
            ylabels.append((y + node.capacity * lh / 2, node.id))
            y += node.capacity * lh
            ax.axhline(y, color=GREY, lw=0.6)
        ax.set_ylim(0, y)
        ax.set_yticks([p for p, _ in ylabels], [n for _, n in ylabels], fontsize=13)
        ax.set_title(LABEL[pol], loc="left", fontweight="bold", color=NAVY, fontsize=18)
        ax.set_xlim(0, window)
        ax.invert_yaxis()
    axes[1].set_xlabel("Simulated time (s)")
    handles = [Patch(facecolor=c, edgecolor=TEXT, lw=0.4, label=t) for t, c in TYPE_COL.items()]
    handles.append(Patch(facecolor="white", edgecolor=TEXT, hatch="////", label="needs TEE (simulated)"))
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=6,
        frameon=False,
        fontsize=13,
        bbox_to_anchor=(0.55, 0.0),
        handlelength=1.4,
        columnspacing=1.0,
    )
    return save(fig, out, "figF_S1_gantt_seed0")


_TYPE_CACHE: dict[tuple[str, str], dict[str, str]] = {}


def _job_type_lookup(root: Path, pol: str, jid: str) -> str:
    key = (str(root), pol)
    if key not in _TYPE_CACHE:
        d = {}
        for line in (root / "S1" / "base" / pol / "seed_0" / "decisions.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r["action"] == "PLACE":
                d[r["job"]] = r["type"]
        _TYPE_CACHE[key] = d
    return _TYPE_CACHE[key][jid]


def pick_explanation(root: Path) -> dict[str, Any]:
    """Deterministically pick an illustrative seas decision: a TEE_CPU job for which an ineligible
    node (no TEE) would have been faster, with at least two eligible candidates."""
    cl = load_cluster("configs/clusters/C-B.yaml")
    for line in (root / "S1" / "base" / "seas" / "seed_0" / "decisions.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["action"] != "PLACE" or "TEE_CPU" not in r["required"] or not r["ineligible"]:
            continue
        if r["type"] not in ("infer_small", "pipe_stage") or len(r["candidates"]) < 3:
            continue
        chosen = next(c for c in r["candidates"] if c["chosen"])
        others = [c for c in r["candidates"] if not c["chosen"]]
        if not any(c["node"].startswith("cpu") for c in others) or chosen["est"] > r["t"] + 1e-9:
            continue
        # Hypothetical estimates on the ineligible node(s), as if the job ran there unprotected.
        job = Job(
            id=r["job"],
            type=JobType(r["type"]),
            work=r["work"],
            memory_gb=r["memory_gb"],
            release=0,
            deadline=1,
            required=frozenset(),
            data_gb=r["data_gb"],
        )
        inel = []
        for nid in r["ineligible"]:
            n = cl.node(nid)
            inel.append(
                {
                    "node": nid,
                    "T": exec_time(job, n, cl),
                    "E": dyn_energy(job, n),
                    "missing": sorted(set(r["required"]) - {c.value for c in n.capabilities}),
                }
            )
        r["ineligible_detail"] = inel
        out: dict[str, Any] = r
        return out
    raise RuntimeError("no illustrative decision found")


def fig_explanation(root: Path, out: Path) -> tuple[list[Path], dict[str, Any]]:
    """Figure C: one real decision record of seas (S1, seed 0)."""
    style(21)
    r = pick_explanation(root)
    rows = [("ineligible", c) for c in r["ineligible_detail"]] + [("eligible", c) for c in r["candidates"]]
    fig, ax = plt.subplots(figsize=(222 * MM, 132 * MM))
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.99)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch((1, 76), 98, 21, boxstyle="round,pad=0.4,rounding_size=2", fc="#EEF2F7", ec=NAVY, lw=1.6)
    )
    req = ", ".join(c for c in r["required"] if c.startswith("TEE")) or "none"
    ax.text(
        3,
        91,
        f"Job {r['job']}  ·  {r['type']}  ·  requires {req}",
        fontsize=22,
        fontweight="bold",
        color=NAVY,
        va="center",
    )
    ax.text(
        3,
        82,
        f"deadline in {r['deadline'] - r['t']:.1f} s  ·  α = {r['alpha']}  ·  score = α·Ê + (1−α)·R̂",
        fontsize=20,
        va="center",
    )
    hdr_y = 70
    for x, h in ((3, "Node"), (26, "time"), (41, "energy"), (57, "decision")):
        ax.text(x, hdr_y, h, fontsize=19, fontweight="bold", color=GREY, va="center")
    y = hdr_y - 9
    for kind, c in rows:
        node = c["node"]
        if kind == "ineligible":
            ax.add_patch(Rectangle((1, y - 4.2), 98, 8.4, fc="white", ec="#C0392B", lw=1.4, ls="--"))
            verdict, col = "ineligible: no " + "+".join(m for m in c["missing"] if m.startswith("TEE")), "#C0392B"
        elif c["chosen"]:
            ax.add_patch(Rectangle((1, y - 4.2), 98, 8.4, fc="#E3F4EE", ec=COL["seas"], lw=2.2))
            verdict, col = "chosen: lowest score", COL["seas"]
        else:
            ax.add_patch(Rectangle((1, y - 4.2), 98, 8.4, fc="white", ec="#BBBBBB", lw=1.0))
            verdict = "higher score" if c["feasible"] else "misses deadline"
            col = TEXT
        ax.text(
            3, y, node, fontsize=20, va="center", fontweight="bold" if kind == "eligible" and c.get("chosen") else None
        )
        ax.text(26, y, f"{c['T']:.1f} s", fontsize=20, va="center")
        ax.text(41, y, f"{c['E']:.0f} J", fontsize=20, va="center")
        ax.text(57, y, verdict, fontsize=19, va="center", color=col)
        y -= 10
    paths = save(fig, out, "figC_decision_example")
    return paths, r


def fig_scaling(root: Path, out: Path) -> list[Path]:
    style(20)
    df = pd.read_csv(root / "scaling" / "runs.csv")
    fig, ax = plt.subplots(figsize=(205 * MM, 110 * MM))
    fig.subplots_adjust(left=0.2, right=0.97, bottom=0.2, top=0.95)
    for p in ["eft", "seas"]:
        g = df[df.policy == p].groupby("nodes")["sched_p95_us"].mean()
        ax.plot(g.index.to_numpy(), g.to_numpy(dtype=float) / 1000, "-o", color=COL[p], label=LABEL[p])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Nodes in simulated cluster")
    ax.set_ylabel("p95 decision time (ms, wall)")
    ax.legend(frameon=False)
    return save(fig, out, "figS_scaling")
