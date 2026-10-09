"""CP-B1 Q4: block-length sensitivity of the moving-block bootstrap CI of C*_per(8) (class-A node, F5 rows).

For each (cell, m) the point estimate C* and the 95 % percentile CI under circular 7-, 14- and 30-day blocks
(B = 1000, seed 42). Reports, per block length, how many CIs do NOT contain the point estimate. C* is a
maximum-drawdown (max-type) statistic; resampling blocks breaks the longest deficit runs, which biases the
bootstrap distribution downwards. Decision rule (CP-B1 Q4): if CIs still exclude the estimate at BOTH 14 and
30 days, switch the C* interval to subsampling (see `subsample_ci`).
python -m sim40.sizing_sens --split all
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import config as cfg
from . import energy as E
from . import policies as P
from . import traces as T
from .bootstrap import ci, day_block_resample
from .sizing import EIDLE_J, K, L_A, R_A

BLOCKS = (7, 14, 30)
DAY = 1440


def subsample_ci(h, b_days, alpha=0.05):
    """m-out-of-n subsampling (Politis-Romano) for the max-drawdown C*: all n circular windows of b_days
    contiguous days; the statistic on a window is the NON-cyclic max drawdown started full (a b-day design
    horizon). Returns the empirical quantiles of the window statistic and the share of windows >= the full
    estimate. Reported as a descriptive interval for 'C* needed over a b-day stretch', not rescaled."""
    days = h.size // DAY
    H = h[: days * DAY]
    hh = np.r_[H, H]
    vals = []
    for d0 in range(days):
        seg = hh[d0 * DAY:(d0 + b_days) * DAY]
        net = P.N_SUB * (seg - (1.0 + L_A + (R_A - 1.0) / K))
        vals.append(E.max_drawdown(net) + (R_A - 1.0))
    v = np.array(vals)
    return [float(np.quantile(v, alpha / 2)), float(np.quantile(v, 1 - alpha / 2))], v


def run(split, B=cfg.B_BOOT):
    rows = []
    for site, sea in T.cells():
        g, meta = T.season_series(site, sea, split=split)
        for m in cfg.M_LEVELS:
            h = T.scale_panel(g, R_A, L_A, m)
            Cs = E.C_periodic(h, P.N_SUB, R_A, L_A, 1 / K)
            rec = {"site": site, "season": sea, "m": m, "days": meta["days"], "Cstar_J": Cs * EIDLE_J}
            for bl in BLOCKS:
                rng = np.random.default_rng(cfg.SEED)
                bs = [E.C_periodic(day_block_resample(h, rng, bl), P.N_SUB, R_A, L_A, 1 / K) for _ in range(B)]
                lo, hi = ci(bs)
                rec[f"b{bl}"] = {"ci_J": [lo * EIDLE_J, hi * EIDLE_J], "contains": bool(lo <= Cs <= hi),
                                 "median_ratio": float(np.median(bs) / Cs)}
            rows.append(rec)
            print(site, sea, m, round(rec["Cstar_J"]), {b: rec[f"b{b}"]["contains"] for b in BLOCKS}, flush=True)
    summ = {f"b{bl}": {"n": len(rows), "n_exclude": int(sum(not r[f"b{bl}"]["contains"] for r in rows)),
                       "median_boot_over_point": float(np.median([r[f"b{bl}"]["median_ratio"] for r in rows]))}
            for bl in BLOCKS}
    trigger = summ["b14"]["n_exclude"] > 0 and summ["b30"]["n_exclude"] > 0
    out = {"split": split, "B": B, "summary": summ, "switch_to_subsampling": trigger, "rows": rows}
    (cfg.RES / f"sizing_block_sens_{split}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(summ), "switch:", trigger)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all")
    ap.add_argument("--B", type=int, default=cfg.B_BOOT)
    a = ap.parse_args()
    run(a.split, a.B)
