# Stage-1 implementation report

Repository: https://github.com/Maxxtra/phd · commits `86cd5b5` (preregistration) → `dc30ad3`
(implementation; all confirmatory runs) → `38bb2b2` (analysis/figures) → `31a5905` (results, poster).

## 1. Corrections made to the blueprint before implementation

| Issue | Resolution (details: `methodology_decisions.md`) |
|---|---|
| One-sided Wilcoxon presented as a non-inferiority test | MD-1: paired one-sided *t*-test of `mean(miss_seas − miss_eft) < δ = 2 pp` (≡ upper 95 % bound < δ); bootstrap and shifted-Wilcoxon as sensitivity; H1 as intersection–union test |
| Workload tuning to make H4 pass | MD-2: arrival rate set a priori from workload/cluster only; confirmatory configs hashed and committed before runs; seeds 0–29 reserved; exploratory scenarios labelled; negative results reported |
| "TEE" wording implied execution | MD-3: simulated capability eligibility; metric renamed `eligibility_violations`; σ is a modelled parameter |
| Energy accounting | MD-4: dynamic energy primary; idle reported on a common horizon (always-on) and under ideal power-gating; dropped work not counted as savings; energy per completed work reported |
| Formal model ≠ simulator | MD-5: online, non-preemptive, no reservations, uniform expiry rule; seas uses *response time* (not execution time) in its latency term; offline problem stated as reference only |
| Unsupported novelty/performance claims | MD-6: full-vision gap framed as programme; narrow, falsifiable Stage-1 claim; no literature percentages reused as claims |

## 2. What was built

`seas` package (Python ≥ 3.11, pydantic, numpy/pandas/scipy, matplotlib, typer): models, estimators,
deterministic DES engine, six policies (`fifo-ff`, `eft`, `eft-slack` ablation, `energy-greedy`, `seas`,
`seas-ε`), explainable decision records, CRN workload generator, experiment runner, statistics,
verification gates, figure generation, report/macro generation, CLI. 25 tests (exhaustive eligibility
truth table, analytic estimator checks, hand-built policy scenarios, 40 property-based random
configurations × 6 policies with independent trace replay, statistics known-answer tests, CLI smoke).
`ruff` and `mypy --strict` clean. GitHub Actions CI re-runs S1 and compares trace hashes with the
committed results.

## 3. Evidence produced

4,380 simulated runs over eight scenarios (+ 24 scaling runs). All pass: 0 eligibility violations,
capacity/memory never exceeded (trace replay), job conservation, preregistration hashes, deterministic
re-runs (also checked on a simulated fresh clone).

| Hypothesis | Result |
|---|---|
| H1 energy superiority + miss non-inferiority vs EFT | supported, Holm p = 0.040; −0.6 % [−1.1, −0.1]; misses 7.8 % → 3.7 % |
| H2 gain increases with security share | **not supported; opposite direction** (1.4 % → 0.2 %) |
| H3 robustness to ±25 % estimation error | supported, Holm p = 0.002 |
| H4 deadlines binding | yes (energy-greedy +11.5 pp misses, −4.8 % energy) |

Secondary (not preregistered; accounting corrected in audit, MD-7): with always-on nodes over the
service window, dynamic energy is ≈ 51 % of seas's total and the total changes by −0.28 % [−0.53, −0.00];
under ideal power gating the saving disappears (+0.17 %, CI −0.24…+0.62). seas is 0.4 % above the
relaxation floor for the jobs it completes (EFT 2.4 %), i.e. ≈ 0.2 % of total energy (mean; worst seed 0.7 %) is left for placement in this model,
while idle power on empty nodes is ≈ 36 %. seas completes 3.2 % more work, −3.6 % dynamic energy per unit of
completed work. α ∈ {0.25 … 1} gives identical schedules in 27 of 30 seeds (energy within 0.01 %). The miss
reduction comes from least-slack ordering (EFT-slack matches it); the energy term gives −1.6 % against that
ordering. Scaling (exploratory): p95 decision time ≈ 0.15 ms at 6 nodes, ≈ 5 ms at 192 nodes (Python
implementation; machine-dependent).

## 3a. Pre-presentation audit (2026-10-23)

* Independent recomputation of all confirmatory statistics from `runs.csv` (separate script, no reuse of
  `seas.experiments.stats`) reproduced H1–H3, the ablation, H4 and the secondary comparisons.
* Found and fixed: the always-on idle horizon was set by FIFO's long backlog, inflating idle energy for
  all policies (MD-7); poster/README overstatements (α "identical schedules" — true in 27/30 seeds;
  miss gain attributed to the whole of seas rather than to least-slack ordering; "consistent across
  seeds" — seas is lower than EFT in 20/30 seeds; H2 "refuted" → not supported, opposite trend post hoc).
* All 4,380 runs re-executed after the fix; event traces bit-identical to the confirmatory runs at
  `dc30ad3`. Provenance now records `+dirty` when code differs from the recorded commit.

## 4. Poster

`poster/poster.pdf`: A0 portrait, one page, fully vector (0 raster images, QR included), all fonts
embedded, every number from generated macros. Layout follows the SciFig Classic/Navy specification; the
original `.pptx` was not downloadable from the build environment, so the grid, type scale and colours
were rebuilt in LaTeX (`poster/poster.tex`, editable). Logos are not included (not available).

## 5. Limitations and remaining work

* Synthetic, uncalibrated profiles; no contention model; independent non-preemptive jobs; one cluster.
* No real TEE, attestation or encryption; σ from literature/assumption.
* No exact optimisation bound (MILP deferred); only a relaxation lower bound on dynamic energy.
* The energy weight α is not a useful control in this setting (identical schedules in 27/30 seeds for α ≥ 0.25); a better-designed knob is open work.
* Scaling beyond ~200 nodes is slow in the current implementation (per-decision cost grows with
  queue length × nodes); vectorisation or indexing of candidate evaluation is needed.

Next steps that follow directly from the evidence: (1) power-state-aware placement (placement headroom ≈ 0.2 %, idle on empty nodes ≈ 36 %);
(2) Stage-2 calibration with RAPL/NVML so energies become measured; (3) measured TEE overhead per job
type (Stage 3a); (4) an exact small-instance bound to size the remaining headroom.

### Known weaknesses a reviewer may raise

* H1's energy result is narrow: the relative difference excludes zero (CI −1.1 … −0.1 %), but the paired
  difference in joules does not (−1.9 kJ, CI −3.7 … +0.2 kJ); seas is lower than EFT in 20 of 30 seeds.
* The miss-rate means of `seas` and `eft-slack` coincide (3.7 %), but per seed they agree in 15 of 30.
* The preregistration is time-stamped only by git history (`86cd5b5` precedes `dc30ad3`), not by an
  external registry.
