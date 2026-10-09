"""Exploratory stage Q2 (post-TEST, PREREG_40 v1.1): is Kansal-EWMA's gain over blackout explained by its mean
activation (Theorem 1), and does periodic operation at a_max dominate?

New module; the code frozen at tag prereg-40-v1 is imported, never modified.
Policies per (cell, r, l, m, C), same population and C grid as the `throttle` stage:
  blackout_K8        periodic 1/8 with blackout (as in `throttle`)
  kansal_ewma        as in `throttle`
  per_abarK          periodic at the MEASURED mean activation a_bar of kansal_ewma in the same run (E1)
  per_amax_d{0,5,10} periodic at a_max(C) * (1 - delta), a_max = largest constant rate whose storage need
                     (Corollary 1.1, fluid + (r-1)) on the TRAIN months is <= C; same physical panel as TEST
                     (scale factor of the TEST months applied to the TRAIN irradiance) (E3)
Usage:
  python -m sim40.explore_q2 --part grid  [--workers 3]
  python -m sim40.explore_q2 --part boot          (25 cells, r = 15, l = 0.04, m = 0.25, C = C*_per8 / 2)
  python -m sim40.explore_q2 --part analyze       -> results/exploratory_q2_test.json
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

from . import config as cfg
from . import energy as E
from . import metrics as M
from . import policies as P
from . import traces as T
from .bootstrap import boot_p_sign, ci, holm, video_laws
from .events import law_for
from .run_grid import c_grid, combos, durations_for, ram_ok

STAGE = "exploratory_q2"
SPLIT = "test"
K = 8
DELTAS = (0.0, 0.05, 0.10)
BOOT_SEL = {"r": 15.0, "l": 0.04, "m": 0.25, "C_frac": 0.5}


def h_pair(site, season, r, l, m, split=SPLIT):
    """TEST harvest (as in every TEST stage) and TRAIN harvest on the SAME physical panel.
    (split='train' is only for smoke tests: both members are then TRAIN.)"""
    g_te, _ = T.season_series(site, season, split=split)
    g_tr, _ = T.season_series(site, season, split="train")
    s = (1.0 + m) * (1.0 + l + (r - 1.0) / cfg.K_REF) / g_te.mean()
    return g_te * s, g_tr * s


def a_max_periodic(h, r, l, C, tol=1e-6):
    """Largest constant rate a in [0, 1] with C_periodic(h, a) <= C (0 if idle alone is infeasible)."""
    need = lambda a: E.C_periodic(h, P.N_SUB, r, l, a)  # noqa: E731
    if not need(0.0) <= C:
        return 0.0
    if need(1.0) <= C:
        return 1.0
    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if need(mid) <= C:
            lo = mid
        else:
            hi = mid
    return lo


def periodic_rate(h, r, l, C, a):
    on, rt, B = E.simulate_cyclic(h, np.full(h.size, a), P.N_SUB, r, l, C, P.RESTART, mode=0)
    return on, rt


def _rec(on, rt, law, D, rng, extra=None):
    s = M.summarize(on, rt, law, K)
    out = {"miss": s["miss"], "replay": M.replay_miss(on, rt, D, 100_000, rng)[0], "outage": s["outage_frac"],
           "a_bar": s["a_bar"], "floor_T1": float(law.eps_star(s["a_bar"])[0])}
    if extra:
        out.update(extra)
    return out, s


def run_cell(site, season, r, l, m, split=SPLIT):
    law = law_for(split)
    D = durations_for(split)
    h, h_tr = h_pair(site, season, r, l, m, split)
    Cs, _ = c_grid(h, r, l)                      # identical grid to the `throttle` stage
    rng = np.random.default_rng(cfg.SEED)
    rows = []
    for C in Cs:
        res = {}
        res["blackout_K8"], sb = _rec(*P.periodic(h, r, l, C, K), law, D, rng)
        pi = sb["outage_frac"]
        res["blackout_K8"]["floor_P2"] = float(pi + (1 - pi) * law.eps_star(1.0 / K)[0]) if pi < 1 else 1.0
        res["kansal_ewma"], sk = _rec(*P.kansal_ewma(h, r, l, C), law, D, rng)
        aK = sk["a_bar"]
        res["per_abarK"], _ = _rec(*periodic_rate(h, r, l, C, aK), law, D, rng, {"a_set": aK})
        am = a_max_periodic(h_tr, r, l, C)
        for d in DELTAS:
            a = am * (1.0 - d)
            res[f"per_amax_d{int(round(d * 100))}"], _ = _rec(*periodic_rate(h, r, l, C, a), law, D, rng,
                                                              {"a_set": a, "a_max_train": am})
        rows.append({"C": float(C), "policies": res})
    return {"site": site, "season": season, "r": r, "l": l, "m": m, "split": split,
            "C_per8": E.C_periodic(h, P.N_SUB, r, l, 1.0 / K), "rows": rows}


def ckpt(c):
    s, sea, r, l, m = c
    d = cfg.CKPT / STAGE / SPLIT
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{s}_{sea}_r{r}_l{l}_m{m}.json"


def _job(c):
    if not ram_ok():
        return c, "ram"
    t = time.time()
    res = run_cell(*c)
    res["elapsed_s"] = time.time() - t
    ckpt(c).write_text(json.dumps(res, default=lambda o: None if (isinstance(o, float) and not np.isfinite(o))
                                  else float(o)))
    return c, "ok"


def grid(workers=3):
    todo = [c for c in combos("throttle") if not ckpt(c).exists()]
    print(f"{STAGE}/{SPLIT}: {len(todo)} combos, workers={workers}", flush=True)
    t0, done = time.time(), 0
    with ProcessPoolExecutor(workers) as ex:
        futs = [ex.submit(_job, c) for c in todo]
        for f in as_completed(futs):
            c, st = f.result()
            done += 1
            if st == "ram":
                print("RAM guard tripped (< 6 GB free) at", c, "- stopping", flush=True)
                ex.shutdown(cancel_futures=True)
                break
            if done % 20 == 0 or done == len(todo):
                el = time.time() - t0
                print(f"  {done}/{len(todo)}  {el / 60:.1f} min  eta {el / done * (len(todo) - done) / 60:.1f} min",
                      flush=True)


def boot(B=cfg.B_BOOT):
    """By-video bootstrap (F_D resampled, energy fixed) of the analytic miss differences in 25 cells."""
    r, l, m = BOOT_SEL["r"], BOOT_SEL["l"], BOOT_SEL["m"]
    law = law_for(SPLIT)
    laws = video_laws(SPLIT, B)
    cells = []
    for site, sea in T.cells():
        h, h_tr = h_pair(site, sea, r, l, m)
        C = BOOT_SEL["C_frac"] * E.C_periodic(h, P.N_SUB, r, l, 1.0 / K)
        hist = {"blackout_K8": M.rate_histogram(*P.periodic(h, r, l, C, K)),
                "kansal_ewma": M.rate_histogram(*P.kansal_ewma(h, r, l, C))}
        aK = float(np.mean(np.prod(P.kansal_ewma(h, r, l, C), axis=0)))
        hist["per_abarK"] = M.rate_histogram(*periodic_rate(h, r, l, C, aK))
        am = a_max_periodic(h_tr, r, l, C)
        hist["per_amax_d0"] = M.rate_histogram(*periodic_rate(h, r, l, C, am))
        miss = lambda L, k: M.miss_from_hist(*hist[k], L)  # noqa: E731
        diffs = {"E1_K_minus_perabar": ("kansal_ewma", "per_abarK", +1),       # predicted >= 0
                 "E3_K_minus_amax": ("kansal_ewma", "per_amax_d0", +1),        # predicted >= 0
                 "E3_blk_minus_amax": ("blackout_K8", "per_amax_d0", +1)}      # predicted >= 0
        rec = {"site": site, "season": sea, "C": C, "a_bar_K": aK, "a_max_train": am,
               "miss": {k: miss(law, k) for k in hist}}
        for name, (x, y, sgn) in diffs.items():
            if name.startswith("E3") and am <= 0:          # E3 population: a_max_train > 0 only
                rec[name] = None
                continue
            v = miss(law, x) - miss(law, y)
            vb = [miss(L, x) - miss(L, y) for L in laws]
            # boot_p_sign(vb, s) is the p-value of H0 'sign is not s' (share of resamples against s), so the
            # p-value for a significant WRONG sign is boot_p_sign(vb, -sgn). (Fix 10-10-2026: the first run used
            # boot_p_sign(vb, sgn), i.e. it counted significant PREDICTED signs; kept as *.buggy_holm_direction.json)
            rec[name] = {"d": v, "ci": ci(vb), "p_wrong_sign": boot_p_sign(vb, -sgn),
                         "p_predicted_sign": boot_p_sign(vb, sgn)}
        cells.append(rec)
        print(site, sea, {k: (round(rec[k]["d"], 4) if rec[k] else None) for k in diffs}, flush=True)
    out = {"split": SPLIT, "B": B, **BOOT_SEL, "cells": cells}
    for name in ("E1_K_minus_perabar", "E3_K_minus_amax", "E3_blk_minus_amax"):
        # Holm over the 25 cells of each family: H0 'predicted sign holds'; a rejection = significant WRONG sign
        cc = [c for c in cells if c[name] is not None]
        rej = holm([c[name]["p_wrong_sign"] for c in cc]) if cc else np.zeros(0, bool)
        rp = holm([c[name]["p_predicted_sign"] for c in cc]) if cc else np.zeros(0, bool)
        out[f"holm_{name}"] = {"n": len(cc), "n_sig_wrong_sign": int(rej.sum()),
                               "cells": [f"{c['site']} {c['season']}" for c, x in zip(cc, rej) if x],
                               "n_sig_predicted_sign": int(rp.sum())}
    (cfg.RES / f"exploratory_q2_boot_{SPLIT}.json").write_text(json.dumps(out, indent=1, default=float))
    return out


def load_rows():
    rows = []
    for f in sorted((cfg.CKPT / STAGE / SPLIT).glob("*.json")):
        R = json.loads(f.read_text())
        for row in R["rows"]:
            p = row["policies"]
            rows.append({k: R[k] for k in ("site", "season", "r", "l", "m")} |
                        {"C_rel": row["C"] / R["C_per8"] if R["C_per8"] else None} | p)
    return rows


def r2_45(obs, pred):
    """R^2 of the prediction itself (45-degree line, no fitting): 1 - SS_res / SS_tot."""
    obs, pred = np.asarray(obs), np.asarray(pred)
    return float(1 - np.sum((obs - pred) ** 2) / np.sum((obs - obs.mean()) ** 2))


def analyze():
    rows = [x for x in load_rows() if 0 < x["blackout_K8"]["outage"] < 1]     # H5 population
    g = lambda pol, key="replay": np.array([x[pol][key] for x in rows])  # noqa: E731
    blk, ks, pa = g("blackout_K8"), g("kansal_ewma"), g("per_abarK")
    out = {"split": SPLIT, "n_cells": len(rows), "metric": "replay miss (100k real events); analytic in *_analytic"}
    # E1
    d1 = ks - pa
    out["E1"] = {"d_K_minus_perabar": {"median": float(np.median(d1)), "p05": float(np.percentile(d1, 5)),
                                       "p95": float(np.percentile(d1, 95)),
                                       "median_abs": float(np.median(np.abs(d1)))},
                 "share_ge_-0.005": float(np.mean(d1 >= -0.005)), "share_ge0": float(np.mean(d1 >= 0)),
                 "outage_perabar_minus_K": float(np.median(g("per_abarK", "outage") - g("kansal_ewma", "outage")))}
    da1 = g("kansal_ewma", "miss") - g("per_abarK", "miss")
    out["E1"]["analytic_share_ge_-0.005"] = float(np.mean(da1 >= -0.005))
    # E2
    dobs = ks - blk
    aK, aB = g("kansal_ewma", "a_bar"), g("blackout_K8", "a_bar")
    law = law_for(SPLIT)
    eps = lambda a: law.eps_star(np.asarray(a))  # noqa: E731
    pred = {"T1_both_abar (primary)": eps(aK) - eps(aB),
            "literal_eps(aK)-eps(1/8)": eps(aK) - float(eps(np.array([1 / K]))[0]),
            "floorK_minus_P2floor": eps(aK) - g("blackout_K8", "floor_P2")}
    out["E2"] = {"d_obs_median": float(np.median(dobs)),
                 "predictors": {k: {"R2_45": r2_45(dobs, v), "pearson_r2": float(np.corrcoef(dobs, v)[0, 1] ** 2),
                                    "median_pred": float(np.median(v)),
                                    "median_resid": float(np.median(dobs - v))} for k, v in pred.items()},
                 "a_bar_K_over_blk_median": float(np.median(aK / np.maximum(aB, 1e-12)))}
    # E3
    # E3 population: cells where idle-only operation is feasible on the TRAIN months (a_max_train > 0);
    # below that, Theorem 2's a_max is undefined and every policy has outages
    feas = g("per_amax_d0", "a_max_train") > 0
    out["E3"] = {"n_feasible": int(feas.sum()), "n_excluded_amax0": int((~feas).sum())}
    ks, blk = ks[feas], blk[feas]
    for d in DELTAS:
        k = f"per_amax_d{int(round(d * 100))}"
        pm = g(k)[feas]
        out["E3"][k] = {"share_le_K": float(np.mean(pm <= ks)), "share_le_blk": float(np.mean(pm <= blk)),
                        "share_le_both": float(np.mean((pm <= ks) & (pm <= blk))),
                        "share_outage_gt0": float(np.mean(g(k, "outage")[feas] > 1e-9)),
                        "median_outage": float(np.median(g(k, "outage")[feas])),
                        "median_minus_K": float(np.median(pm - ks)), "median_minus_blk": float(np.median(pm - blk))}
    # C_rel bands for the figure / text
    ks, blk = g("kansal_ewma"), g("blackout_K8")
    Cr = np.array([x["C_rel"] for x in rows])
    out["bands"] = {}
    for lo, hi in ((0, 0.1), (0.1, 0.5), (0.5, 1.01)):
        sel = (Cr >= lo) & (Cr < hi)
        out["bands"][f"{lo}-{hi}"] = {"n": int(sel.sum()), "K_minus_blk": float(np.median(dobs[sel])),
                                      "K_minus_perabar": float(np.median(d1[sel])),
                                      "amax0_minus_blk": float(np.median(g("per_amax_d0")[sel] - blk[sel]))}
    (cfg.RES / f"exploratory_q2_{SPLIT}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("grid", "boot", "analyze"), required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--B", type=int, default=cfg.B_BOOT)
    a = ap.parse_args()
    {"grid": lambda: grid(a.workers), "boot": lambda: boot(a.B), "analyze": analyze}[a.part]()


if __name__ == "__main__":
    main()
