"""Main grid (Viec 3) and its stages. One checkpoint JSON per (split, cell, r, l, m) -> restartable.

Stages
  main      policies x C grid: periodic K, throttle(8->64), harvest-following (a = 1/8), Kansal-EWMA,
            taut-string (energy-tunnel optimal), greedy a_max; floors; baselines; replay miss  (F1, F2, F6)
  frontier  equal-a comparison periodic vs harvest-following vs taut-string; eps-sizing C_LB <= C_TS <= C_per
            (F3, Theorem 2b) - subset r in {5, 15, 40}, l in {0, 0.04}
  gate      Corollary 3 map (F4): storage ratio and outage of a gate with cue cost c, rate rho * a_per
Usage: python -m sim40.run_grid --split train --stage main [--workers 3] [--quick]
RAM guard: a worker refuses to start a combo when free RAM < 6 GB; the pool stops submitting.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import psutil

from . import config as cfg
from . import energy as E
from . import metrics as M
from . import policies as P
from . import traces as T
from .events import law_for, load_corpus, video_split

RAM_MIN_GB = 6.0
N_SUB = P.N_SUB
DAY = 1440


def ram_ok():
    return psutil.virtual_memory().available / 2**30 >= RAM_MIN_GB


def durations_for(split):
    ev = load_corpus()
    if split in (None, "all"):
        return ev.duration.values
    tr = video_split(ev)
    key = ev.dataset + "/" + ev.video
    sel = key.isin(tr) if split == "train" else ~key.isin(tr)
    return ev.duration.values[sel.values]


# ------------------------------------------------------------------ baselines (PREREG R12)
def baselines(h, r, l, K=cfg.K_REF, n_day_rule=3):
    a = 1.0 / K
    e = 1.0 + l + a * (r - 1.0)
    days = h.size // DAY
    H = h[: days * DAY].reshape(days, DAY)
    avg = H.mean(0)
    C_star = E.C_periodic(h, N_SUB, r, l, a)
    C_avgday = E.storage_need_cyclic(N_SUB * (avg - e)) + (r - 1.0)                 # P0 "average day"
    C_buchli = E.storage_need_cyclic(N_SUB * (H.sum(1) - DAY * e))                  # daily-resolution deficit
    C_nday = n_day_rule * DAY * N_SUB * e
    # Kansal Thm 2.2: B0 >= eta*sigma2 + sigma3 (eta folded into h). sigma3 <= (r-1) for periodic demand.
    sig2_tight = E.storage_need_cyclic(N_SUB * (h - e))     # rho1 = rho2 + rho_leak (tightest admissible)
    sig2_mean = E.storage_need_cyclic(N_SUB * (h - h.mean()))  # rho1 = mean harvest rate
    return {"C_star": C_star, "C_avgday": C_avgday, "C_buchli_daily": C_buchli, "C_3day": C_nday,
            "C_kansal_tight": sig2_tight + (r - 1.0), "C_kansal_mean": sig2_mean + (r - 1.0),
            "e_slot_K": e, "daily_demand": DAY * N_SUB * e}


def c_grid(h, r, l):
    b = baselines(h, r, l)
    lo = 0.25 * min(b["C_avgday"], b["C_star"])
    hi = 2.0 * b["C_star"] if np.isfinite(b["C_star"]) else 50 * b["C_avgday"]
    return np.geomspace(lo, hi, cfg.N_C), b


def _pack(s, extra=None):
    out = {k: v for k, v in s.items() if not k.startswith("_")}
    if extra:
        out.update(extra)
    return out


def run_main(site, season, r, l, m, split, quick=False):
    law = law_for(split)
    lawK = law.conditional(cfg.K_REF)
    D = durations_for(split)
    g, meta = T.season_series(site, season, split=split)
    h = T.scale_panel(g, r, l, m)
    Cs, base = c_grid(h, r, l)
    if quick:
        Cs = Cs[::4]
    Cper = {K: E.C_periodic(h, N_SUB, r, l, 1.0 / K) for K in cfg.K_LEVELS}
    a_bal = max((h.mean() - 1.0 - l) / (r - 1.0), 0.0)
    rng = np.random.default_rng(cfg.SEED)
    rows = []
    for ci, C in enumerate(Cs):
        a_bound = E.amax_cyclic_bound(h, N_SUB, r, l, C)
        floor_E = float(law.eps_star(a_bound)[0]) if np.isfinite(a_bound) else None
        pol = {}
        for K in cfg.K_LEVELS:
            pol[f"periodic_K{K}"] = (P.periodic(h, r, l, C, K), K)
        pol["throttle_8to64"] = (P.throttle(h, r, l, C, 8, 64), 8)
        pol["hf_a1/8"] = (P.harvest_following(h, r, l, C, 1.0 / 8), 8)
        pol["kansal_ewma"] = (P.kansal_ewma(h, r, l, C), 8)
        pol["taut"] = (P.taut(h, r, l, C), 8)
        pol["greedy_amax"] = (P.greedy(h, r, l, C), 8)
        res = {}
        for name, (x, Kn) in pol.items():
            if x is None:
                res[name] = None
                continue
            on, rt = x
            s = M.summarize(on, rt, law, Kn)
            rm, ne = M.replay_miss(on, rt, D, 100_000, rng)
            # floors: Thm 1 on the run's own mean rate; Prop 2' (blackout) on-time decomposition
            a_on = s["a_bar_on"]
            pi = s["outage_frac"]
            floor_T1 = float(law.eps_star(s["a_bar"])[0])
            floor_bo = float(pi + (1 - pi) * law.eps_star(a_on)[0]) if pi < 1 else 1.0
            bnd = s["n_outages"] * law.mean / (h.size * N_SUB)       # Remark 4 boundary term
            extra = {"replay_miss": rm, "replay_n": ne, "floor_T1": floor_T1, "floor_blackout": floor_bo,
                     "boundary_term": bnd, "no_outage": pi < 1e-9}
            if s["outage_frac"] < 1e-9 and floor_E is not None:
                extra["floor_E"] = floor_E
            if ci in (0, int(np.searchsorted(Cs, Cper[8])) if np.isfinite(Cper[8]) else -1, len(Cs) - 1):
                rr, ww = s["_hist"]
                extra["hist"] = [np.round(rr, 6).tolist(), np.round(ww, 8).tolist()] if rr.size <= 512 else None
            res[name] = _pack(s, extra)
        rows.append({"C": float(C), "a_bound": a_bound, "floor_E": floor_E, "policies": res})
    return {"site": site, "season": season, "r": r, "l": l, "m": m, "split": split, "meta": meta,
            "a_bal": a_bal, "floor_bal": float(law.eps_star(a_bal)[0]), "C_per": {str(k): v for k, v in Cper.items()},
            "baselines": base, "eps_star_K": {str(K): float(law.eps_star(1 / K)[0]) for K in cfg.K_LEVELS},
            "eps_star_K_DgeK": {str(K): float(lawK.eps_star(1 / K)[0]) for K in cfg.K_LEVELS},
            "rows": rows}


# ------------------------------------------------------------------ frontier (F3 / Theorem 2b)
def taut_at_rate(h, r, l, C, a):
    """Equal-a frontier point: discard a fixed fraction of the INCOMING harvest (h' = kappa h) so the cycle's
    activation budget is exactly a, then run the energy-tunnel optimal schedule on h'. Replayed on the true h
    (storage is then pointwise higher -> never an outage; surplus spills)."""
    kappa = (1.0 + l + a * (r - 1.0)) / h.mean()
    if kappa > 1.0 + 1e-12:
        return None
    sched = E.taut_schedule(kappa * h, float(N_SUB), float(r), float(l), float(C))
    if sched is None:
        return None
    on, rt, B = E.simulate_cyclic(h, sched, N_SUB, r, l, C, P.RESTART, mode=0)
    return on, rt


def c_min_policy(fn, C_hi, tol=0.01, it=40):
    """Smallest C (relative tol) at which fn(C) returns True; inf if not at C_hi."""
    if not fn(C_hi):
        return np.inf
    lo, hi = 0.0, C_hi
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        if fn(mid):
            hi = mid
        else:
            lo = mid
        if hi - lo <= tol * hi:
            break
    return hi


def run_frontier(site, season, r, l, m, split, eps_list=(0.45, 0.5, 0.55, 0.6, 0.66, 0.75)):
    law = law_for(split)
    g, meta = T.season_series(site, season, split=split)
    h = T.scale_panel(g, r, l, m)
    a_bal = (h.mean() - 1.0 - l) / (r - 1.0)
    out = {"site": site, "season": season, "r": r, "l": l, "m": m, "split": split, "a_bal": a_bal,
           "floor_bal": float(law.eps_star(max(a_bal, 0))[0]), "equal_a": {}, "eps_sizing": {}}
    for K in (4, 8, 16, 32):
        a = 1.0 / K
        Cp = E.C_periodic(h, N_SUB, r, l, a)
        sched = P.hf_schedule(h, r, l, a)
        Chf = E.C_schedule(h, N_SUB, r, l, sched)
        miss_hf = M.miss_from_hist(*M.rate_histogram(np.ones(h.size), sched), law)
        rec = {"a": a, "C_per": Cp, "miss_per": float(law.eps_star(a)[0]), "C_hf": Chf, "miss_hf": miss_hf,
               "frontier": []}
        if np.isfinite(Cp) and a <= a_bal:
            C_lo = max(Chf if np.isfinite(Chf) else Cp * 0.01, 1e-9) * 0.5
            for C in np.geomspace(C_lo, Cp * 1.2, 8):
                x = taut_at_rate(h, r, l, C, a)
                if x is None:
                    rec["frontier"].append({"C": float(C), "miss": None})
                    continue
                s = M.summarize(*x, law)
                rec["frontier"].append({"C": float(C), "miss": s["miss"], "a_bar": s["a_bar"],
                                        "outage": s["outage_frac"]})
        out["equal_a"][str(K)] = rec
    C_hi0 = 50 * baselines(h, r, l)["C_star"] if np.isfinite(baselines(h, r, l)["C_star"]) else 1e12
    for eps in eps_list:
        a_e = law.a_eps(eps)
        rec = {"a_eps": a_e}
        if not np.isfinite(a_e) or a_e > a_bal:
            rec.update({"C_LB": np.inf, "C_TS": np.inf, "C_per": np.inf, "note": "a_eps > energy balance"})
        else:
            rec["C_per"] = E.C_periodic(h, N_SUB, r, l, a_e)
            rec["C_LB"] = E.C_for_amax(h, N_SUB, r, l, a_e, C_hi0, tol=0.01)

            def ok_ts(C):
                x = P.taut(h, r, l, C)
                return x is not None and M.summarize(*x, law)["miss"] <= eps
            rec["C_TS"] = c_min_policy(ok_ts, min(C_hi0, rec["C_per"] * 1.01) if np.isfinite(rec["C_per"]) else C_hi0)
        out["eps_sizing"][str(eps)] = rec
    return out


# ------------------------------------------------------------------ gate map (F4 / Corollary 3)
def run_gate(site, season, r, l, m, split, rhos=(0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 4.0, 6.0), K=8):
    g, meta = T.season_series(site, season, split=split)
    h = T.scale_panel(g, r, l, m)
    a_per = 1.0 / K
    Cp = E.C_periodic(h, N_SUB, r, l, a_per)
    out = {"site": site, "season": season, "r": r, "l": l, "m": m, "split": split, "C_per": Cp, "cells": []}
    for c in (0.0,) + cfg.CUE_LEVELS:
        for rho in rhos:
            a_g = min(rho * a_per, 1.0)
            Cg = P.gate_storage_need(h, r, l, a_g, c)
            on, rt, B = E.simulate_cyclic(h, np.full(h.size, a_g), N_SUB, r, l + c, Cp, P.RESTART, mode=0) \
                if np.isfinite(Cp) else (np.zeros(h.size), None, None)
            out["cells"].append({"c": c, "rho": rho, "a_g": a_g, "C_gate": Cg,
                                 "ratio": (Cg / Cp) if np.isfinite(Cp) and np.isfinite(Cg) else None,
                                 "c_breakeven": (1 - rho) * a_per * (r - 1.0),
                                 "outage_at_Cper": float(1 - np.mean(on)),
                                 "infeasible_any_C": bool(not np.isfinite(Cg))})
    return out


# ------------------------------------------------------------------ throttling vs blackout (F6)
THROTTLES = {"thr_K16_5/10": (16, 0.05, 0.10), "thr_K16_20/50": (16, 0.20, 0.50),
             "thr_K64_5/10": (64, 0.05, 0.10), "thr_K64_20/50": (64, 0.20, 0.50),
             "thr_K32_10/20": (32, 0.10, 0.20)}


def run_throttle(site, season, r, l, m, split, K=8):
    law = law_for(split)
    D = durations_for(split)
    g, meta = T.season_series(site, season, split=split)
    h = T.scale_panel(g, r, l, m)
    Cs, base = c_grid(h, r, l)
    rng = np.random.default_rng(cfg.SEED)
    rows = []
    for C in Cs:
        res = {}
        on, rt = P.periodic(h, r, l, C, K)
        s = M.summarize(on, rt, law, K)
        res["blackout_K8"] = {"miss": s["miss"], "replay": M.replay_miss(on, rt, D, 100_000, rng)[0],
                              "outage": s["outage_frac"], "a_bar": s["a_bar"], "lat_max": s["latency"]["max"]}
        for name, (Kl, lo, hi) in THROTTLES.items():
            on, rt = P.throttle(h, r, l, C, K, Kl, lo, hi)
            s = M.summarize(on, rt, law, K)
            res[name] = {"miss": s["miss"], "replay": M.replay_miss(on, rt, D, 100_000, rng)[0],
                         "outage": s["outage_frac"], "a_bar": s["a_bar"], "lat_max": s["latency"]["max"]}
        on, rt = P.kansal_ewma(h, r, l, C)
        s = M.summarize(on, rt, law, K)
        res["kansal_ewma"] = {"miss": s["miss"], "replay": M.replay_miss(on, rt, D, 100_000, rng)[0],
                              "outage": s["outage_frac"], "a_bar": s["a_bar"], "lat_max": s["latency"]["max"]}
        rows.append({"C": float(C), "policies": res})
    return {"site": site, "season": season, "r": r, "l": l, "m": m, "split": split,
            "C_per8": E.C_periodic(h, N_SUB, r, l, 1.0 / K), "rows": rows}


# ------------------------------------------------------------------ driver
STAGES = {"main": run_main, "frontier": run_frontier, "gate": run_gate, "throttle": run_throttle}


def combos(stage, quick=False):
    cells = T.cells()
    if stage == "main":
        rs, ls, ms = cfg.R_LEVELS, cfg.L_LEVELS, cfg.M_LEVELS
    elif stage in ("frontier", "throttle"):
        rs, ls, ms = (5.0, 15.0, 40.0), (0.0, 0.04), cfg.M_LEVELS
    else:
        rs, ls, ms = (5.0, 15.0, 40.0), (0.04,), (0.25,)
    if quick:
        rs, ls, ms = (15.0,), (0.04,), (0.25,)
    return [(s, sea, r, l, m) for (s, sea) in cells for r in rs for l in ls for m in ms]


def ckpt_path(stage, split, c):
    s, sea, r, l, m = c
    d = cfg.CKPT / stage / split
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{s}_{sea}_r{r}_l{l}_m{m}.json"


def _job(stage, split, c, quick):
    if not ram_ok():
        return c, "ram"
    t = time.time()
    res = STAGES[stage](*c, split, **({"quick": quick} if stage == "main" else {}))
    res["elapsed_s"] = time.time() - t
    ckpt_path(stage, split, c).write_text(json.dumps(res, default=lambda o: None if (isinstance(o, float) and not np.isfinite(o)) else float(o)))
    return c, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train", choices=["train", "test", "all"])
    ap.add_argument("--stage", default="main", choices=list(STAGES))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    todo = [c for c in combos(a.stage, a.quick) if not ckpt_path(a.stage, a.split, c).exists()]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{a.stage}/{a.split}: {len(todo)} combos to run, workers={a.workers}, free RAM "
          f"{psutil.virtual_memory().available / 2**30:.1f} GB", flush=True)
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(_job, a.stage, a.split, c, a.quick) for c in todo]
        for f in as_completed(futs):
            c, st = f.result()
            done += 1
            if st == "ram":
                print("RAM guard tripped (< 6 GB free) at", c, "- stopping", flush=True)
                ex.shutdown(cancel_futures=True)
                break
            if done % 20 == 0 or done == len(todo):
                el = time.time() - t0
                print(f"  {done}/{len(todo)}  {el/60:.1f} min  eta {el/done*(len(todo)-done)/60:.1f} min  "
                      f"RAM free {psutil.virtual_memory().available / 2**30:.1f} GB", flush=True)


if __name__ == "__main__":
    main()
