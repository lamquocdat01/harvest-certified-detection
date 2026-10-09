#!/usr/bin/env python3
"""gen_supp.py (topic 40): tables of the supplementary material -> submission_package/IoTJ/latex/supp_tables.tex.
Every number comes from a results JSON (no hand typing)."""
from __future__ import annotations

import json
import pathlib
from collections import defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RES = ROOT / "results"
LATEX = ROOT / "submission_package" / "IoTJ" / "latex"


def J(n):
    p = RES / n
    return json.loads(p.read_text()) if p.exists() else None


def esc(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def num(v, d=3):
    if v is None:
        return "--"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, np.integer)):
        return f"{v:,}".replace(",", "{,}")
    return f"{v:.{d}f}"


def table(caption, label, head, rows, spec=None):
    spec = spec or "@{}" + "l" * len(head) + "@{}"
    L = [r"\begin{table}[!ht]\centering\footnotesize\caption{" + caption + r"}\label{" + label + "}",
         r"\begin{tabular}{" + spec + r"}\toprule", " & ".join(head) + r"\\\midrule"]
    L += [" & ".join(r) + r"\\" for r in rows]
    L += [r"\bottomrule\end{tabular}\end{table}"]
    return "\n".join(L)


def prereg():
    SC = J("prereg_score_test.json")
    rows = []
    for k, v in SC.items():
        if not isinstance(v, dict) or "verdict" not in v:
            continue
        det = {kk: vv for kk, vv in v.items() if kk != "verdict"}
        txt = "; ".join(f"{kk}={num(vv) if not isinstance(vv, (dict, list)) else '(see JSON)'}"
                        for kk, vv in det.items() if not isinstance(vv, (dict, list)))
        rows.append([k, v["verdict"], r"\parbox[t]{0.68\textwidth}{\raggedright " + esc(txt) + "}"])
    return table(r"Scoring of PREREG v1 (H1--H7) on TEST; dictionary-valued details are in "
                 r"\texttt{results/prereg\_score\_test.json}", "tab:s_prereg", ["", "Verdict", "Scalar details"],
                 rows, "@{}llp{0.7\\textwidth}@{}")


def exploratory():
    X, XB = J("exploratory_q2_test.json"), J("exploratory_q2_boot_test.json")
    E1, E2, E3 = X["E1"], X["E2"], X["E3"]
    rows = [["E1", "FAIL", f"share $\\Delta_1\\ge-0.005$: {num(E1['share_ge_-0.005'])}; median $|\\Delta_1|$: "
             f"{num(E1['d_K_minus_perabar']['median_abs'])}; Holm-significant wrong sign: "
             f"{XB['holm_E1_K_minus_perabar']['n_sig_wrong_sign']}/25"]]
    for k, v in E2["predictors"].items():
        rows.append(["E2" if k.startswith("T1") else "", "FAIL" if k.startswith("T1") else "(not scored)",
                     esc(k) + f": $R^2$ (identity line) {num(v['R2_45'], 2)}, Pearson $r^2$ {num(v['pearson_r2'], 2)}, "
                     f"median predicted {num(v['median_pred'])}"])
    for d in ("d0", "d5", "d10"):
        v = E3[f"per_amax_{d}"]
        rows.append(["E3" if d == "d0" else "", "FAIL" if d == "d0" else "(secondary)",
                     f"$\\delta$={d[1:]}\\,\\%: better than both {num(v['share_le_both'])}, outage$>0$ "
                     f"{num(v['share_outage_gt0'])}, median minus blackout {num(v['median_minus_blk'])}"])
    rows.append(["", "", f"E3 population {num(E3['n_feasible'])} cases; excluded ($a_{{\\max}}=0$) "
                         f"{num(E3['n_excluded_amax0'])}; bootstrap wrong sign "
                         f"{XB['holm_E3_K_minus_amax']['n_sig_wrong_sign']}/25 (vs Kansal), "
                         f"{XB['holm_E3_blk_minus_amax']['n_sig_wrong_sign']}/25 (vs blackout)"])
    return table("Exploratory predictions E1--E3 (PREREG v1.1, registered after TEST, before the stage was run)",
                 "tab:s_explore", ["", "Verdict", "Details"], rows, "@{}llp{0.72\\textwidth}@{}")


def interp():
    I = J("interp_sensitivity_test.json")
    rows = [[esc(x["site"]), x["season"], num(x["zoh"]["miss_per8_at_half"], 4), num(x["linear"]["miss_per8_at_half"], 4),
             num(100 * x["rel_diff_Cstar"], 3)] for x in I]
    return table(r"Interpolation of satellite steps to 1-min sub-steps: zero-order hold vs linear (TEST)",
                 "tab:s_interp", ["Site", "Season", "miss (zoh)", "miss (linear)", r"$\Delta C^*$ [\%]"], rows)


