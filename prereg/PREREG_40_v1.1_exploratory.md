# PREREG_40 v1.1: exploratory appendix (Q2)

*Written 10-10-2026. **Post-TEST exploratory analysis; the predictions below are registered BEFORE this stage is run.***

**Status relative to v1**
- v1 (`PREREG_40.md`, tag `prereg-40-v1`, commit 95e4a55) is unchanged, and its H1–H7 scores stand (CP-B1, 16/18 PASS).
- This appendix adds three predictions, E1–E3, about an observation made on TEST at CP-B1: Kansal-EWMA beat blackout by a median of 0.015 in miss, which v1 §3 had listed as "reported, not predicted".
- Because the motivating observation comes from TEST, **every E-result is exploratory**. It will be labelled that way in the paper and may not be cited as confirmatory evidence.

**Freezing**
- This file is frozen by its own SHA-256 (`P1/PREREG_40_v1.1_exploratory.sha256`).
- It is committed in `D:\Repos\harvest-certified-detection` as a separate commit. The tag `prereg-40-v1` is not moved, and no new tag is created.
- Decision source: CP-B1 Q2, approved by the author on 09-10-2026. The predictions are the ones stated in the P4 prompt; the operational details in §2 were fixed by the analyst before any E-run on TEST.

## 1. Code and data

- **Module:** `code/sim40/explore_q2.py`, SHA-256 `9ded54696238762a763d0d981660e096bb913b994f2685f9eb4ffcc37c0cf923`. It is a new module; the tagged code is imported but not modified.
- **Population:** the `throttle`-stage grid on TEST, i.e. 25 cells × r ∈ {5, 15, 40} × ℓ̃ ∈ {0, 0.04} × m ∈ {0.25, 1} × the same 20 C values. Only C at which blackout periodic K = 8 has outage 0 < π < 1 is kept (the H5 population; 4,686 cells at CP-B1).
- **Policies at each C:**
  - `blackout_K8` and `kansal_ewma`, exactly as in the `throttle` stage;
  - `per_abarK`: periodic, blackout on empty storage, at a constant rate equal to the **measured** mean activation ā_K of `kansal_ewma` in the same run (ā counts outage time as rate 0);
  - `per_amax_d{0,5,10}`: periodic at ā_max(C)·(1 − δ), δ ∈ {0, 0.05, 0.10}.
- **Definition of ā_max(C):** the largest constant rate whose storage need (Corollary 1.1, fluid + (r − 1)) on the **TRAIN months of the same cell** is ≤ C, i.e. a design-time choice from past data. The TRAIN irradiance is scaled with the **TEST panel factor**, so both halves describe the same physical panel and the same C.
- **Metric:** replay miss with 100,000 real TEST events, the same metric as H5. Analytic miss is reported alongside.
- **Bootstrap:**
  - 25 cells at r = 15, ℓ̃ = 0.04, m = 0.25, C = C\*_per(8)/2 (TEST);
  - by-video bootstrap of F_D, B = 1000, seed 42, analytic miss;
  - one-sided p-value of the **wrong** sign (same rule as v1 §0, including the normal approximation when no resample has the wrong sign);
  - Holm at α = 0.05 within each family of 25 tests.

## 2. Predictions

| # | Prediction | PASS criterion (all parts must hold) |
|---|---|---|
| **E1** | At equal mean activation ā and equal C, Kansal-EWMA misses **at least as much** as periodic-ā. Reason: by Theorem 1(iii), a time-varying rate violates gaps ∈ {g, g+1}. The difference is predicted to be small | (i) Δ₁ = miss(Kansal) − miss(per_abarK) ≥ −0.005 in ≥ 90 % of the population. The tolerance 0.005 is about 3 SE of a difference of two 100k-event replays. (ii) median \|Δ₁\| < 0.03. (iii) Bootstrap: 0 of 25 cells with a Holm-significant wrong sign (Δ₁ < 0) |
| **E2** | Kansal's advantage over blackout is explained by mean activation | R² ≥ 0.8 between the observed Δ_obs = miss(Kansal) − miss(blackout) and the **predicted** Δ_pred = ε\*(ā_K) − ε\*(ā_blk). R² is computed around the 45° line, with no fitting: R² = 1 − Σ(Δ_obs − Δ_pred)² / Σ(Δ_obs − mean Δ_obs)². Here ā_blk is the measured mean activation of the blackout run (Theorem 1 applied to both policies). *Also reported, not scored:* the literal form ε\*(ā_K) − ε\*(1/8), which ignores blackout's outage, and the form ε\*(ā_K) − [π + (1 − π) ε\*(1/8)] (Prop. 2′ floor) |
| **E3** | Periodic at ā_max (Theorem 2, sized on TRAIN, run on TEST) misses no more than Kansal-EWMA and no more than blackout | Population: cells with ā_max(TRAIN) > 0. Below that, idle-only operation already empties storage, ā_max is undefined, and every policy has outages; the number of excluded cells is reported. Criterion: miss(per_amax_d0) ≤ miss(Kansal) **and** ≤ miss(blackout) in ≥ 90 % of the population. Bootstrap: 0 Holm-significant wrong signs in the 25-cell families (Kansal − per_amax_d0 ≥ 0; blackout − per_amax_d0 ≥ 0), restricted to cells with ā_max > 0. The outage share of per_amax_d0 on TEST is reported. The variants δ = 0.05 and 0.10 are reported as secondary and **do not change the E3 verdict** (no choice of δ after seeing the results) |

**Rule from the P4 prompt:** statement (a) "throttling is useless; spending the spill is what helps, fully predicted by ε\*(ā); periodic at ā_max dominates" may be chosen for the paper **only if E1, E2 and E3 all PASS**. If E2 FAILs, (a) is excluded. Otherwise the narrow claim of CP-B1 Q2 stands, and Kansal is reported as an exploratory observation.

## 3. What the analyst saw before registering (disclosure)

- **TEST:** only the CP-B1 aggregates (Kansal − blackout: median −0.015; share better by > 0.03: 34 %; the extremes at Madrid SON, r = 5, m = 1).
- **TRAIN smoke test** of the new module, 1 combo (Madrid-MSG SON, r = 5, ℓ̃ = 0.04, m = 1, TRAIN for both members):
  - At small C, ā_max = 0. This motivated the E3 population rule above.
  - At C ≈ 1.2 C\*_per(8), Kansal runs at ā ≈ 0.50 with 2.7 % outage, against ā_max = 0.158 for no-outage periodic (miss 0.29 vs 0.44). This suggests that **E3 is at risk**: accepting short outages may buy more activation than any no-outage constant rate.
  - The predictions were **not** changed after this smoke test. They are the ones stated in the prompt.
- **Nothing else** from the E-stage on TEST was seen.
