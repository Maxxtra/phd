# Methodology decisions (Stage 1)

This document records where the Stage‑1 implementation deliberately departs from the
original handoff blueprint, and why. It was written **before** any confirmatory
experiment was run. Each decision is referenced by its ID (MD‑n) in code comments,
`docs/preregistration.md` and the README.

---

## MD‑1 Non-inferiority is tested as non-inferiority, not as a one-sided Wilcoxon test

**Problem in the blueprint.** H1 required `seas` to be "non-inferior" to EFT on
deadline-miss rate, but specified a one-sided Wilcoxon signed-rank test of
`seas ≤ eft`. Failing to reject `seas > eft` is not evidence of non-inferiority, and a
test whose null is "no difference" cannot establish it.

**Decision.** Let `d_i = miss(seas, seed i) − miss(eft, seed i)` (paired by seed, the
two policies see the identical job stream). With a pre-specified margin `δ = 0.02`
(two percentage points of deadline-miss rate):

* H0_NI: `E[d] ≥ δ`  vs  H1_NI: `E[d] < δ`.
* **Primary decision:** one-sided paired t-test on `d_i − δ` at α = 0.05, equivalently
  the upper bound of the one-sided 95 % confidence interval of `E[d]` lies below `δ`.
  With n = 30 paired seeds the t-procedure is justified by the CLT; it is reported
  together with its CI.
* **Sensitivity analyses (reported, not decisive):** (i) percentile bootstrap upper
  95 % bound of `E[d]` (10 000 resamples), (ii) Wilcoxon signed-rank test on `d_i − δ`
  (alternative: less), which tests a location shift under a symmetry assumption.
* The margin `δ = 0.02` is fixed here, before data, as the largest increase in missed
  deadlines we consider operationally acceptable for an energy-oriented policy.

H1 is an **intersection–union** hypothesis (energy superiority **and** miss-rate
non-inferiority); its p-value is the maximum of the two component p-values, which
controls the type-I error of H1 without further correction.

## MD‑2 No outcome-dependent tuning; confirmatory and exploratory are separated

**Problem in the blueprint.** The protocol said to "raise load until energy-greedy
misses deadlines" (H4) and to tune the arrival rate by running EFT. Both make the
scenario depend on observed outcomes of the policies being compared.

**Decision.**

1. The arrival rate is set **a priori** from workload and cluster parameters only
   (`seas offered-load`, no scheduling policy is executed): λ is chosen so that the
   offered load on the GPU pool equals 0.70 when every job runs on its fastest
   eligible node. The value is written into the frozen scenario files.
2. **Confirmatory scenarios** S1 (H1, H4), S4 (H2) and S7 (H3) are frozen in
   `configs/scenarios/` and hashed in `docs/preregistration.md` before their first run.
   Seeds 0–29 are reserved for them. Development and debugging use seeds ≥ 1000 only.
3. H4 is reported as observed. If energy-greedy does not miss more deadlines, we
   report that deadlines were not binding in S1; the scenario is **not** re-tuned.
4. Everything else (α/ε sweep S2, deadline-pressure S3, hardware S5, infeasibility
   S6, consolidation S8, load sweep E‑load, scaling) is **exploratory**: labelled as
   such in file names, tables and figure captions, and never used to support a
   confirmatory claim.
5. Negative and null findings are reported with the same prominence as positive ones,
   on the poster and in the README.

## MD‑3 Simulated security eligibility ≠ confidential execution

**Problem.** The blueprint used names like `TEE_CPU` and a metric
`security_violations`, which can be read as if confidential execution happened.

**Decision.** The simulator models **declared security capabilities** of nodes and
**required capabilities** of jobs, and enforces the set-inclusion rule
`R_j ⊆ C_n` at placement. Nothing is encrypted, no enclave is created, no attestation
is verified. Consequently:

* the metric is named `eligibility_violations` (placements on a node that does not
  declare the required capabilities) and is asserted to be 0;
* the protected-execution slowdown `σ_n` is a **modelled parameter** (GPU 1.07 taken
  from the upper end of a published H100 confidential-computing throughput
  measurement [Zhu et al. 2024]; CPU 1.10 is an assumption), not a measurement;
* capability semantics are documented explicitly: `TEE_CPU` = job must run inside a
  CPU confidential VM/enclave; `TEE_GPU` = job's GPU memory must be protected by GPU
  confidential computing. A confidential-GPU node runs inside a confidential VM and
  therefore declares both;
* every text that mentions TEEs says "modelled/simulated eligibility"; real TEE
  execution is Stage 3 work.

## MD‑4 Energy accounting audit

Choices and their consequences, all stated in `docs/assumptions.md`:

1. **Additive slot model.** A node has `c_n` slots. Each running job adds
   `ΔP_{n,τ} = P^load_{n,τ} − P^idle_n` while it computes. Power is additive across
   slots and co-located jobs do not slow each other down (**no contention model**).
   This is optimistic for CPUs with shared memory bandwidth and for GPU sharing;
   Stage 2 calibration is required to quantify it.
2. **Dynamic energy** is the primary energy metric:
   `E_dyn = Σ_j ΔP_{n(j),τ_j} · t^compute_j`, where `t^compute_j` is the *actual*
   compute time (with estimation noise in S7). Data staging time occupies the slot
   but is assumed to draw no incremental node power (staging is network-bound).
