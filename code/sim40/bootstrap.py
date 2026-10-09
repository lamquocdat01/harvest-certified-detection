"""Bootstrap helpers: moving-block (7-day, circular) over days for energy quantities, by-video for miss;
B = 1000, seed 42; Holm step-down for families of sign tests."""
from __future__ import annotations

import numpy as np

from . import config as cfg
from .events import DurationLaw, load_corpus, video_split

DAY = 1440


def day_block_resample(h, rng, block_days=7):
    days = h.size // DAY
    H = h[: days * DAY].reshape(days, DAY)
    nb = int(np.ceil(days / block_days))
    starts = rng.integers(0, days, nb)
    idx = (starts[:, None] + np.arange(block_days)[None, :]).ravel()[:days] % days
    return H[idx].ravel()


def video_laws(split=None, B=cfg.B_BOOT, seed=cfg.SEED):
    """B resampled duration laws (resample videos with replacement)."""
    ev = load_corpus()
    key = (ev.dataset + "/" + ev.video).values
    if split in ("train", "test"):
        tr = video_split(ev)
        sel = np.isin(key, list(tr)) if split == "train" else ~np.isin(key, list(tr))
        ev, key = ev[sel], key[sel]
    vids = np.unique(key)
    groups = {v: ev.duration.values[key == v] for v in vids}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(B):
        pick = rng.choice(vids, vids.size, replace=True)
        out.append(DurationLaw(np.concatenate([groups[v] for v in pick])))
    return out


def ci(x, alpha=0.05):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return [None, None]
    return [float(np.quantile(x, alpha / 2)), float(np.quantile(x, 1 - alpha / 2))]


def holm(pvals, alpha=0.05):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = p.size
    rej = np.zeros(m, bool)
    for i, k in enumerate(order):
        if p[k] <= alpha / (m - i):
            rej[k] = True
        else:
            break
    return rej


def boot_p_sign(samples, expected_sign):
    """One-sided bootstrap p-value for H0: sign opposite to expected (share of resamples with wrong sign)."""
    s = np.asarray(samples, float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return 1.0
    wrong = (s <= 0).mean() if expected_sign > 0 else (s >= 0).mean()
    if wrong > 0:
        return float(wrong)
    # no resample with the wrong sign: normal approximation of the bootstrap distribution (pre-declared in
    # PREREG_40; the empirical floor 1/(B+1) would sit above Holm's first threshold for ~56 tests)
    from scipy.stats import norm
    sd = s.std(ddof=1)
    return float(norm.sf(abs(s.mean()) / sd)) if sd > 0 else 0.0


# ------------------------------------------------------------------ prereg bootstrap stage (H3/H4)
def run_boot(split, r=15.0, l=0.04, m=0.25, K=8, B=cfg.B_BOOT, B_ts=100, ts_cells=None):
    """Delta-miss (HF - periodic, by-video bootstrap), Delta-C (HF - periodic, 7-day block bootstrap) for
    every (site, season); C_TS/C_per at eps = eps*(1/K) (block bootstrap, B_ts) on `ts_cells`."""
    import json
    from . import energy as E, metrics as M, policies as P, traces as T
    from .events import law_for
    from .run_grid import c_min_policy
    law = law_for(split)
    laws = video_laws(split, B)
    rng = np.random.default_rng(cfg.SEED)
    a = 1.0 / K
    out = {"split": split, "r": r, "l": l, "m": m, "K": K, "B": B, "B_ts": B_ts, "cells": []}
    for site, sea in T.cells():
        g, _ = T.season_series(site, sea, split=split)
        h = T.scale_panel(g, r, l, m)
        sched = P.hf_schedule(h, r, l, a)
        rates, w = M.rate_histogram(np.ones(h.size), sched)
        dmiss = float(M.miss_from_hist(rates, w, law) - law.eps_star(a)[0])
        dmiss_b = [float(M.miss_from_hist(rates, w, Lb) - Lb.eps_star(a)[0]) for Lb in laws]
        Cp, Ch = E.C_periodic(h, P.N_SUB, r, l, a), E.C_schedule(h, P.N_SUB, r, l, sched)
        dC_b = []
        for _ in range(B):
            hb = day_block_resample(h, rng)
            sb = P.hf_schedule(hb, r, l, a)
            cp, ch = E.C_periodic(hb, P.N_SUB, r, l, a), E.C_schedule(hb, P.N_SUB, r, l, sb)
            dC_b.append((ch - cp) / cp if np.isfinite(cp) and np.isfinite(ch) else np.nan)
        rec = {"site": site, "season": sea, "dmiss": dmiss, "dmiss_ci": ci(dmiss_b),
               "p_dmiss_le0": boot_p_sign(dmiss_b, +1),
               "dC_rel": (Ch - Cp) / Cp if np.isfinite(Cp) and np.isfinite(Ch) else None, "dC_rel_ci": ci(dC_b),
               "p_dC_ge0": boot_p_sign(dC_b, -1)}
        if ts_cells and (site, sea) in ts_cells:
            eps = float(law.eps_star(a)[0]) + 1e-9

            def ratio(hh):
                cp = E.C_periodic(hh, P.N_SUB, r, l, a)
                if not np.isfinite(cp):
                    return np.nan

                def ok(C):
                    x = P.taut(hh, r, l, C)
                    return x is not None and M.summarize(*x, law)["miss"] <= eps
                return c_min_policy(ok, cp * 1.01) / cp
            rec["TS_over_per"] = ratio(h)
            tb = [ratio(day_block_resample(h, rng)) for _ in range(B_ts)]
            rec["TS_over_per_ci"] = ci(tb)
            rec["p_TS_ge_per"] = boot_p_sign([1 - x for x in tb], +1)
        out["cells"].append(rec)
    ps = [c["p_dmiss_le0"] for c in out["cells"]] + [c["p_dC_ge0"] for c in out["cells"]] + \
         [c["p_TS_ge_per"] for c in out["cells"] if "p_TS_ge_per" in c]
    rej = holm(ps)
    out["holm"] = {"n_tests": len(ps), "n_rejected": int(rej.sum()), "all_rejected": bool(rej.all())}
    (cfg.RES / f"boot_{split}.json").write_text(json.dumps(out, indent=1, default=lambda o: None))
    return out


TS_CELLS = [("HCMC", "SON"), ("Madrid-MSG", "DJF"), ("Madrid-SARAH3", "DJF"), ("Uppsala-MSG", "DJF"),
            ("Uppsala-SARAH3", "DJF"), ("SetupC", "ALL")]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--B", type=int, default=cfg.B_BOOT)
    ap.add_argument("--B_ts", type=int, default=100)
    a_ = ap.parse_args()
    o = run_boot(a_.split, B=a_.B, B_ts=a_.B_ts, ts_cells=TS_CELLS)
    print(o["holm"])
