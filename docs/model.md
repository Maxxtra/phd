# Formal model (Stage 1)

This is the model the code implements. Where the online simulator differs from the
offline formulation, the difference is stated (see also `methodology_decisions.md`, MD‑5).

## Entities

**Jobs** `j ∈ J`: type `τ_j ∈ {prep, infer_small, infer_large, finetune, pipe_stage}`, work `w_j`,
memory `m_j`, release `r_j`, deadline `d_j`, required capabilities `R_j ⊆ 𝒞`, energy weight
`α_j ∈ [0,1]`, staged data `D_j` (GB), and (simulation only) an estimation-error factor `η_j`.

**Nodes** `n ∈ N`: class (CPU/GPU), slots `c_n`, memory `M_n`, declared capabilities `C_n ⊆ 𝒞`,
protected-execution slowdown `σ_n ≥ 1`, idle power `P^idle_n`, and per job type a per-slot
throughput `θ_{n,τ}` and per-slot loaded power `P^load_{n,τ}`.

`𝒞 = {ENC_AT_REST, ENC_IN_TRANSIT, TEE_CPU, TEE_GPU, ATTESTED}` (simulated declarations).

## Derived quantities

```
S_jn  = 1[R_j ⊆ C_n  and  m_j ≤ M_n]                     eligibility (hard)
ρ_jn  = σ_n if R_j ∩ {TEE_CPU, TEE_GPU} ≠ ∅ else 1        modelled protection slowdown
t_jn  = ρ_jn · w_j / θ_{n,τ_j}                            compute time (estimate)
T_jn  = t_jn + 8·D_j / B                                  slot-occupancy time (estimate), B = bandwidth (Gb/s)
E_jn  = (P^load_{n,τ_j} − P^idle_n) · t_jn                 dynamic energy (estimate)
actual compute time = t_jn · (1 + η_j)                    (η_j = 0 except in S7)
```

## Offline problem (reference formulation, not solved in Stage 1)

Decision variables `x_jn ∈ {0,1}`, start times `s_j`, drop indicators `z_j`.

```
minimise   Σ_j Σ_n x_jn E_jn            (total dynamic energy)
s.t.       x_jn ≤ S_jn                   (security/memory eligibility)
           Σ_n x_jn + z_j = 1            (each job placed once or dropped)
           s_j ≥ r_j,  s_j + T_jn ≤ d_j for placed jobs   (hard deadlines)
           Σ_{j running on n at t} 1 ≤ c_n,   Σ m_j ≤ M_n  ∀ n, t
           Σ_j z_j ≤ Z                   (service constraint)
```

This is NP-hard in general (it contains multiprocessor scheduling with deadlines). Stage 1 does
not solve it; it reports a simple relaxation bound `E_LB = Σ_{completed j} min_{n: S_jn=1} E_jn`
(capacity and deadlines relaxed) only as a descriptive reference.

## Online problem (what the simulator executes)

* Jobs become known at `r_j`. Decisions happen only at events (arrival, completion).
* Non-preemptive, no migration, no reservations.
* **Expiry rule (all policies):** a waiting job is dropped at event time `t` if
  `t + min_{n: S_jn=1} T_jn > d_j`.
* A started job always completes; it is *late* if it finishes after `d_j` (possible when a policy
  knowingly chooses a node that cannot meet the deadline, or under estimation error).
* Service metric: miss rate = (late + expired) / (submitted − ineligible).

## The seas decision rule

At event time `t`, waiting jobs are processed in least-slack-first order
(`d_j − t − min_n T_jn`). For job `j`, with predicted earliest start `est_jn` on each eligible node
(from estimated completions of running jobs; other waiting jobs ignored):

```
resp_jn  = est_jn − t + T_jn                 predicted response time
F_j      = { n : S_jn = 1, est_jn + T_jn ≤ d_j }
Ê_jn     = E_jn / min_{n: S_jn=1} E_jn
R̂_jn     = resp_jn / min_{n ∈ F_j} resp_jn
choose   n* = argmin_{n ∈ F_j}  α_j Ê_jn + (1 − α_j) R̂_jn      (EFT choice if F_j = ∅)
place j on n* if n* has a free slot and memory now; otherwise j waits.
```

`seas-ε` instead chooses the minimum-energy node in `F_j` whose response time is within
`(1+ε)` of the best feasible response time.

Properties: per-decision cost `O(|ready| · |N| · c)` plus a sort; no optimality guarantee for total
energy, makespan or miss rate. α is the user-facing "customize energy consumption" knob.

## What changes for later stages

TEE overhead becomes measured per job type (Stage 3a); attestation state enters `C_n` dynamically
(3b); recurring retraining jobs with staleness costs are added (4); a QPU node class with queue
latency, shot cost and fidelity is added to the same capability/cost schema (5).
