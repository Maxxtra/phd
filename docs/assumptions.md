# Assumptions (Stage 1)

Every parameter below is a **synthetic, order-of-magnitude placeholder** chosen a priori to create a
plausible heterogeneous setting. None is a measurement. Stage 2 replaces them with calibrated,
provenance-tagged profiles.

## Hardware profiles (`configs/clusters/*.yaml`)

| Parameter | CPU node | GPU node | Rationale |
|---|---|---|---|
| slots | 4 | 2 | CPU nodes run several jobs; a GPU shared by two jobs (MIG/MPS-like) |
| memory | 128 GB | 80 GB | typical server / data-centre GPU memory |
| idle power | 60 W | 70 W | per node, excluding host for GPU (simplification) |
| per-slot dynamic power | 35–45 W | 100–210 W | increases with job intensity |
| throughput prep / infer_small / infer_large / finetune / pipe_stage (units/s/slot) | 2 / 0.8 / 0.05 / 0.02 / 1 | 2.5 / 20 / 4 / 1.5 / 8 | GPU ≈ CPU for preprocessing; 25–80× faster for neural compute |
| σ (protected slowdown) | 1.10 | 1.07 | GPU from the upper end of the 3–7 % throughput overhead measured for H100 CC LLM inference (Zhu et al. 2024); CPU is an assumption |

Consequences: per unit of work, CPUs are the energy-cheaper choice only for `prep`; GPUs are cheaper
and faster for all neural job types. The energy leverage of placement therefore comes from
(i) keeping preprocessing off GPUs and (ii) avoiding slow CPU execution of neural jobs.

## Power model

* Additive per-slot power, **no contention** between co-located jobs (optimistic for shared memory
  bandwidth and GPU sharing).
* Data staging occupies the slot but adds no node power.
* Idle power: always-on (reported over the common horizon; identical across policies) or ideal
  power gating with zero wake-up cost (exploratory, optimistic bound).

## Workload (`configs/workloads/baseline-mix.yaml`)

* Poisson arrivals, λ = 0.26155 /s set a priori (GPU-pool offered load 0.70); 200 jobs per run.
* Type mix 25/35/15/10/15 % (prep / infer_small / infer_large / finetune / pipe_stage).
* Log-normal work sizes and staged data volumes per type.
* Deadline = release + 10 s + U(1.5, 4) × fastest eligible execution time.
* 50 % of jobs have security requirements: of those 20 % encryption-only, 60 % CPU confidential VM,
  20 % confidential GPU + attestation.
* α = 0.5 for all jobs unless swept.
* Jobs are independent; pipeline stages are modelled as independent jobs.

## Simulation

* Estimates are exact except in S7 (multiplicative error on compute time, floor −50 %).
* Single cluster, single bandwidth figure for staging, no network topology.
* No failures, preemption, migration or reservations.
