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

Secondary (not preregistered): idle energy ≈ 82 % of always-on total (total change −0.06 %); under ideal
power-gating the saving disappears (+0.2 %, CI −0.2…+0.6); seas completes 3.2 % more work, −3.6 % dynamic
energy per unit of completed work; α ≥ 0.25 gives identical schedules (the knob acts as a switch); miss
gains come from least-slack ordering (EFT-slack matches them). Scaling (exploratory): p95 decision time
≈ 0.15 ms at 6 nodes, ≈ 5 ms at 192 nodes (Python implementation; machine-dependent).

## 4. Poster

`poster/poster.pdf`: A0 portrait, one page, fully vector (0 raster images, QR included), all fonts
embedded, every number from generated macros. Layout follows the SciFig Classic/Navy specification; the
original `.pptx` was not downloadable from the build environment, so the grid, type scale and colours
were rebuilt in LaTeX (`poster/poster.tex`, editable). Logos are not included (not available).

## 5. Limitations and remaining work

* Synthetic, uncalibrated profiles; no contention model; independent non-preemptive jobs; one cluster.
* No real TEE, attestation or encryption; σ from literature/assumption.
* No exact optimisation bound (MILP deferred); only a relaxation lower bound on dynamic energy.
* The energy weight α is not a smooth control in this setting; a better-designed knob is open work.
* Scaling beyond ~200 nodes is slow in the current implementation (per-decision cost grows with
  queue length × nodes); vectorisation or indexing of candidate evaluation is needed.

Next steps that follow directly from the evidence: (1) power-state-aware placement (idle power dominates);
(2) Stage-2 calibration with RAPL/NVML so energies become measured; (3) measured TEE overhead per job
type (Stage 3a); (4) an exact small-instance bound to size the remaining headroom.
