# THEORY_40 — Miss floors and storage sizing for energy-harvesting sensing nodes

*Topic 40, P1 (drafted 09-10-2026, after CP-B0 of 08-10-2026). Status: working theory note, not manuscript text.*
*Every numerical value quoted here is produced by `code/sim40/` (tests in `code/sim40/tests/test_theory.py`); corpus numbers use the full rebuilt corpus (121 videos, 3,713 events, `results/corpus_rebuild_check.json`).*

---

## 0. What is new and what is restated (A8)

| Item | Status | Closest prior work (DOI) |
|---|---|---|
| Lemma 1 (storage never empties ⇔ window condition) | **Restated** | Moser, Thiele, Brunelli, Benini, Real-Time Syst. 2007, Thm 4/5 and §5.1 (10.1007/s11241-007-9027-0); leakage as in Kansal et al., ACM TECS 2007, Eq. 8 / Thm 2.2 (10.1145/1274858.1274870) |
| Lemma 2 (gap decomposition of the catch probability) | **Restated** | Discrete Palm–Khinchin form (Daley & Vere-Jones, 10.1007/b97277); per-gap cost of Lin et al., Oper. Res. 2013 (10.1287/opre.1120.1149); periodic case = Yau et al., ACM TOSN 2010, Thm 4.2 (10.1145/1824766.1824774) |
| Theorem 1(i): miss ≥ ε\*(a) for *every* oblivious schedule | **Elementary consequence, stated explicitly** (Lemma 2 + Jensen) | Implied by Lin et al. 2013; no explicit E_D[min(1, aD)] certificate found (`P1/A8_THM1_LITCHECK_40.md`) |
| Theorem 1(iii): equality for every F_D ⇔ all gaps ∈ {g, g+1} | **New to our knowledge** (proof elementary) | — |
| Corollary 1.2 (spread-even ≻ bursty, Jensen gap of Ψ) | Same Jensen principle as Kar et al. (10.1109/tnet.2005.863710, Thm 1), new object (harvest-driven rate profile, events with duration) | — |
| Lemma 3 (greedy attains the maximum activation budget) | New statement, routine exchange proof | (cf. lazy scheduling, Moser 2007) |
| **Theorem 2 (energy-induced miss floor)** | **New** (no finite-capacity floor on the miss of *events with duration* found; Ren 2015 and Jaggi WN full texts still unread — R16) | Kar/Jaggi/Ren 2005–2015 (stochastic, asymptotic in capacity) |
| Proposition 2′ (blackout = LPSP + ε\* term) | LPSP part **known** (PV sizing); only the ε\* term is new | — |
| Lemma 4 (taut string optimal for every concave Ψ) | **Restated** (energy-tunnel shortest path) | Tutuncuoglu & Yener, IEEE TWC 2012 (10.1109/TWC.2012.012412.110805); Yang & Ulukus, IEEE TCOM 2012 (10.1109/TCOMM.2011.112811.100349) |
| **Theorem 2b (C\*(ε) sandwich; exact under an anchoring condition)** | **New** (ε > 0 part of G2; ε = 0 is Moser §5.1) | — |
| Corollary 3 (gate with cue cost) | One-line consequence of Lemma 1 (as P0 predicted); value is the measured map | — |

All results 1–2b concern **oblivious** policies. Cue-based (gated) policies appear only in §6.

---

## 1. Model

**Time and energy.** Slots t ∈ ℤ_T (a cyclic horizon of T slots; one slot = one frame period, 100 ms at 10 fps). All energies are in units of the idle-slot energy e_idle (dimensionless, P0 `ENERGY_MODEL_40.md` §8):