def block():
    out = []
    for split in ("all", "test"):
        B = J(f"sizing_block_sens_{split}.json")
        if not B:
            out.append(r"\noindent[[PENDING block sensitivity " + split + "]]")
            continue
        rows = []
        for r in B["rows"]:
            if abs(r["m"] - 0.25) > 1e-9:
                continue
            rows.append([esc(r["site"]), r["season"], num(r["Cstar_J"] / 1e3, 2)] +
                        [f"{num(r[f'b{b}']['ci_J'][0] / 1e3, 2)}--{num(r[f'b{b}']['ci_J'][1] / 1e3, 2)}"
                         + ("" if r[f"b{b}"]["contains"] else r"$^\dagger$") for b in (7, 14, 30)])
        s = B["summary"]
        cap = (f"Block-length sensitivity of the 95\\,\\% interval of $C^*$ [kJ], class-A node, $m=0.25$, "
               f"{'full year' if split == 'all' else 'TEST months'}. $^\\dagger$: interval excludes the point "
               f"estimate (all $m$: {s['b7']['n_exclude']}, {s['b14']['n_exclude']}, {s['b30']['n_exclude']} of "
               f"{s['b7']['n']} for 7, 14, 30 days). Switch to subsampling: "
               f"{'yes' if B['switch_to_subsampling'] else 'no'} (rule: exclusions at both 14 and 30 days). "
               f"Median bootstrap/point ratio: {s['b7']['median_boot_over_point']:.2f}, "
               f"{s['b14']['median_boot_over_point']:.2f}, {s['b30']['median_boot_over_point']:.2f}; a ratio near 1 "
               f"at 30 days reflects a nearly degenerate resampling of a season that is only a few blocks long")
        out.append(table(cap, f"tab:s_block_{split}", ["Site", "Season", "$C^*$", "7 d", "14 d", "30 d"], rows))
    return "\n\n".join(out)


def products():
    F = J("F5_sizing_all.json")
    R = {(x["site"], x["season"], x["m"]): x for x in F["rows"]}
    rows = []
    for city in ("Madrid", "Uppsala"):
        for sea in ("DJF", "MAM", "JJA", "SON"):
            a, b = R[(f"{city}-MSG", sea, 0.25)], R[(f"{city}-SARAH3", sea, 0.25)]
            rows.append([city, sea, num(a["Cstar_J"] / 1e3, 2), num(b["Cstar_J"] / 1e3, 2),
                         num(a["Cstar_J"] / b["Cstar_J"], 2)])
    return table("Satellite product sensitivity: $C^*$ [kJ] from MSG and SARAH-3 (full year, class-A node, $m=0.25$)",
                 "tab:s_products", ["City", "Season", "MSG", "SARAH-3", "ratio"], rows)


def monthly_test():
    F = J("F5_sizing_test.json")
    rows = [[esc(x["site"]), x["season"], num(x["days"], 0), num(x["Cstar_J"] / 1e3, 2),
             f"{num(x['Cstar_J_CI95'][0] / 1e3, 2)}--{num(x['Cstar_J_CI95'][1] / 1e3, 2)}",
             num(x["TS_over_Cstar"], 2)] for x in F["rows"] if abs(x["m"] - 0.25) < 1e-9]
    return table("Pre-registered sizing on the TEST months only (H7; one or two months per season)",
                 "tab:s_monthly", ["Site", "Season", "Days", "$C^*$ [kJ]", "95\\,\\% CI", "$C_{TS}/C^*$"], rows)


def grid_r():
    S = J("summary_test.json")
    d = defaultdict(lambda: defaultdict(list))
    for x in S["main"]["baselines"]:
        g = "indoor" if x["site"].startswith("Setup") else x["site"].split("-")[0]
        for k in ("C*/C_avgday", "C*/C_buchli_daily"):
            v = x[k]
            if v is not None and np.isfinite(v):
                d[(x["r"], k)][g].append(v)
    rows = []
    for r in sorted(set(k[0] for k in d)):
        rows.append([num(r, 1)] + [num(float(np.median(d[(r, "C*/C_avgday")][g])), 2)
                                   for g in ("HCMC", "Madrid", "Uppsala", "indoor")] +
                    [num(float(np.median(d[(r, "C*/C_buchli_daily")][g])), 2) if d[(r, "C*/C_buchli_daily")][g] else "--"
                     for g in ("HCMC", "Madrid", "Uppsala", "indoor")])
    return table(r"Median $C^*/C_{\mathrm{avg\text{-}day}}$ and $C^*/C_{\mathrm{Buchli}}$ by $r$ "
                 r"(all $\tilde\ell$, $m$; TEST)", "tab:s_grid",
                 ["$r$", "AD HCMC", "AD Mad.", "AD Upp.", "AD in", "Bu HCMC", "Bu Mad.", "Bu Upp.", "Bu in"],
                 rows)


def main():
    parts = [prereg(), exploratory(), monthly_test(), products(), block(), interp(), grid_r()]
    (LATEX / "supp_tables.tex").write_text("% GENERATED by code/paper/gen_supp.py\n" + "\n\n".join(parts) + "\n",
                                           encoding="utf-8")
    print("supp_tables.tex written")


if __name__ == "__main__":
    main()
