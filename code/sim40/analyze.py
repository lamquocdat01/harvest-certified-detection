"""Aggregate grid checkpoints into the F1-F6 summaries (same code for TRAIN exploration and TEST evaluation).

python -m sim40.analyze --split train   ->  results/summary_<split>.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np

from . import config as cfg

Z = 3.0  # per-test tolerance (replay standard errors); reported together with the family-wise rule below
ALPHA_FW = 0.05
TOL_ANALYTIC = 1e-6  # float tolerance for the exact (Psi-based) comparison
# greedy_amax is a single-pass (start full, free end) schedule, not a cyclic steady-state one: Theorem 2's
# cyclic floor eps*(A_cyc) does not apply to it (its own floor is eps*(A(C)) = Theorem 1 at its rate).


def load(stage, split):
    d = cfg.CKPT / stage / split
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def _f(x):
    return None if x is None else float(x)


def site_group(site):
    return "indoor" if site.startswith("Setup") else "outdoor"


def f2_violations(rows_all):
    """Theorem 1 (own rate), Theorem 2 (no-outage, energy floor), Prop 2' (blackout) on replayed misses."""
    out = defaultdict(lambda: {"n": 0, "viol": 0, "worst_margin": np.inf})
    for R in rows_all:
        for row in R["rows"]:
            for name, s in row["policies"].items():
                if s is None:
                    continue
                rm, n = s["replay_miss"], s["replay_n"]
                se = max(np.sqrt(rm * (1 - rm) / n), 1.0 / n)   # SE floor 1/n (miss ~ 0 cells)
                checks = [("T1_any_policy", s["floor_T1"], 0.0)]
                if s.get("no_outage") and s.get("floor_E") is not None and name != "greedy_amax":
                    checks.append(("T2_energy_floor", s["floor_E"], 0.0))
                if s["outage_frac"] > 0:
                    checks.append(("P2prime_blackout", s["floor_blackout"], s["boundary_term"]))
                for key, fl, bnd in checks:
                    o = out[key]
                    o["n"] += 1
                    margin = rm - (fl - bnd)
                    o["worst_margin"] = min(o["worst_margin"], margin / se if se > 0 else margin)
                    if margin < -Z * se:
                        o["viol"] += 1
                # analytic (non-replay) miss vs floor: must hold exactly (Jensen)
                if s.get("no_outage") and s.get("floor_E") is not None and name != "greedy_amax":
                    o = out["T2_energy_floor_analytic"]
                    o["n"] += 1
                    o["viol"] += int(s["miss"] < s["floor_E"] - TOL_ANALYTIC)
                    o["worst_margin"] = min(o["worst_margin"], s["miss"] - s["floor_E"])
    from scipy.stats import norm
    res = {}
    for k, v in out.items():
        v = dict(v)
        if not k.endswith("analytic"):
            v["z_bonferroni"] = float(norm.ppf(1 - ALPHA_FW / max(v["n"], 1)))
            v["viol_familywise"] = None  # filled below
            v["expected_3sigma_if_tight"] = float(v["n"] * norm.sf(Z))
        res[k] = v
    return res


def f2_familywise(rows_all, res):
    cnt = {k: 0 for k in res}
    for R in rows_all:
        for row in R["rows"]:
            for name, s in row["policies"].items():
                if s is None:
                    continue
                rm, n = s["replay_miss"], s["replay_n"]
                se = max(np.sqrt(rm * (1 - rm) / n), 1.0 / n)   # SE floor 1/n (miss ~ 0 cells)
                checks = [("T1_any_policy", s["floor_T1"], 0.0)]
                if s.get("no_outage") and s.get("floor_E") is not None and name != "greedy_amax":
                    checks.append(("T2_energy_floor", s["floor_E"], 0.0))
                if s["outage_frac"] > 0:
                    checks.append(("P2prime_blackout", s["floor_blackout"], s["boundary_term"]))
                for key, fl, bnd in checks:
                    if rm - (fl - bnd) < -res[key]["z_bonferroni"] * se:
                        cnt[key] += 1
    for k in cnt:
        if "z_bonferroni" in res[k]:
            res[k]["viol_familywise"] = cnt[k]
    return res


def f2_points(rows_all, n_max=20000, seed=42):
    fl, rp = [], []
    for R in rows_all:
        for row in R["rows"]:
            for s in row["policies"].values():
                if s is None:
                    continue
                f = s.get("floor_E") if s.get("no_outage") and s.get("floor_E") is not None else                     (s["floor_blackout"] if s["outage_frac"] > 0 else s["floor_T1"])
                fl.append(f); rp.append(s["replay_miss"])
    idx = np.random.default_rng(seed).permutation(len(fl))[:n_max]
    return {"floor": [fl[i] for i in idx], "replay": [rp[i] for i in idx]}


def f1_frontier(rows_all):
    """C*_per(K) in days of the K-demand, per site/season/r/l/m."""
    out = []
    for R in rows_all:
        dem = {K: 1440 * 600 * (1 + R["l"] + (R["r"] - 1) / int(K)) for K in R["C_per"]}
        out.append({k: R[k] for k in ("site", "season", "r", "l", "m")} |
                   {"C_per_days": {K: (_f(v) / dem[K] if v is not None else None) for K, v in R["C_per"].items()},
                    "C_per": R["C_per"]})
    return out


