"""Every number that may appear in the paper -> results/numbers.json (single source of truth).
python -m sim40.numbers --split test
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import config as cfg
from .analyze import describe
from .events import law_for


def grp(site):
    return "indoor" if site.startswith("Setup") else ("outdoor_" + site)


def by_group(rows, key, **sel):
    out = {}
    for x in rows:
        if any(abs(x.get(k, np.nan) - v) > 1e-9 for k, v in sel.items()):
            continue
        out.setdefault(grp(x["site"]), []).append(x.get(key))
    return {g: describe(v) for g, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    S = json.loads((cfg.RES / f"summary_{a.split}.json").read_text())
    law = law_for(a.split)
    lawall = law_for("all")
    N = {"split": a.split}
    N["corpus"] = json.loads((cfg.RES / "corpus_rebuild_check.json").read_text())
    N["F_D_all"] = {"P(D=1)": float(lawall.pmf[1]), "P(D<8)": float(lawall.pmf[:8].sum()), "E[D]": lawall.mean,
                    "eps_star": {K: float(lawall.eps_star(1 / K)[0]) for K in (2, 4, 8, 16, 32, 64)},
                    "a_eps": {e: float(lawall.a_eps(e)) for e in (0.2, 0.3, 0.4, 0.5, 0.6, 0.75)}}
    N["F_D_split"] = {"eps_star": {K: float(law.eps_star(1 / K)[0]) for K in (4, 8, 16, 64)}}
    M = S["main"]
    N["n_combos_main"] = M["n_combos"]
    N["F2_violations"] = M["F2"]
    b = M["baselines"]
    N["baselines_ratio"] = {k: by_group(b, k) for k in ("C*/C_kansal_tight", "C*/C_kansal_mean", "C*/C_avgday",
                                                         "C*/C_buchli_daily", "C*/C_3day", "C*_days")}
    N["baselines_ratio_r15_l0.04"] = {k: by_group(b, k, r=15.0, l=0.04) for k in
                                      ("C*/C_avgday", "C*/C_buchli_daily", "C*/C_3day")}
    f6 = M["F6"]
    N["F6_thr8to64_minus_blackout"] = by_group(f6, "d_miss_thr_minus_blackout")
    if "rows" in S.get("throttle", {}):
        T = S["throttle"]["rows"]
        for n in ("thr_K16_5/10", "thr_K16_20/50", "thr_K64_5/10", "thr_K64_20/50", "thr_K32_10/20", "kansal_ewma"):
            vals = [x[n] - x["blackout_K8"] for x in T if n in x and 0 < x.get("blackout_K8_outage", 0) < 1]
            N.setdefault("F6_throttle_minus_blackout_when_blackout", {})[n] = describe(vals)
    F = S["frontier"]
    N["F3_equal_a_K8"] = {"dmiss_hf_minus_per": by_group([x for x in F["equal_a"] if x["K"] == 8], "dmiss_hf_minus_per"),
                          "C_hf_over_per": by_group([x | {"q": x["C_hf"] / x["C_per"]} for x in F["equal_a"] if x["K"] == 8], "q")}
    N["F3_eps_sizing_TS_over_per"] = {str(e): by_group([x for x in F["eps_sizing"] if x["eps"] == e], "TS_over_per")
                                      for e in sorted(set(x["eps"] for x in F["eps_sizing"]))}
    N["F3_TS_le_per_violations"] = int(sum(1 for x in F["eps_sizing"] if x["TS_over_per"] > 1 + 0.02))
    G = S["gate"]
    N["F4_gate_analytic_vs_sim_agree"] = {"n": len(G), "agree": int(sum(x["agree"] for x in G))}
    try:
        F5 = json.loads((cfg.RES / f"F5_sizing_{a.split}.json").read_text())
        N["F5"] = {"node": F5["node"], "Cstar_J": by_group(F5["rows"], "Cstar_J"),
                   "TS_over_Cstar": by_group(F5["rows"], "TS_over_Cstar")}
    except FileNotFoundError:
        N["F5"] = None
    (cfg.RES / ("numbers.json" if a.split == "test" else f"numbers_{a.split}.json")).write_text(
        json.dumps(N, indent=1, default=lambda o: None))
    print("ok")


if __name__ == "__main__":
    main()
