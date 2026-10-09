"""F5: absolute sizing table for the class-A node (GAP9 + HM0360, 10 fps; P0 ENERGY_MODEL_40, DOI
10.1007/978-3-031-91989-3_17): r = 14.3, e_idle = 0.248 mJ, leakage l = 0.036 (AVX SCC 10 F max DCL), K = 8.
Storage needs in J, in 10 F/3 V super-capacitors (0.5 C V^2 = 45 J) and in 18650 Li-ion cells (3.4 Ah x 3.6 V
= 44.1 kJ), with the three named baselines (PREREG R12) and a 7-day moving-block bootstrap (B = 1000) CI.
python -m sim40.sizing --split test
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import config as cfg
from . import energy as E
from . import policies as P
from . import metrics as M
from . import traces as T
from .bootstrap import ci, day_block_resample
from .events import law_for
from .run_grid import baselines, c_min_policy

R_A, L_A, EIDLE_J, K = 14.3, 0.036, 0.248e-3, 8
SUPERCAP_J = 0.5 * 10 * 3.0 ** 2
CELL18650_J = 3.4 * 3.6 * 3600


def run(split, B=cfg.B_BOOT):
    law = law_for(split)
    eps = float(law.eps_star(1 / K)[0]) + 1e-9   # same miss as periodic K = 8 (like-for-like)
    rng = np.random.default_rng(cfg.SEED)
    rows = []
    for site, sea in T.cells():
        g, meta = T.season_series(site, sea, split=split)
        for m in cfg.M_LEVELS:
            h = T.scale_panel(g, R_A, L_A, m)
            b = baselines(h, R_A, L_A, K)
            Cs = b["C_star"]

            def ok(C):
                x = P.taut(h, R_A, L_A, C)
                return x is not None and M.summarize(*x, law)["miss"] <= eps
            C_ts = c_min_policy(ok, Cs * 1.01) if np.isfinite(Cs) else np.inf
            boot = [E.C_periodic(day_block_resample(h, rng), P.N_SUB, R_A, L_A, 1 / K) for _ in range(B)]
            J = lambda c: c * EIDLE_J if np.isfinite(c) else None  # noqa: E731
            rows.append({"site": site, "season": sea, "m": m, "days": meta["days"],
                         "Cstar_J": J(Cs), "Cstar_J_CI95": [J(v) if v is not None else None for v in ci(boot)],
                         "C_TS_at_eps*_K8_J": J(C_ts), "TS_over_Cstar": (C_ts / Cs) if np.isfinite(Cs) and np.isfinite(C_ts) else None, "eps*_K8": float(law.eps_star(1 / K)[0]),
                         "Cstar_supercaps_10F": J(Cs) / SUPERCAP_J if np.isfinite(Cs) else None,
                         "Cstar_18650": J(Cs) / CELL18650_J if np.isfinite(Cs) else None,
                         "baselines_J": {k: J(b[k]) for k in ("C_kansal_tight", "C_kansal_mean", "C_avgday",
                                                              "C_buchli_daily", "C_3day")},
                         "daily_demand_J": b["daily_demand"] * EIDLE_J})
    out = {"split": split, "node": {"r": R_A, "l": L_A, "e_idle_J": EIDLE_J, "K": K, "fps": 10},
           "units": {"supercap_10F_3V_J": SUPERCAP_J, "cell_18650_J": CELL18650_J}, "rows": rows}
    (cfg.RES / f"F5_sizing_{split}.json").write_text(json.dumps(out, indent=1, default=lambda o: None))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--B", type=int, default=cfg.B_BOOT)
    a = ap.parse_args()
    run(a.split, a.B)
