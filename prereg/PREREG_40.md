# PREREG_40 — Pre-registration of predictions before the TEST run (topic 40)

*Written 09-10-2026 after the TRAIN exploration and BEFORE any TEST simulation. Frozen by SHA-256 and the git tag `prereg-40-v1` in the local repo `D:\Repos\harvest-certified-detection\` (not pushed). Any later change becomes a new version (`-v2`) with a dated reason; the v1 predictions are the ones scored at CP-B1.*

## 0. Split, data and code

- **Traces:** TRAIN = odd months, TEST = even months, applied within every (site, season) cell.
  - Outdoor: 5 site-products × 4 seasons. HCMC Himawari-9; Madrid MSG and SARAH-3; Uppsala MSG and SARAH-3; 2025, Open-Meteo, native resolution.
  - Indoor: EnHANTS Setups B–F, horizon 'ALL' (whole record), months split the same way.
- **Corpus:** TRAIN/TEST by video, half/half, seeded permutation (seed 42), from the corpus rebuilt in `code/sim40/events.py`. The rebuild is identical to `events_gated.csv`: 121 videos, 3,713 events, F_D hash equal (`results/corpus_rebuild_check.json`).
- **Code:** `code/sim40/` at the tag. One TRAIN-only difference: the TRAIN `main` stage ran with a fixed two-pass cyclic simulation. Before freezing, this was changed to iterate until the end-of-cycle storage converges (`energy.simulate_cyclic`). The change only affects policies whose cycle is in energy deficit (periodic K = 2/4, gates with ρ > 1). TEST runs entirely with the frozen code.
- **Grid (TEST):**
  - `main`: 25 cells × r ∈ {1.1, 1.3, 2, 5, 15, 40, 100, 300} × ℓ̃ ∈ {0, 0.01, 0.04, 0.1} × m ∈ {0.25, 1.0} × 20 log-spaced C.
  - Policies: periodic K ∈ {2, 4, 8, 16, 32, 64}, throttle 8→64, harvest-following (a = 1/8), Kansal-style EWMA duty cycle, taut string (energy-tunnel optimum), greedy a_max.
  - `frontier`, `throttle`: r ∈ {5, 15, 40} × ℓ̃ ∈ {0, 0.04} × m ∈ {0.25, 1.0}.
  - `gate`: r ∈ {5, 15, 40}, ℓ̃ = 0.04, m = 0.25, c ∈ {0, 0.02, 0.05, 0.1, 0.2}, ρ ∈ {0.25, 0.5, 0.75, 1, 1.5, 2, 4, 6}.
  - `boot` (r = 15, ℓ̃ = 0.04, m = 0.25, K = 8):
    - by-video bootstrap B = 1000 for Δmiss;
    - 7-day moving-block bootstrap B = 1000 for ΔC;
    - B = 100 for C_TS/C_per on 6 cells (HCMC SON, Madrid-MSG DJF, Madrid-SARAH3 DJF, Uppsala-MSG DJF, Uppsala-SARAH3 DJF, SetupC ALL).
  - F5 sizing: class-A node, r = 14.3, ℓ̃ = 0.036, e_idle = 0.248 mJ, K = 8, B = 1000.
- **Statistics:**
  - Sign tests use one-sided bootstrap p-values (share of resamples with the wrong sign). When no resample has the wrong sign, p is the normal approximation Φ(−|mean|/sd) of the bootstrap distribution. Declared here because the empirical floor 1/(B+1) is above Holm's first threshold.
  - Holm step-down at family-wise α = 0.05 over all sign tests of `boot`.
- **Notation (fixes an ambiguity in the prompt):**
  - Δmiss := miss(harvest-following) − miss(periodic) at equal a; predicted > 0.
  - ΔC := C(harvest-following) − C(periodic) at equal a; predicted < 0.

## 1. Predictions

| # | Prediction (TEST) | Pass criterion | TRAIN basis |
|---|---|---|---|
| **H1** (F2) | No violation of Theorem 1 (all policies, replayed events), Theorem 2 (cyclic no-outage policies, energy floor ε\*(A_cyc(C)); the single-pass greedy excluded) or Proposition 2′ (outage policies, with the boundary term) | **0 family-wise violations** (replay below floor by more than z_Bonf·SE, α = 0.05, SE ≥ 1/n). **0 analytic violations** (tolerance 10⁻⁶) | 0 / 0 / 0 family-wise. The 25 raw analytic hits were all the transient artifact fixed above |
| **H2a** Kansal Thm 2.2, tight (ρ₁ = ρ₂ + ρ_leak) | C\*/C_Kansal ∈ [0.99, 1.01] in 100 % of `main` combos | = 1.00 by construction (identity of drawdowns for constant demand). Stated so that it is never presented as a finding |
| **H2b** Kansal with ρ₁ = mean harvest | C\*/C_Kansal-mean < 1 (Kansal-mean **over**-sizes) in ≥ 95 % of combos | TRAIN 0.05–0.75 |
| **H2c** average-day (P0 "C_neutral", daily balance on the mean day) | C\*/C_avgday > 1 in 100 % of combos. Medians per group: HCMC ∈ [1.1, 2.5]; Madrid ∈ [2, 8]; Uppsala ∈ [2, 10]; indoor ∈ [5, 25]. Max outdoor ≥ 15, max indoor ≥ 30 | TRAIN medians 1.41 / 3.7–3.5 / 2.8–5.6 / 11.5; max 40 / 76 |
| **H2d** Buchli daily-resolution deficit | C\*/C_Buchli > 1 in ≥ 95 % of combos where C_Buchli > 0. HCMC median ≥ 2 (nights invisible at daily resolution); Madrid, Uppsala and indoor medians ∈ [1, 2] | TRAIN 2.83 / 1.36–1.39 / 1.25–1.6 / 1.15 |
| **H2e** 3-day autonomy rule | HCMC: C\* < C_3day (rule **over**-sizes) in 100 % of combos. Madrid, Uppsala: median ratio < 1.2 but max > 2 (rule **under**-sizes in transition and winter seasons). Indoor: share with C\* > C_3day ≥ 40 % | TRAIN HCMC max 0.47; Madrid/Uppsala max 3.3–7.4; indoor median 1.35 |
| **H3a** (F3, equal a) | Δmiss > 0 in 100 % of `frontier` combos (K ∈ {4, 8, 16, 32}). Median Δmiss at K = 8 per site group ∈ [0.18, 0.32] | TRAIN min 0.05 (K = 32); K = 8 medians 0.24–0.27 |
| **H3b** (F3, equal a) | ΔC < 0 in ≥ 95 % of combos with finite C_HF. Median C_HF/C_per at K = 8 ∈ [0.1, 0.5] per group | TRAIN 0.01–0.89; medians 0.19–0.28 |
| **H3c** (boot) | Δmiss > 0 and ΔC < 0 significant after Holm in every one of the 25 cells | TRAIN Madrid DJF: Δmiss 0.29 [0.24, 0.37], ΔC −0.80 [−0.85, −0.72] |
| **H4a** (F3, equal ε; Theorem 2b) | C_TS(ε)/C_per(ε) < 1 in ≥ 95 % of finite cells. Median per group ∈ [0.2, 0.7] for ε ∈ {0.5, 0.6} | TRAIN medians 0.30–0.46 |
| **H4b** (Theorem 2b(a), check of the theorem) | C_LB/C_TS ≤ 1.02 (bisection tolerance) in 100 % of cells | TRAIN max 1.0098 |
| **H4c** (tightness of the sandwich) | C_LB/C_TS median ≥ 0.9 at ε ≥ 0.6; median < 0.9 at ε = 0.45 in ≥ 3 of 4 groups | TRAIN ≥ 0.96 at ε ≥ 0.6; 0.41–0.69 at ε = 0.45 |
| **H4d** (boot) | C_TS/C_per < 1 significant after Holm in the 6 bootstrap cells | TRAIN Madrid DJF 0.28 |
| **H5** (F6) | see §2 | |
| **H6** (F4, Corollary 3) | Simulated gate infeasibility at C\*_per (outage > 0) agrees with the analytic boundary c > (1 − ρ)a_per(r − 1) in 100 % of `gate` cells. Gate outage at C\*_per non-decreasing in c (fixed ρ) and in ρ (fixed c) in ≥ 95 % of pairs | TRAIN 3000 / 3000 |
| **H7** (F5, class-A node, m = 0.25) | C\*_per(8) < 1 kJ at HCMC in all 4 seasons; > 2 kJ in ≥ 2 Madrid and ≥ 2 Uppsala seasons; < 44 kJ (one 18650 cell) in 100 % of cells; > 45 J (one 10 F super-capacitor) in 100 % of cells. C_TS/C\* at the same miss < 0.6 in ≥ 80 % of cells | TRAIN HCMC 0.42–0.82 kJ; max 20.5 kJ (indoor C); TS/C\* 0.08–0.59 |

## 2. H5 — throttling vs blackout (F6)

Population: `throttle`-stage cells where blackout periodic K = 8 has outage fraction 0 < π < 1. Throttle variants:
- K′ ∈ {16, 32, 64};
- (low, high) storage thresholds ∈ {5/10 %, 10/20 %, 20/50 %};
- five variants in total (`run_grid.THROTTLES`).

| # | Prediction (TEST) | Pass criterion | TRAIN basis (4,668 cells) |
|---|---|---|---|
| **H5a** | Even the best throttle variant per cell (oracle choice, favouring throttling) is within ±0.03 of blackout | \|miss(best throttle) − miss(blackout)\| ≤ 0.03 in ≥ 95 % of cells; best throttle better by > 0.03 in ≤ 1 % | 99.9 % within ±0.02; 0 % better by > 0.03; median +0.0016 |
| **H5b** | The naive throttle 8→64 at 20/50 % misses **more** than blackout | Δ > 0 in ≥ 90 % of cells; median Δ ∈ [0.01, 0.06] | 98.9 % > 0; median +0.030 |
| **H5c** | The coupled throttling gain is far below the equal-a analytic gain of THEORY Remark 5 (3–13 points) | median(best throttle − blackout) > −0.01 in every site group | TRAIN medians +0.0009 … +0.0026 |

Interpretation fixed in advance: if H5a–c pass, the "throttle instead of blackout" design rule is **not** supported at trace scale. That is the counter-intuitive candidate (luật 6). The reason is that outages are multi-hour deficits, so a throttled node still pays idle energy and ends up in the same deficit.


## 3. What is NOT predicted (exploratory at TEST)

- The anchoring condition of Theorem 2b(c) (exact equality C_min = C_TS) is not tested.
- The latency of throttled policies (> K − 1 by construction) is reported, not predicted.
- The Kansal-style EWMA controller's miss and outage are reported, not predicted.
- Interpolation sensitivity (zoh vs linear) is reported for 6 cells, not predicted.

## 4. Scoring rule at CP-B1

Each H is scored PASS / FAIL against its criterion. A FAIL is reported with its numbers, and neither the prediction nor the theorem is edited to match (THEORY_40 §7). A wrong sign in H3/H4 demotes the corresponding T3(i) claim.
