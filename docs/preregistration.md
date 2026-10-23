# Preregistration — Stage 1 confirmatory analysis

Registered: 2026-10-23, before any run with confirmatory seeds 0–29.
Policies, engine semantics and analysis plan are fixed by this document and
`docs/methodology_decisions.md` (MD-1 … MD-6).

## Frozen inputs (SHA-256)

| File | SHA-256 |
|---|---|
| configs/scenarios/S1.yaml | 4742fa256129b04574ce791602aef07b6ceb0f2b2f4fd81266c43cb63309dbb9 |
| configs/scenarios/S4.yaml | 795933cc9285bedcaf217213eb0573bfc865002ce5fef5e74d323dece68a7622 |
| configs/scenarios/S7.yaml | 33e97134a00dfd67d5e206e4c89da074b71d8a0b38705f6efb255e89ca5ea3ea |
| configs/workloads/baseline-mix.yaml | 0bb5d5eaade46620e8f912fe413b35f3a479172a72faff689322319927f1f049 |
| configs/clusters/C-B.yaml | 229984a2503aacfdfc8ab124ff41695134a0dfb0b7f9ab210b18e2a7d4ae81d4 |

`seas verify` recomputes these hashes and fails if a confirmatory result was produced
from different inputs.

## Disclosure

Before freezing, three **development** seeds (1000–1002) of the baseline mix were run on
C-B to debug the engine. The policy definitions in `seas/policies/` had been written
before those runs and were not changed afterwards. Development seeds are never used in
any reported analysis.

## Arrival rate

λ = 0.26155 jobs/s, set a priori by `seas offered-load` (GPU-pool offered load 0.70 on
C-B, fastest-eligible-node assumption, Monte-Carlo over development seeds 1000–1049;
no scheduling policy executed).

## Hypotheses, metrics and tests (α = 0.05)

All comparisons are paired by seed (identical job streams, common random numbers).
`E` = modelled dynamic energy (`energy_dyn_J`). `M` = deadline-miss rate
((late + expired) / eligible submitted).

**H1 (S1) — intersection–union.** `seas` uses less modelled dynamic energy than `eft`
**and** is non-inferior on deadline misses.
* H1a: Wilcoxon signed-rank on `E_seas − E_eft`, alternative "less" → p_a.
* H1b (non-inferiority, margin δ = 0.02): one-sided paired t-test of
  `mean(M_seas − M_eft) < δ` → p_b; decision equivalent to the upper one-sided 95 %
  bound being < δ. Sensitivity: bootstrap upper bound; Wilcoxon on `d − δ`.
* p_H1 = max(p_a, p_b).

**H2 (S4).** The relative energy gain `g = (E_eft − E_seas)/E_eft` increases with the
secure-job fraction f ∈ {0, 0.2, 0.4, 0.6, 0.8}. Per seed, OLS slope of g on f; Wilcoxon
signed-rank on the 30 slopes, alternative "greater" → p_H2. Bootstrap CI of mean slope.

**H3 (S7, σ = 0.25).** Under estimation error, (a) `seas` energy < `eft` energy
(Wilcoxon, less) and (b) `seas` miss rate < `energy-greedy` miss rate (Wilcoxon,
less). p_H3 = max(p_a, p_b). Other σ levels are reported descriptively.

**Multiplicity.** Holm correction over {p_H1, p_H2, p_H3}. All other comparisons
(vs fifo-ff, eft-slack, energy-greedy, seas-eps; other σ; exploratory scenarios) are
secondary/descriptive, Holm-corrected within their own family, with matched-pairs
rank-biserial correlation as effect size.

**H4 (S1, descriptive).** Deadlines are binding if `mean(M_greedy − M_seas) ≥ 0.05`.
Reported as observed; scenarios are **not** re-tuned if it fails.

## Reporting commitment

Every hypothesis is reported as supported or not supported with p (raw and Holm),
point estimate, CI and effect size, on the poster and in the README, regardless of
direction. The `eft-slack` ablation is reported next to H1 to separate the effect of
job ordering from the effect of the energy term.
