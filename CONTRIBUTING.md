# Contributing

Thank you for considering a contribution. This is a research codebase: correctness and reproducibility
come before features.

## Ground rules

1. **No result without a reproducible command.** Numbers in docs, papers or posters come from
   `seas analyze` / `seas report`; figures from `seas plot` and are listed in `figures/MANIFEST.md`.
2. **Confirmatory configs are frozen.** Do not edit `configs/scenarios/S1.yaml`, `S4.yaml`, `S7.yaml`,
   `configs/workloads/baseline-mix.yaml` or `configs/clusters/C-B.yaml`; `seas verify` checks their
   hashes against `docs/preregistration.md`. New ideas go into new, clearly labelled exploratory scenarios.
3. **Development seeds are ≥ 1000.** Seeds 0–29 are reserved for reported experiments.
4. **Label what is modelled, simulated or measured** — in code comments, axis labels and prose.
5. **Fair comparisons.** Policies only see eligible candidates; never add a code path that lets one
   policy bypass the engine's eligibility filter or expiry rule.

## Workflow

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy seas && pytest -q
```

* One policy = one class in `seas/policies/`, registered in `seas/policies/__init__.py`, with a unit test
  on `tests/fixtures/toy_cluster.yaml` and a paragraph in `docs/model.md`.
* Estimator changes must update the analytic tests in `tests/test_models_estimators.py`.
* Calibrated profiles go in `configs/clusters/calibrated/` with a `provenance` block
  (host, CPU/GPU model, driver, tool, date, number of runs, spread).

## Good first issues

| Area | Task |
|---|---|
| Optimisation | Exact CP-SAT bound for ≤ 40-job instances; optimality gap of `seas` |
| Power states | Policy that accounts for idle power with a wake-up cost model |
| Calibration | `benchmarks/calibrate.py` measuring throughput and power with RAPL/NVML |
| Security | Property tests for a richer capability lattice (attestation freshness) |
| Workloads | Drift-triggered retraining generator (continual learning) |
| Quantum | `QPU` node class with queue latency, shot cost and fidelity (schema only) |

Pull requests are reviewed within a week. Substantive contributions are acknowledged in releases and,
where they contribute intellectually to a paper, through co-authorship by the usual criteria.