def baseline_ratios(rows_all):
    out = []
    for R in rows_all:
        b = R["baselines"]
        cs = b["C_star"]
        if cs is None:
            continue
        out.append({k: R[k] for k in ("site", "season", "r", "l", "m")} |
                   {f"C*/{k}": (cs / b[k] if b.get(k) else None)
                    for k in ("C_kansal_tight", "C_kansal_mean", "C_avgday", "C_buchli_daily", "C_3day")} |
                   {"C*_days": cs / b["daily_demand"]})
    return out


def f6_throttle_vs_blackout(rows_all):
    """At each C where periodic-8 blacks out (0 < pi < 1): miss(throttle 8->64) - miss(periodic-8 blackout)."""
    out = []
    for R in rows_all:
        for row in R["rows"]:
            p8, th = row["policies"].get("periodic_K8"), row["policies"].get("throttle_8to64")
            if not p8 or not th or not (0 < p8["outage_frac"] < 1):
                continue
            out.append({k: R[k] for k in ("site", "season", "r", "l", "m")} |
                       {"C": row["C"], "pi_per8": p8["outage_frac"], "miss_per8": p8["replay_miss"],
                        "miss_thr": th["replay_miss"], "pi_thr": th["outage_frac"],
                        "d_miss_thr_minus_blackout": th["replay_miss"] - p8["replay_miss"]})
    return out


def policy_table(rows_all, C_key="C*_per8"):
    """Miss/outage of each policy at the C-grid point closest to C*_per(8)."""
    out = []
    for R in rows_all:
        cp = R["C_per"]["8"]
        if cp is None:
            continue
        i = int(np.argmin([abs(np.log(row["C"] / cp)) for row in R["rows"]]))
        row = R["rows"][i]
        rec = {k: R[k] for k in ("site", "season", "r", "l", "m")} | {"C_over_Cper8": row["C"] / cp,
                                                                       "floor_E": row["floor_E"]}
        for name, s in row["policies"].items():
            if s is not None:
                rec[name] = {"miss": s["replay_miss"], "outage": s["outage_frac"], "a_bar": s["a_bar"]}
        out.append(rec)
    return out


def summarize_main(split):
    R = load("main", split)
    return {"n_combos": len(R), "F2": f2_familywise(R, f2_violations(R)), "F2_points": f2_points(R),
            "baselines": baseline_ratios(R), "F1": f1_frontier(R),
            "F6": f6_throttle_vs_blackout(R), "at_Cper8": policy_table(R)}


def summarize_frontier(split):
    F = load("frontier", split)
    eq, eps = [], []
    for R in F:
        base = {k: R[k] for k in ("site", "season", "r", "l", "m")}
        for K, v in R["equal_a"].items():
            if v["C_per"] is None or v["C_hf"] is None:
                continue
            eq.append(base | {"K": int(K), "C_per": v["C_per"], "C_hf": v["C_hf"], "miss_per": v["miss_per"],
                              "miss_hf": v["miss_hf"], "dC_hf_minus_per_rel": v["C_hf"] / v["C_per"] - 1,
                              "dmiss_hf_minus_per": v["miss_hf"] - v["miss_per"]})
        for e, v in R["eps_sizing"].items():
            if v.get("C_per") is None or v.get("C_TS") is None:
                continue
            eps.append(base | {"eps": float(e), "C_LB": v.get("C_LB"), "C_TS": v["C_TS"], "C_per": v["C_per"],
                               "TS_over_per": v["C_TS"] / v["C_per"],
                               "LB_over_TS": (v["C_LB"] / v["C_TS"]) if v.get("C_LB") else None})
    return {"equal_a": eq, "eps_sizing": eps}


def summarize_gate(split):
    G = load("gate", split)
    out = []
    for R in G:
        for c in R["cells"]:
            infeasible_sim = c["outage_at_Cper"] > 1e-9
            analytic = c["c"] > c["c_breakeven"] + 1e-12
            out.append({k: R[k] for k in ("site", "season", "r", "l", "m")} | c |
                       {"infeasible_sim": infeasible_sim, "infeasible_analytic": analytic,
                        "agree": infeasible_sim == analytic})
    return out


def summarize_throttle(split):
    Tt = load("throttle", split)
    rows = []
    for R in Tt:
        cp = R["C_per8"]
        for row in R["rows"]:
            rec = {k: R[k] for k in ("site", "season", "r", "l", "m")} | {"C_rel": row["C"] / cp if cp else None}
            for n, v in row["policies"].items():
                rec[n] = v["replay"]
                rec[n + "_outage"] = v["outage"]
            rows.append(rec)
    return {"rows": rows}


def describe(vals):
    v = np.asarray([x for x in vals if x is not None and np.isfinite(x)], float)
    if v.size == 0:
        return None
    return {"n": int(v.size), "min": float(v.min()), "p50": float(np.median(v)), "max": float(v.max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    a = ap.parse_args()
    out = {"split": a.split}
    for st, fn in (("main", summarize_main), ("frontier", summarize_frontier), ("gate", summarize_gate),
                   ("throttle", summarize_throttle)):
        try:
            out[st] = fn(a.split)
        except Exception as e:  # stage not run yet
            out[st] = {"error": repr(e)}
    p = cfg.RES / f"summary_{a.split}.json"
    p.write_text(json.dumps(out, default=lambda o: None if (isinstance(o, float) and not np.isfinite(o)) else o))
    print("wrote", p)


if __name__ == "__main__":
    main()