- slot demand e_t = 1 + ℓ̃ + x_t (r − 1), with x_t ∈ {0, 1} (detector invoked or not), r = (e_idle + e_act)/e_idle ≥ 1;
- ℓ̃ ≥ 0 is a **constant-power leakage** per slot. A state-dependent leakage λ(B) with λ(B) ≤ ℓ̃ for all B ≤ C (e.g. a super-capacitor's DCL at rated voltage) only lowers the demand, so every "never empties" statement proved with ℓ̃ remains valid for λ (conservative);
- harvest h_t ≥ 0 per slot (trace), storage capacity C, storage B_t.

**Definition 1 (storage dynamics, brown-out rule).** B_0 ≤ C and, while the node is on,
B_t = min(C, B_{t−1} + h_t − e_t). If B_{t−1} + h_t < e_t the slot cannot be paid: the node is **off** (outage), x_t = 0, only leakage is drawn, and it restarts when B ≥ θC (θ = 0.05 in the simulator).

**Definition 2 (policy, activation rate).** A policy is a (possibly random) schedule x ∈ {0,1}^T. Its average activation is a(x) = (1/T) Σ_t x_t. A policy is **oblivious** if x is independent of the event process (it may depend on the harvest trace, on time, on its own storage). A **cue-based** policy (gate) pays a cue cost c per slot and lets x_t depend on frame content.

**Definition 3 (events).** An event is a pair (s, D): onset s, duration D ∈ {1, 2, …}. It is **caught** if x_t = 1 for some t ∈ {s, …, s + D − 1} (indices mod T). miss(x) = P(not caught).

**Assumption A1.** s is uniform on ℤ_T, D ~ F_D, and (s, D, x) are mutually independent. D ≤ T. (The corpus has D_max = 6,300 slots ≪ T ≈ 10⁸ per season.)
**Assumption A2.** The harvest trace is independent of the event process (A1 already implies it for oblivious x).

**Notation.** φ(g) := E[min(g, D)] = Σ_{k=0}^{g−1} P(D > k) (concave, non-decreasing in g ∈ ℕ);
Ψ(a) := E[min(1, aD)] (concave, non-decreasing, piecewise linear in a ∈ [0, 1] with breakpoints at a = 1/d);
**ε\*(a) := 1 − Ψ(a)** (convex, non-increasing). Corpus values: ε\*(1/K) = 0.358, 0.4995, 0.655, 0.849 for K = 4, 8, 16, 64 (identical to P0 §4.3).

---

## 2. Lemma 1 (restated) — when storage never empties

**Lemma 1 (Moser et al. 2007, Thm 4/5 and §5.1; leakage as Kansal et al. 2007, Eq. 8).** Let B_0 = C. Write H(s, t] = Σ_{u=s+1}^{t} h_u and E_x(s, t] = Σ_{u=s+1}^{t} e_u. Then
B_t ≥ 0 for all t  ⇔  E_x(s, t] − H(s, t] ≤ C for all 0 ≤ s < t ≤ T.
If the harvest is only known through a lower envelope α_l (H(s, s+Δ] ≥ α_l(Δ) for all s, Δ), a sufficient condition is demand_x(Δ) ≤ α_l(Δ) + C for all Δ, with demand_x(Δ) := max_s E_x(s, s+Δ]; it is also necessary when every harvest sequence compatible with α_l must be served (Moser et al., Thm 4).

*Proof sketch.* Without lower clipping, the recursion with upper saturation has the closed form B_t = min_{0≤s≤t} (C + H(s, t] − E_x(s, t]) (Lindley-type recursion for a reflected walk). Non-negativity of every term is the window condition. The envelope form follows from H ≥ α_l. ∎ (Not claimed as new.)

**Corollary 1.1 (storage need).** For a known trace, C\*(x; h) = max_{s<t} [E_x(s, t] − H(s, t]]⁺ (maximum drawdown of the cumulative net income). For an envelope, C\*(x; α_l) = sup_Δ [demand_x(Δ) − α_l(Δ)]⁺. For periodic-K, demand_K(Δ) = ⌈Δ/K⌉(r − 1) + Δ(1 + ℓ̃) ≤ Δ(1 + ℓ̃ + (r − 1)/K) + (r − 1).
*Validated:* brute force vs. slot-level simulation, 300 random cases, 0 mismatches (test (c)).

**Remark 1 (steady state, granularity).** On a cyclic horizon in steady state, C\* is the maximum drawdown over two concatenated cycles, and C\* = ∞ when the cycle's net income is negative. The simulator works in 1-minute sub-steps with constant harvest and constant rate inside a sub-step, where storage is monotone and every constraint is checked exactly at sub-step boundaries. The activation granularity (one activation costs r − 1 at once) is covered by adding r − 1 to fluid storage needs. Checked against a slot-level simulation at 10 fps (2 days, Madrid DJF): storage agrees within r − 1 up to the first outage, and the on-time fraction agrees within 0.01 (test `fluid_vs_slot_level`).

---

## 3. Theorem 1 — miss floor of any oblivious schedule

**Lemma 2 (gap decomposition; restated).** Let x be deterministic with n ≥ 1 activations at cyclic positions τ_1 < … < τ_n and gaps g_i = τ_{i+1} − τ_i (cyclically, Σ g_i = T). Under A1,
1 − miss(x) = (1/T) Σ_{i=1}^{n} φ(g_i).

*Proof.* The onsets s ∈ (τ_i, τ_{i+1}] are exactly g_i positions. For each of them the first activation at or after s is τ_{i+1}, at distance k = τ_{i+1} − s ∈ {0, …, g_i − 1}, and the event is caught iff D > k. Summing P(D > k) over k gives φ(g_i). Averaging over the uniform onset gives the claim. ∎
(This is the discrete form of the Palm–Khinchin equation; the periodic case is Yau et al. 2010, Thm 4.2.)

**Theorem 1 (miss floor vs. average activation).**
(i) For every oblivious policy with E[a(x)] = a: miss(x) ≥ ε\*(a) = 1 − E_D[min(1, aD)].
(ii) (Exact form.) For deterministic x, miss(x) − ε\*(a) = (1/T) E_D[ min(T, nD) − Σ_i min(g_i, D) ] ≥ 0.
(iii) (Tightness.) For deterministic x, equality holds iff for every d with P(D = d) > 0, either all gaps are ≤ d or all gaps are ≥ d. Hence equality holds **for every** F_D on ℕ iff all gaps take values in {g, g + 1} for some integer g.
(iv) Periodic-K with uniform phase attains it: 1 − miss = φ(K)/K = Ψ(1/K).
(v) For any a with aT ∈ ℕ, the interleaved schedule with gaps ⌊1/a⌋ and ⌈1/a⌉ attains ε\*(a) exactly. The gap between "K not an integer" and the bound is therefore **zero**.

*Proof.* (i) Deterministic case: by Lemma 2 and Σ_i min(g_i, d) ≤ min(Σ_i g_i, Σ_i d) = min(T, nd) for every d,
1 − miss = (1/T) E_D Σ_i min(g_i, D) ≤ E_D[min(1, (n/T) D)] = Ψ(a).
Random oblivious x: condition on x and apply the deterministic bound. Since Ψ is concave, Jensen gives E_x[Ψ(a(x))] ≤ Ψ(E a(x)). (ii) is the same computation without the inequality.
(iii) Σ_i min(g_i, d) = min(T, nd) iff all g_i ≤ d (both sides equal T) or all g_i ≥ d (both sides equal nd). If some g_i < d < g_j, the left side is < nd and < T. If the gaps take only the values {g, g+1}, no integer d lies strictly between two gaps. Conversely, if two gaps differ by ≥ 2, a point mass at an integer strictly between them breaks equality.
(iv)–(v) follow from (iii). ∎

*Validated (1.7 a, b):*
- 10,000 random oblivious schedules (periodic, Bernoulli, burst, diurnal; T ∈ [500, 6000]) × the real F_D: **0 violations**. The exact catch probability, computed onset by onset, equals the gap formula to 10⁻¹².
- Monte Carlo with sampled events agrees within 4σ.
- Periodic K = 1…64 and interleaved K ∈ {2.5, 3.3, 7.7, 12.25, 40.1} attain the bound to 10⁻¹² (the requirement was ≤ 10⁻³).
- A schedule with gaps {3, 17} is strictly below the bound.

**Remark 2 (shape of ε\*; correction to PROMPT 1.3).** ε\* is **convex** and non-increasing, not concave: Ψ is concave because min(1, aD) is concave in a. Its slope is −E[D; D < 1/a]. On the corpus that slope is −0.36, −0.83, −1.40, −3.32 at a = 1/2, 1/4, 1/8, 1/16. Each extra activation therefore buys less and less, and the most expensive misses are the 1-frame events (P(D = 1) = 0.359): ε\*(a) ≥ P(D = 1)(1 − a).

**Remark 3 (why the heavy tail locks the benefit of throttling).** ε\*(a) ≥ Σ_{d < 1/a} P(D = d)(1 − ad). With 67.4 % of events shorter than 8 frames, periodic K = 8 already misses ε\*(1/8) = 0.4995 of events counted by event head, although it certifies latency ≤ 7 for every event with D ≥ 8 (miss among D ≥ K is exactly 0). Throttling from K = 8 to K = 64 (8× less activation energy) raises the miss only from 0.50 to 0.85: it keeps catching the long events that carry most of the mass of E[D] = 34.0. The miss **per unit of activation saved** is therefore small at large K and large at small K.

**Corollary 1.2 (time-varying rates: spread-even ≻ bursty).** Split the horizon into blocks of lengths n_j ≫ D_max. In each block the schedule is interleaved at rate a_j, and Σ n_j a_j = aT. Then
1 − miss = Σ_j (n_j/T) Ψ(a_j) + O(#blocks · E[D]/T) ≤ Ψ(a).
The Jensen gap Ψ(a) − Σ_j (n_j/T) Ψ(a_j) ≥ 0 is the exact miss penalty of a non-constant rate profile, such as harvest-following, day-only operation, or outages. This is the same Jensen principle as Kar et al. (2006, Thm 1), applied here to a harvest-driven rate profile and events with duration.

---

## 4. Theorem 2 — energy-induced miss floor

**Lemma 3 (maximum activation budget; greedy is optimal).** Fix h, C, r, ℓ̃ and B_0. Let need_j be the least storage at the end of sub-step j from which idle-only operation survives to the horizon:
need_J = 0, need_{j−1} = [need_j + n(1 + ℓ̃) − n h_j]⁺.
If need_0 > B_0 or need_j > C for some j, no schedule avoids an outage (blackout regime). Otherwise the greedy
y_j = min(n(r − 1), B_{j−1} + n h_j − n(1 + ℓ̃) − need_j), B_j = min(C, B_{j−1} + n h_j − n(1 + ℓ̃) − y_j)
maximises Σ_j y_j (total activation energy) over all no-outage schedules. The same holds at slot level with integer activations.

*Proof.* Let P be any feasible schedule. By induction, B^G_j ≤ B^P_j: either G stopped at need_j ≤ B^P_j, or G spent the maximum y_j while starting from no more storage. Hence G spills no more than P in every sub-step. With Z_j = (cumulative spill) + B_j, the recursion Z_j = Z_{j−1} + n h_j − n(1 + ℓ̃) − y_j gives Z^G_j ≤ Z^P_j in both cases. Then Σ y^G = B_0 + H − I − Z^G_J ≥ Σ y^P. ∎
*Validated (1.7 d):* the integer greedy equals exhaustive search over {0,1}^T (T ≤ 14) in 150 random cases, and the fluid greedy is ≥ the integer optimum in all of them.

**Definition 4.** A(C) := (1/(T(r − 1))) max Σ_j y_j (Lemma 3, B_0 = C) is the largest average activation of any no-outage schedule.
For **cyclic steady state**, any no-outage policy also satisfies the cycle's energy balance, a ≤ a_bal := (h̄ − 1 − ℓ̃)/(r − 1), so
A_cyc(C) := min(A(C), a_bal) is a valid upper bound.

**Theorem 2 (energy-induced miss floor).** Every oblivious policy that never empties storage on (h, C) satisfies
miss ≥ ε\*(A_cyc(C)).
The schedule may be chosen with full knowledge of the harvest trace, offline. Only independence from events is needed.

*Proof.* Its average activation is ≤ A_cyc(C) by Lemma 3 and the energy balance. ε\* is non-increasing, and Theorem 1(i) applies. ∎

**Proposition 2′ (blackout is the special case; only the ε\* term is new).** Let a policy (oblivious) be off on a set of slots of fraction π, made of N_out outage episodes, and let a_on be its average activation over on-slots. Under A1,
miss ≥ π + (1 − π) ε\*(a_on) − N_out E[D]/T.
At trace scale (L_out of hours, D_max = 6,300 slots, P0 §4.4), the correction is negligible. π is the classical **loss-of-power-supply probability (LPSP)** of PV sizing, which is **not new**. The new term is (1 − π) ε\*(a_on). By Jensen, π + (1 − π)ε\*(a_on) ≥ ε\*((1 − π)a_on) = ε\*(a): an outage is the most bursty rate profile.
*Proof sketch.* Events whose span lies in an outage are missed. Apply Theorem 1(i) to the on-slots concatenated into one cyclic horizon. Only events that straddle an on/off boundary are affected by the concatenation, at most E[D] per boundary in expectation. ∎

**Remark 4 (what the floor looks like on traces).** Under the season-neutral panel rule (horizon-mean harvest = (1 + m)·e(1/K_ref), K_ref = 8), a_bal is the same at every site. The **energy floor ε\*(a_bal) is therefore site-independent**, and the site enters only through how much storage brings the achievable miss down to it (Theorem 2b). The single-pass A(C) (start full, free end) exceeds a_bal when C is large relative to the season's demand (e.g. Uppsala-MSG DJF, C = C\*_per(8): A(C) = 0.22 vs a_bal = 0.175). That is the start-full advantage, which is why the cyclic bound uses the minimum.

**Remark 5 (throttling vs. blackout, F6).** At equal average activation a, throttling (spread over all slots) has floor ε\*(a), and blackout with outage fraction π has floor π + (1 − π)ε\*(a/(1 − π)). On the corpus at a = 0.1: throttling 0.538; blackout 0.568 (π = 0.1), 0.600 (π = 0.2), 0.667 (π = 0.4). So **throttling beats blackout by 3–13 points, not by an order of magnitude**: the convexity of ε\* is mild because F_D is heavy-tailed. This is the quantitative form of P0's "throttling helps only a little" (to be checked against the energy-coupled simulation, F6).

---

## 5. Theorem 2b — sizing for a miss target, C\*(ε)

**Definition 5.** For ε ∈ (ε\*(a_bal), 1), let a_ε := min{a : ε\*(a) ≤ ε} (it exists because ε\* is continuous and non-increasing). Define

- C_min(ε) := inf{C : some oblivious no-outage policy on (h, C) has miss ≤ ε} (the quantity to size);
- C_LB(ε) := inf{C : A_cyc(C) ≥ a_ε};
- C_per(ε) := C\*(interleaved periodic at a_ε) (Corollary 1.1);
- C_TS(ε) := inf{C : the taut-string policy of Lemma 4 on (h, C) has miss ≤ ε}.

**Lemma 4 (energy tunnel; restated).** Let L_j ≤ U_j be non-decreasing bounds on the cumulative activation energy Y_j, with Y_0 = 0 and Y_J fixed. The taut string Y\* (the shortest path inside the tube) satisfies Σ_j Ψ(ΔY\*_j) ≥ Σ_j Ψ(ΔY_j) for every feasible Y and **every** concave Ψ, because its increment vector is majorised by that of every feasible path (Tutuncuoglu & Yener 2012; Yang & Ulukus 2012). Applied with Ψ from Theorem 1 (catch rate per sub-step is (n/T)Ψ(a_j)) and the no-spill tube S_j ≤ Y_j ≤ C + S_j, S_j = Σ_{i≤j} n(h_i − 1 − ℓ̃) (monotone hull), it gives the miss-optimal no-outage oblivious policy among those that never spill.

**Theorem 2b (sizing sandwich).** For every ε ∈ (ε\*(a_bal), 1):
(a) C_LB(ε) ≤ C_min(ε);
(b) C_min(ε) ≤ min(C_TS(ε), C_per(ε));
(c) (*exactness*) let t\* be the anchor used by the taut string (the end of the cycle's largest cumulative idle-only surplus). If some miss-optimal no-outage cyclic policy has full storage at t\* and its rate stays below the cap a = 1, then C_min(ε) = C_TS(ε).

*Proof.* (a) A policy with miss ≤ ε needs a ≥ a_ε (Theorem 1(i)) and a ≤ A_cyc(C) (Theorem 2). A_cyc is non-decreasing in C.
(b) Both policies are feasible no-outage policies (the taut string by construction; periodic by Corollary 1.1).
(c) Without the cap, every spilling policy is dominated, rate-wise, by a non-spilling one that consumes the would-be spill: same storage path while not full, pointwise higher rates, and Ψ is increasing. A non-spilling cyclic policy that is full at t\* is a path in the anchored tube S_j ≤ Y_j ≤ C + S_j (start full, end full at t\*). By Lemma 4 the taut string maximises Σ Ψ over that tube. ∎

*Empirical companion of (b) (not a theorem):* C_TS(ε) ≤ C_per(ε) and miss_TS(C) ≤ miss_per(C) whenever periodic has no outage. Both are checked in every grid cell (F3), and any cell where they fail is reported. A theorem would need the anchor to coincide with a full-storage time of the periodic schedule; the simulator does not search anchors.

**What this answers in PROMPT 1.5(ii).** "Does periodic need the least storage at a given miss?" **No.** Periodic is miss-optimal at a *given activation rate* (Theorem 1). For a *given miss target*, the miss-optimal schedule spends more when the sun shines but keeps its rate as flat as the tube allows (taut string), and it needs C_TS ≤ C_per. Example (TRAIN, Madrid-MSG DJF, r = 15, ℓ̃ = 0.04, m = 0.25, ε = 0.5): C_TS/C_per ≈ 0.30.
The lower bound C_LB is **weak**: it collapses to the idle-feasibility threshold, because A(C) counts daytime activations that a low-miss policy cannot use. The informative bounds are C_TS (exact under (c)) and C_per.

**T3(i) — the frontier "spread-even ↔ harvest-following".**
- *At equal a:* periodic attains ε\*(a) (best miss) and needs C_per(a); harvest-following (rate ∝ surplus over idle) needs less storage C_HF(a) but misses more, by the Jensen gap of Corollary 1.2.
- The intermediate curve uses the equal-a frontier points obtained by discarding a fixed fraction of the incoming harvest and running the taut string. It is achievable but not proven optimal at small C, because dumping harvest is not the optimal way to waste energy, so it is reported as an inner frontier.
- *At equal ε:* C_LB ≤ C_min ≤ C_TS (= C_min under anchoring) and C_TS ≤ C_per (checked empirically).
- The prereg (`PREREG_40.md`) fixes the signs and magnitudes to be checked on TEST.

---

## 6. Corollary 3 — gates with a per-slot cue cost (cue-based class)

A gate cannot be "oblivised": x_t depends on the cue, so Theorems 1–2b do not apply to it. Its energy, however, is at least that of an oblivious schedule with the same activation profile plus the cue: e_t = 1 + ℓ̃ + c + x_t(r − 1).

**Corollary 3.** Let a periodic schedule at rate a_per be feasible on (h, C) (Lemma 1), and let a gate activate at long-run rate a_g = ρ a_per.
(i) (*Long-run, any C.*) If c + (ρ − 1) a_per (r − 1) > h̄ − (1 + ℓ̃ + a_per(r − 1)) (the periodic slack per slot), the gate empties storage for every finite C. This needs only stationarity of the gate's activation process.
(ii) (*Fluid, window form.*) If the gate's activations are spread at rate a_g, it is infeasible on (h, C) iff c Δ + (a_g − a_per)(r − 1)Δ exceeds the periodic slack α_l(Δ) + C − demand_per(Δ) for some Δ. For constant fluid demand, C\* is strictly increasing in demand, so at C = C\*_per(a_per) the gate is infeasible iff **c > c\*(ρ) := (1 − ρ) a_per (r − 1)**. This boundary is analytic and site-independent.
(iii) The site enters only through the **extra storage** C\*_gate/C\*_per, and through the outage, and hence miss, of a gate run at C\*_per. These are what F4 maps.

**Activation ratio recomputed from public data (R18).** From the rebuilt corpus, the in-event frame fraction is 126,394/166,589 ≈ 0.759. This is the activation rate of an ideal *presence gate* that keeps the detector on while any object is present. Against periodic K = 8, ρ ≈ 6.1. No cue model is fitted, so Corollary 3 stays parametric in (c, ρ) with ρ ∈ {0.25, …, 6}. The value ρ ≈ 6.1 is marked on the map as "presence gate, recomputed from public JSON".

---

## 7. Sanity checks (1.7) — summary

| Check | Requirement | Result |
|---|---|---|
| (a) Theorem 1 on random oblivious schedules × real F_D | 0 violations, ≥ 10⁴ schedules | **0 / 10,000** |
| (a′) sampled-event Monte Carlo vs exact | within 4σ | pass (K = 3, 8, 33; 2·10⁵ events) |
| (b) tightness, periodic and interleaved | ≤ 10⁻³ | ≤ 10⁻¹² (K = 1…64; five non-integer K) |
| (c) Lemma 1 vs brute force | 0 mismatches | 0 / 300 |
| (d) Lemma 3 greedy vs exhaustive | equal | 150 / 150 equal |
| loader energy integral | ≤ 0.1 % | ≤ 2·10⁻¹⁶ (zoh exact; linear rescaled per day) |
| fluid vs slot-level storage (10 fps) | within r − 1 | pass (Madrid DJF, 2 days, with an outage) |
| event replay vs analytic miss | within CI | e.g. 0.4995 vs 0.5003; 0.8107 vs 0.8109 (2·10⁵ events) |

Rule: any violation is reported, never fixed by changing a theorem.

---

## 8. Open points for CP-B1

1. Ren & Cheng 2015 (P2P, 10.1007/s12083-013-0238-y) and Jaggi et al. WN 2009 full texts: needed before claiming Theorem 2 is the first finite-capacity miss floor (R16).
2. Lemma 4 cites the energy-tunnel result for concave *rate* functions. I verified that Ψ is concave and piecewise linear; the full text of Tutuncuoglu & Yener still has to be read to quote the exact theorem number.
3. Theorem 2b(c) is exact only under the anchoring condition (a miss-optimal policy is full at the anchor t\*). Otherwise C_TS is an achievable upper bound on C_min. Searching over anchors (cost × number of anchors) would remove the condition and is left for P4 if a reviewer needs it.
4. A1 (uniform onsets) is an assumption: event timing in real deployments is diurnal. A diurnal onset density w(t) turns Ψ into a w-weighted average and breaks the site-independence of the floor. This is a robustness item, not covered here.