3. **Idle energy depends on the power-management regime**, and naive per-policy idle
   accounting is biased: charging idle power over each policy's own makespan
   penalises a policy for finishing later even though the machines would be powered
   anyway. We therefore report:
   * `E_idle_window` — always-on regime: `Σ_n P^idle_n × W`, with `W` the **service
     window** of the job stream (first release to last deadline; extended to a policy's
     own makespan if it finishes later). The window depends only on the workload, so the
     term is identical for every policy that finishes within it. *(Originally the
     latest completion over all policies — see MD‑7 for why this was corrected.)*
   * `E_idle_busy` — idealised power-gating regime (exploratory S8): idle power only
     while a node has at least one running job, with zero wake-up cost. This is an
     optimistic bound and is labelled as such.
4. **Dropped work is not "saved energy".** A policy that lets jobs expire spends less
   energy. Energy claims are therefore only made jointly with the miss-rate
   non-inferiority test (MD‑1), and we also report energy per unit of completed work.
5. **Estimates vs actuals.** Policies see estimated times/energies; the simulator
   charges actual times. Without noise (S1, S4) they coincide; S7 separates them.
6. All energy values are **modelled** from synthetic profiles; figure axes say so.

## MD‑5 Formal model vs simulator semantics

The handoff stated an offline MILP-style formulation and an online simulator as if
they were the same problem. They are not. The implementation follows these precise
semantics, and `docs/model.md` presents the formal model with this distinction:

* **Online, non-clairvoyant about arrivals, non-preemptive.** Decisions are taken
  only at event times (arrival or completion). No job can be paused or migrated.
* **No reservations.** A policy may decide that a waiting job should wait for a busy
  node; nothing is reserved, and the decision is re-taken at the next event.
* **Sequential greedy decisions within an event.** Jobs are processed in the policy's
  order; cluster state (free slots, free memory, predicted free times) is updated after
  each placement before the next job is considered.
* **Uniform expiry rule (engine, all policies).** At every event, a waiting job whose
  deadline cannot be met even if started immediately on its fastest eligible node is
  dropped with reason `DEADLINE_EXPIRED_WHILE_WAITING`. A started job always runs to
  completion; it is "late" if it finishes after its deadline.
* **Deadline-miss rate** = (late + expired) / (submitted − ineligible-rejected).
  Jobs with no eligible node (`NO_ELIGIBLE_NODE_SECURITY`, `..._MEMORY`) are rejected at
  arrival by the engine for every policy and reported separately.
* **The per-job scalarised objective is not the system objective.** `seas` minimises,
  per decision, `α·Ê + (1−α)·R̂` where `Ê` is the job's energy on a node normalised by
  its minimum over eligible nodes and `R̂` is its predicted *response time*
  (wait + execution) normalised by the minimum over deadline-feasible nodes. This
  is a greedy heuristic; it carries no optimality guarantee for total energy or
  makespan. The blueprint's normalised *execution* time ignored queueing delay; using
  response time is necessary because, online, a fast but busy node is not fast.
* **Lower bound.** We report, per policy, a relaxation bound `E_LB = Σ_{j completed by that policy} min_{n eligible} E_jn`
  only as a descriptive reference for dynamic energy (it ignores capacity and
  deadlines). No exact MILP is solved in Stage 1; the blueprint's optional
  `milp-bound` is deferred and not claimed.
* Per-job energy budgets from the blueprint are **not implemented** in Stage 1; the
  user-facing energy control is the per-job weight α.

## MD‑6 References and claims

* The broad novelty sentence ("no existing system integrates CPU/GPU/QPU placement,
  security by construction, verification, fault tolerance, continual-learning-aware
  scheduling and energy accountability") is a statement about the *research
  programme* and is not presented as an established gap.
* The only Stage‑1 gap claim, worded as "to our knowledge", is that the surveyed
  energy-aware schedulers do not treat security-capability eligibility as a
  constraint inside the energy-aware placement decision with per-decision
  explanations. It is falsifiable by one counter-example and is not printed in bold.
* Performance claims are restricted to "modelled dynamic energy in simulation under
  identical constraints". No percentage from the literature is reused as a claim about
  this system.
* Reference metadata was checked on 2026‑10‑23; entries whose page ranges or venues
  could not be re-confirmed are given with their arXiv identifier and the confirmed
  venue only (see `docs/references.bib`).

## MD‑7 Audit correction: idle-energy window (post-hoc, 2026‑10‑23)

An independent re-computation during the pre-presentation audit found that the
"common horizon" of MD‑4 (latest completion over *all* policies) was set by the FIFO
baseline, whose backlog runs ≈ 2.8× longer than the service window. This inflated the
always-on idle term for every policy and made dynamic energy look like only ≈ 18 % of
the total (the earlier "idle ≈ 82 %" statement). The horizon is now the service window
(first release to last deadline, mean 947 s in S1); `seas`, EFT, EFT-slack and
energy-greedy always finish inside it. Under this accounting dynamic energy is ≈ 51 %
of `seas`'s always-on total, and the total-energy difference vs EFT is −0.28 %
(CI −0.53 … −0.00).

What did **not** change: simulator, policies, workloads, seeds, confirmatory configs
(hashes unchanged) and the preregistered primary metric (dynamic energy). H1–H3 are
unaffected because they are tested on dynamic energy and miss rate. All 4,380 runs were
re-executed after the fix and their event traces are bit-identical to the confirmatory
runs at `dc30ad3`; only the derived `service_window_s` column and the secondary
accounting changed. The per-policy own-makespan variant gives the same picture
(dynamic share 54 %, total −0.21 %).

The same audit also tightened two wordings: the α sweep yields *identical schedules in
27 of 30 seeds* (energy within 0.01 %), not identical schedules everywhere; and the
miss-rate reduction vs EFT is attributed to least-slack-first ordering (the `eft-slack`
ablation reaches the same 3.7 %), while the energy term contributes −1.6 % vs that
ordering.
