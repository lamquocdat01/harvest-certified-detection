"""Score PREREG_40 v1 predictions H1-H7 against the TEST outputs -> results/prereg_score_<split>.json.
Criteria are copied from P1/PREREG_40.md (frozen, tag prereg-40-v1); this script only reads results.
Site groups for 'per group' criteria = HCMC, Madrid, Uppsala, indoor (the 4 groups named in H2c/H4c);
per-product values are reported alongside, and a criterion stated per group must hold for the pooled group.
python -m sim40.score_prereg --split test
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np

from . import config as cfg
from .bootstrap import holm

GROUPS = ("HCMC", "Madrid", "Uppsala", "indoor")
THR5 = ("thr_K16_5/10", "thr_K16_20/50", "thr_K64_5/10", "thr_K64_20/50", "thr_K32_10/20")


def g4(site):
    return "indoor" if site.startswith("Setup") else site.split("-")[0]


def med_by(rows, key, grp=g4):
    d = defaultdict(list)
    for x in rows:
        v = x[key] if isinstance(key, str) else key(x)
        if v is not None and np.isfinite(v):
            d[grp(x["site"])].append(v)
    return {g: float(np.median(v)) for g, v in d.items()}


def frac(vals, cond):
    v = [x for x in vals if x is not None and np.isfinite(x)]
    return (float(np.mean([cond(x) for x in v])) if v else float("nan")), len(v)


def h(ok, **kw):
    return {"verdict": "PASS" if ok else "FAIL"} | kw


def score(split):
    S = json.loads((cfg.RES / f"summary_{split}.json").read_text())
    B = json.loads((cfg.RES / f"boot_{split}.json").read_text())
    F5 = json.loads((cfg.RES / f"F5_sizing_{split}.json").read_text())
    out = {"split": split, "prereg": "P1/PREREG_40.md v1 (tag prereg-40-v1)"}

    # H1
    F2 = S["main"]["F2"]
    fw = {k: F2[k]["viol_familywise"] for k in ("T1_any_policy", "P2prime_blackout", "T2_energy_floor")}
    an = F2["T2_energy_floor_analytic"]["viol"]
    out["H1"] = h(all(v == 0 for v in fw.values()) and an == 0, familywise=fw, analytic=an,
                  n={k: F2[k]["n"] for k in F2})

    # H2
    b = S["main"]["baselines"]
    col = lambda k: [x[k] for x in b]  # noqa: E731
    f, n = frac(col("C*/C_kansal_tight"), lambda x: 0.99 <= x <= 1.01)
    out["H2a"] = h(f == 1.0, share_in_band=f, n=n)
    f, n = frac(col("C*/C_kansal_mean"), lambda x: x < 1)
    out["H2b"] = h(f >= 0.95, share_lt1=f, n=n)
    f, n = frac(col("C*/C_avgday"), lambda x: x > 1)
    md = med_by(b, "C*/C_avgday")
    band = {"HCMC": (1.1, 2.5), "Madrid": (2, 8), "Uppsala": (2, 10), "indoor": (5, 25)}
    mx_out = max(x["C*/C_avgday"] for x in b if g4(x["site"]) != "indoor")
    mx_in = max(x["C*/C_avgday"] for x in b if g4(x["site"]) == "indoor")
    ok = f == 1.0 and all(band[g][0] <= md[g] <= band[g][1] for g in GROUPS) and mx_out >= 15 and mx_in >= 30
    out["H2c"] = h(ok, share_gt1=f, n=n, medians=md, medians_product=med_by(b, "C*/C_avgday", lambda s: s),
                   max_outdoor=mx_out, max_indoor=mx_in)
    bb = [x for x in b if x["C*/C_buchli_daily"] is not None and np.isfinite(x["C*/C_buchli_daily"])]
    f, n = frac([x["C*/C_buchli_daily"] for x in bb], lambda x: x > 1)
    md = med_by(bb, "C*/C_buchli_daily")
    ok = f >= 0.95 and md["HCMC"] >= 2 and all(1 <= md[g] <= 2 for g in ("Madrid", "Uppsala", "indoor"))
    out["H2d"] = h(ok, share_gt1=f, n=n, medians=md, medians_product=med_by(bb, "C*/C_buchli_daily", lambda s: s))
    r3 = defaultdict(list)
    for x in b:
        r3[g4(x["site"])].append(x["C*/C_3day"])
    hc = float(np.mean(np.array(r3["HCMC"]) < 1))
    eu = {g: {"median": float(np.median(r3[g])), "max": float(np.max(r3[g]))} for g in ("Madrid", "Uppsala")}
    ind = float(np.mean(np.array(r3["indoor"]) > 1))
    ok = hc == 1.0 and all(v["median"] < 1.2 and v["max"] > 2 for v in eu.values()) and ind >= 0.40
    out["H2e"] = h(ok, HCMC_share_lt1=hc, HCMC_max=float(np.max(r3["HCMC"])), europe=eu, indoor_share_gt1=ind)

    # H3
    E = S["frontier"]["equal_a"]
    f, n = frac([x["dmiss_hf_minus_per"] for x in E if x["K"] in (4, 8, 16, 32)], lambda x: x > 0)
    md = med_by([x for x in E if x["K"] == 8], "dmiss_hf_minus_per")
    out["H3a"] = h(f == 1.0 and all(0.18 <= md[g] <= 0.32 for g in GROUPS), share_gt0=f, n=n, medians_K8=md,
                   min=float(min(x["dmiss_hf_minus_per"] for x in E if x["K"] in (4, 8, 16, 32))))
    fin = [x for x in E if np.isfinite(x["C_hf"]) and np.isfinite(x["C_per"])]
    f, n = frac([x["dC_hf_minus_per_rel"] for x in fin], lambda x: x < 0)
    md = med_by([x for x in fin if x["K"] == 8], lambda x: x["C_hf"] / x["C_per"])
    out["H3b"] = h(f >= 0.95 and all(0.1 <= md[g] <= 0.5 for g in GROUPS), share_lt0=f, n=n, medians_K8=md)
    cells = B["cells"]
    ps = [c["p_dmiss_le0"] for c in cells] + [c["p_dC_ge0"] for c in cells]
    ts = [c for c in cells if "p_TS_ge_per" in c]
    rej = holm(ps + [c["p_TS_ge_per"] for c in ts])
    nc = len(cells)
    r_dm, r_dc, r_ts = rej[:nc], rej[nc:2 * nc], rej[2 * nc:]
    sign_ok = all(c["dmiss"] > 0 and c["dC_rel"] < 0 for c in cells)
    out["H3c"] = h(nc == 25 and bool(r_dm.all() and r_dc.all()) and sign_ok, n_cells=nc, B=B["B"],
                   n_rej_dmiss=int(r_dm.sum()), n_rej_dC=int(r_dc.sum()), holm_tests=len(rej),
                   not_rejected=[f"{c['site']} {c['season']}" for c, a, d in zip(cells, r_dm, r_dc) if not (a and d)])

    # H4
    Z = S["frontier"]["eps_sizing"]
    f, n = frac([x["TS_over_per"] for x in Z], lambda x: x < 1)
    md = {str(e): med_by([x for x in Z if x["eps"] == e], "TS_over_per") for e in (0.5, 0.6)}
    out["H4a"] = h(f >= 0.95 and all(0.2 <= v[g] <= 0.7 for v in md.values() for g in GROUPS),
                   share_lt1=f, n=n, medians=md)
    f, n = frac([x["LB_over_TS"] for x in Z], lambda x: x <= 1.02)
    out["H4b"] = h(f == 1.0, share_le_1_02=f, n=n, max=float(np.nanmax([x["LB_over_TS"] for x in Z])))
    eps_hi = sorted(e for e in set(x["eps"] for x in Z) if e >= 0.6 - 1e-9)
    hi = {str(e): med_by([x for x in Z if x["eps"] == e], "LB_over_TS") for e in eps_hi}
    lo = med_by([x for x in Z if abs(x["eps"] - 0.45) < 1e-9], "LB_over_TS")
    ok = all(v[g] >= 0.9 for v in hi.values() for g in v) and sum(lo[g] < 0.9 for g in GROUPS) >= 3
    out["H4c"] = h(ok, medians_eps_ge_0_6=hi, medians_eps_0_45=lo)
    out["H4d"] = h(len(ts) == 6 and bool(r_ts.all()) and all(c["TS_over_per"] < 1 for c in ts),
                   B_ts=B.get("B_ts"), cells={f"{c['site']} {c['season']}": [c["TS_over_per"], bool(r)]
                                              for c, r in zip(ts, r_ts)})

    # H5
    T = [x for x in S["throttle"]["rows"] if 0 < x["blackout_K8_outage"] < 1]
    best = np.array([min(x[k] for k in THR5) - x["blackout_K8"] for x in T])
    naive = np.array([x["thr_K64_20/50"] - x["blackout_K8"] for x in T])
    out["H5a"] = h(np.mean(np.abs(best) <= 0.03) >= 0.95 and np.mean(best < -0.03) <= 0.01, n=len(T),
                   share_within_0_03=float(np.mean(np.abs(best) <= 0.03)),
                   share_better_gt_0_03=float(np.mean(best < -0.03)), median=float(np.median(best)))
    out["H5b"] = h(np.mean(naive > 0) >= 0.90 and 0.01 <= np.median(naive) <= 0.06,
                   share_gt0=float(np.mean(naive > 0)), median=float(np.median(naive)))
    mb = med_by([x | {"_b": v} for x, v in zip(T, best)], "_b")
    out["H5c"] = h(all(mb[g] > -0.01 for g in mb), medians_best_minus_blackout=mb)

    # H6
    G = S["gate"]
    agree = sum(x["agree"] for x in G)
    pairs = ok_p = 0
    key = defaultdict(dict)
    for x in G:
        key[(x["site"], x["season"], x["r"])][(x["c"], x["rho"])] = x["outage_at_Cper"]
    for d in key.values():
        cs, rs = sorted(set(c for c, _ in d)), sorted(set(r for _, r in d))
        for r in rs:
            for c0, c1 in zip(cs, cs[1:]):
                pairs += 1; ok_p += d[(c1, r)] >= d[(c0, r)] - 1e-9
        for c in cs:
            for r0, r1 in zip(rs, rs[1:]):
                pairs += 1; ok_p += d[(c, r1)] >= d[(c, r0)] - 1e-9
    out["H6"] = h(agree == len(G) and ok_p / pairs >= 0.95, agree=int(agree), n=len(G),
                  monotone_share=ok_p / pairs, pairs=pairs)

    # H7
    R = [x for x in F5["rows"] if abs(x["m"] - 0.25) < 1e-9]
    hcmc = [x["Cstar_J"] for x in R if x["site"] == "HCMC"]
    big = {p: sum(x["Cstar_J"] > 2000 for x in R if x["site"] == p)
           for p in ("Madrid-MSG", "Madrid-SARAH3", "Uppsala-MSG", "Uppsala-SARAH3")}
    big_pooled = {c: len({x["season"] for x in R if g4(x["site"]) == c and x["Cstar_J"] > 2000})
                  for c in ("Madrid", "Uppsala")}
    u = F5["units"]
    # a cell with C_TS = inf (TS never reaches eps*) counts as NOT satisfying the criterion (conservative)
    ts_share = float(np.mean([x["TS_over_Cstar"] is not None and x["TS_over_Cstar"] < 0.6 for x in R]))
    ok = (len(hcmc) == 4 and max(hcmc) < 1000 and all(v >= 2 for v in big_pooled.values())
          and all(x["Cstar_J"] < u["cell_18650_J"] for x in R) and all(x["Cstar_J"] > u["supercap_10F_3V_J"] for x in R)
          and ts_share >= 0.8)
    out["H7"] = h(ok, HCMC_Cstar_J=hcmc, seasons_gt_2kJ_pooled=big_pooled, seasons_gt_2kJ_product=big,
                  max_J=float(max(x["Cstar_J"] for x in R)), min_J=float(min(x["Cstar_J"] for x in R)),
                  TS_over_Cstar_lt_0_6_share=ts_share, n=len(R),
                  TS_infinite=[f"{x['site']} {x['season']}" for x in R if x["TS_over_Cstar"] is None])
    out["tally"] = {"PASS": sum(v["verdict"] == "PASS" for v in out.values() if isinstance(v, dict) and "verdict" in v),
                    "FAIL": [k for k, v in out.items() if isinstance(v, dict) and v.get("verdict") == "FAIL"]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    o = score(a.split)
    (cfg.RES / f"prereg_score_{a.split}.json").write_text(json.dumps(o, indent=1, default=float))
    for k, v in o.items():
        if isinstance(v, dict) and "verdict" in v:
            print(f"{k:5s} {v['verdict']}")
    print(o["tally"])


if __name__ == "__main__":
    main()
