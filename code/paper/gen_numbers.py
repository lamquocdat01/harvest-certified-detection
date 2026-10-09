#!/usr/bin/env python3
"""gen_numbers.py (topic 40): every number printed in the paper -> numbers.tex (+ sizing_table.tex) with a
provenance record per macro in results/numbers_provenance.json. No number is typed in main.tex.
Sources (all TEST unless stated): results/numbers.json, summary_test.json, prereg_score_test.json, boot_test.json,
exploratory_q2_test.json, exploratory_q2_boot_test.json, F5_sizing_all.json (12 months, descriptive),
sizing_block_sens_all.json, interp_sensitivity_test.json, corpus_rebuild_check.json.
Missing exploratory sources -> the macro prints [[PENDING ...]], which verify_render.py --final rejects.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
RES = ROOT / "results"
LATEX = ROOT / "submission_package" / "IoTJ" / "latex"
REPO_URL = r"\url{https://github.com/lamquocdat/harvest-certified-detection}"

MAC: dict[str, str] = {}
PROV: dict[str, dict] = {}


def J(name):
    p = RES / name
    return json.loads(p.read_text()) if p.exists() else None


def put(name, value, src, note=""):
    MAC[name] = value
    PROV[name] = {"value": value, "source": src, "note": note}


def f(x, d=2):
    return f"{x:.{d}f}"


def pct(x, d=0):
    return f"{100 * x:.{d}f}\\,\\%"


def thou(n):
    return f"{int(n):,}".replace(",", "{,}")


def g4(site):
    return "indoor" if site.startswith("Setup") else site.split("-")[0]


def main():
    N, S, SC, B = J("numbers.json"), J("summary_test.json"), J("prereg_score_test.json"), J("boot_test.json")
    corpus = N["corpus"]
    put("nVid", str(corpus["n_videos"]), "numbers.json:corpus.n_videos")
    put("nEv", thou(corpus["n_events"]), "numbers.json:corpus.n_events")
    fd = N["F_D_all"]
    put("pDone", f(fd["P(D=1)"], 3), "numbers.json:F_D_all.P(D=1)")
    put("pDltEight", pct(fd["P(D<8)"], 1), "numbers.json:F_D_all.P(D<8)")
    put("ED", f(fd["E[D]"], 1), "numbers.json:F_D_all.E[D]")
    put("epsKeight", f(fd["eps_star"]["8"], 3), "numbers.json:F_D_all.eps_star.8")
    # presence gate (THEORY_40 sec. 6, rebuilt corpus)
    ev = json.loads((RES / "corpus_rebuild_check.json").read_text())
    import csv
    rows = list(csv.DictReader(open(RES / "event_corpus_40.csv", encoding="utf-8")))
    in_ev = sum(int(r["duration"]) for r in rows)
    frac = in_ev / ev["n_frames_total"]
    put("inEventFrac", pct(frac, 1), "event_corpus_40.csv sum(duration)/corpus n_frames_total")
    put("rhoPresence", f(frac * 8, 1), "inEventFrac x K=8")
    put("nTraceCells", "25", "traces.cells(): 5 outdoor products x 4 seasons + 5 indoor setups")

    # H1
    F2 = S["main"]["F2"]
    put("nTone", thou(F2["T1_any_policy"]["n"]), "summary_test.json:main.F2.T1_any_policy.n")
    put("nPtwo", thou(F2["P2prime_blackout"]["n"]), "summary_test.json:main.F2.P2prime_blackout.n")
    put("nTtwo", thou(F2["T2_energy_floor"]["n"]), "summary_test.json:main.F2.T2_energy_floor.n")
    tot = F2["T1_any_policy"]["n"] + F2["P2prime_blackout"]["n"] + F2["T2_energy_floor"]["n"]
    put("nFloorChecks", thou(tot), "sum of the three H1 families")
    put("zBonf", f(F2["T1_any_policy"]["z_bonferroni"], 1), "summary_test.json:main.F2.T1_any_policy.z_bonferroni")
    cap = (RES / "figs" / "F2_caption_test.txt").read_text().strip()
    names = {"T1_any_policy": "Theorem~\ref{thm:floor}", "P2prime_blackout": "Proposition~\ref{prop:blackout}",
             "T2_energy_floor": "Theorem~\ref{thm:energy}"}
    put("Ftwocaption", "Violations beyond the family-wise margin: " + "; ".join(
        f"{names[k]}: {F2[k]['viol_familywise']} of {thou(F2[k]['n'])}" for k in names) + ".",
        "summary_test.json:main.F2 (viol_familywise, n)")
    tally = SC["tally"]
    put("nPass", str(tally["PASS"]), "prereg_score_test.json:tally.PASS")
    put("nPred", str(tally["PASS"] + len(tally["FAIL"])), "prereg_score_test.json")
    put("tsUppFail", f(SC["H4a"]["medians"]["0.5"]["Uppsala"], 3), "prereg_score_test.json:H4a.medians.0.5.Uppsala")

    # H3 / boot
    cells = B["cells"]
    dm = [c["dmiss"] for c in cells]
    dc = [c["dC_rel"] for c in cells]
    put("dmissMin", f(min(dm)), "boot_test.json:cells[].dmiss min")
    put("dmissMax", f(max(dm)), "boot_test.json:cells[].dmiss max")
    put("dCMinPct", f"{-100 * max(dc):.0f}", "boot_test.json:cells[].dC_rel (smallest saving)")
    put("dCMaxPct", f"{-100 * min(dc):.0f}\\,\\%", "boot_test.json:cells[].dC_rel (largest saving)")
    put("nHolm", str(B["holm"]["n_tests"]), "boot_test.json:holm.n_tests")
    put("nBootCells", str(len(cells)), "boot_test.json:len(cells)")
    pmax = max(max(c["p_dmiss_le0"], c["p_dC_ge0"]) for c in cells)
    put("pMaxBoot", f"{pmax:.1e}".replace("e-0", r"\times10^{-").replace("e-", r"\times10^{-") + "}",
        "boot_test.json:max p")
    # H4
    h4 = SC["H4a"]["medians"]
    meds = [v for e in ("0.5", "0.6") for v in h4[e].values()]
    put("tsMedLo", f(min(meds)), "prereg_score_test.json:H4a.medians min")
    put("tsMedHi", f(max(meds)), "prereg_score_test.json:H4a.medians max")
    put("tsInvLo", f(1 / max(meds), 1), "1 / tsMedHi")
    put("tsInvHi", f(1 / min(meds), 1), "1 / tsMedLo")
    put("nEps", thou(SC["H4a"]["n"]), "prereg_score_test.json:H4a.n")
    hi = SC["H4c"]["medians_eps_ge_0_6"]
    lbmin = min(v for e in hi.values() for v in e.values())
    put("lbtsHi", f(lbmin, 3), "prereg_score_test.json:H4c min median eps>=0.6")
    put("lbtsGapPct", f"{100 * (1 - lbmin):.1f}\\,\\%", "1 - lbtsHi")
    lo = SC["H4c"]["medians_eps_0_45"].values()
    put("lbtsLoMin", f(min(lo)), "prereg_score_test.json:H4c.medians_eps_0_45 min")
    put("lbtsLoMax", f(max(lo)), "prereg_score_test.json:H4c.medians_eps_0_45 max")
    # H2
    h2c = SC["H2c"]["medians"]
    for k, g in (("avgHCMC", "HCMC"), ("avgMadrid", "Madrid"), ("avgUpp", "Uppsala"), ("avgIn", "indoor")):
        put(k, f(h2c[g], 1), f"prereg_score_test.json:H2c.medians.{g}")
    put("avgMaxOut", f(SC["H2c"]["max_outdoor"], 0), "prereg_score_test.json:H2c.max_outdoor")
    put("avgMaxIn", f(SC["H2c"]["max_indoor"], 0), "prereg_score_test.json:H2c.max_indoor")
    h2d = SC["H2d"]["medians"]
    put("buHCMC", f(h2d["HCMC"], 1), "prereg_score_test.json:H2d.medians.HCMC")
    oth = [h2d[g] for g in ("Madrid", "Uppsala", "indoor")]
    put("buLo", f(min(oth), 1), "H2d medians min (non-HCMC)")
    put("buHi", f(max(oth), 1), "H2d medians max (non-HCMC)")
    put("threeHCMCmax", f(SC["H2e"]["HCMC_max"]), "prereg_score_test.json:H2e.HCMC_max")
    put("threeUppMax", f(SC["H2e"]["europe"]["Uppsala"]["max"], 1), "prereg_score_test.json:H2e.europe.Uppsala.max")
    km = [v["p50"] for v in N["baselines_ratio"]["C*/C_kansal_mean"].values()]
    put("kmeanInvLo", f(1 / max(km), 1), "numbers.json:baselines_ratio.C*/C_kansal_mean p50 max -> inverse")
    put("kmeanInvHi", f(1 / min(km), 1), "numbers.json:baselines_ratio.C*/C_kansal_mean p50 min -> inverse")
    # H5
    put("nThr", thou(SC["H5a"]["n"]), "prereg_score_test.json:H5a.n")
    put("thrMedSigned", f"{SC['H5a']['median']:+.4f}", "prereg_score_test.json:H5a.median")
    put("naiveSharePct", pct(SC["H5b"]["share_gt0"], 1), "prereg_score_test.json:H5b.share_gt0")
    put("naiveMedSigned", f"{SC['H5b']['median']:+.3f}", "prereg_score_test.json:H5b.median")
    # H6
    put("nGate", thou(SC["H6"]["n"]), "prereg_score_test.json:H6.n")
    put("nGateAgree", thou(SC["H6"]["agree"]), "prereg_score_test.json:H6.agree")
    # F1: C*(16)/C*(8) in winter (r = 15, l = 0.04, m = 0.25, TEST)
    put("epsKsixteen", f(fd["eps_star"]["16"], 3), "numbers.json:F_D_all.eps_star.16")
    f1 = [x for x in S["main"]["F1"] if abs(x["r"] - 15) < 1e-9 and abs(x["l"] - 0.04) < 1e-9
          and abs(x["m"] - 0.25) < 1e-9 and x["season"] == "DJF"]
    rat = {x["site"]: x["C_per_days"]["16"] / x["C_per_days"]["8"] for x in f1}
    eu = [v for k, v in rat.items() if k != "HCMC"]
    put("ckWinter", f(1 / float(np.median(eu)), 1), "summary_test.json:main.F1 DJF, 1/median C*(16)/C*(8), Europe")
    put("ckHCMC", f(1 / rat["HCMC"], 1), "summary_test.json:main.F1 DJF, 1/(C*(16)/C*(8)), HCMC")
    # robustness
    I = J("interp_sensitivity_test.json")
    put("interpMax", pct(max(abs(x["rel_diff_Cstar"]) for x in I), 2), "interp_sensitivity_test.json max |rel_diff_Cstar|")

    # sizing table (12 months, descriptive)
    F5 = J("F5_sizing_all.json")
    if F5:
        sizing_table(F5)
        R = {(x["site"], x["season"]): x for x in F5["rows"] if abs(x["m"] - 0.25) < 1e-9}
        diffs = [abs(R[("Uppsala-MSG", s)]["Cstar_J"] / R[("Uppsala-SARAH3", s)]["Cstar_J"] - 1)
                 for s in ("DJF", "MAM", "JJA", "SON")]
        put("uppProdDiffMax", pct(max(diffs)), "F5_sizing_all.json Uppsala MSG/SARAH3 C* (m=0.25) max |ratio-1|")
        put("uppProdDiffMed", pct(float(np.median(diffs))), "same, median")
    else:
        for k in ("uppProdDiffMax", "uppProdDiffMed"):
            put(k, "[[PENDING F5 all]]", "missing")
        (LATEX / "sizing_table.tex").write_text("[[PENDING sizing table]]\n")
    BS = J("sizing_block_sens_all.json")
    if BS:
        s = BS["summary"]
        txt = ("intervals for 7-, 14- and 30-day blocks in the supplement (7-day intervals exclude the estimate in "
               f"{s['b7']['n_exclude']} of {s['b7']['n']} cells, 30-day in {s['b30']['n_exclude']})")
        if BS["switch_to_subsampling"]:
            txt += "; the table therefore uses subsampling intervals"
        put("blockNote", txt, "sizing_block_sens_all.json:summary")
    else:
        put("blockNote", "[[PENDING block sensitivity]]", "missing")

    exploratory()
    put("repoURL", REPO_URL, "repository (push and tag pending, CP-B2)")
    put("AIdisclosure", AI, "IEEE PSPB 8.2.1.B.10 disclosure")

    out = ["% numbers.tex: GENERATED by code/paper/gen_numbers.py. Do not hand-edit."]
    out += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in MAC.items()]
    (LATEX / "numbers.tex").write_text("\n".join(out) + "\n", encoding="utf-8")
    (RES / "numbers_provenance.json").write_text(json.dumps(PROV, indent=1), encoding="utf-8")
    pend = [k for k, v in MAC.items() if "PENDING" in v]
    print(f"{len(MAC)} macros; pending: {pend}")
    return 0


AI = ("The author used an AI assistant (Claude, Anthropic) for code development, literature search and "
      "language editing; all results, code and text were checked by the author, who takes full responsibility.")


def sizing_table(F5):
    rows = [x for x in F5["rows"] if abs(x["m"] - 0.25) < 1e-9]
    order = ["HCMC", "Madrid-MSG", "Madrid-SARAH3", "Uppsala-MSG", "Uppsala-SARAH3"]
    L = [r"\begin{table}[!t]\centering\caption{Storage for a class-A node over the full year ($m=0.25$, $K=8$; "
         r"kJ; 7-day block bootstrap). Kansal's mean-rate condition is omitted (it oversizes by \kmeanInvLo--\kmeanInvHi{} times). Descriptive, not pre-registered}\label{tab:sizing}",
         r"\footnotesize\setlength{\tabcolsep}{2pt}",
         r"\begin{tabular}{@{}llrrrrr@{}}\toprule",
         r"Site & & $C^*$ & 95\,\% CI & Avg-day & Buchli & 3-day\\\midrule"]
    kj = lambda v: "--" if v is None else f"{v / 1e3:.2f}"  # noqa: E731
    def line(x, name, sea):
        ci = x["Cstar_J_CI95"]
        b = x["baselines_J"]
        return (f"{name} & {sea} & {kj(x['Cstar_J'])} & {kj(ci[0])}--{kj(ci[1])} & {kj(b['C_avgday'])} & "
                f"{kj(b['C_buchli_daily'])} & {kj(b['C_3day'])}\\\\")
    for site in order:
        for sea in ("DJF", "MAM", "JJA", "SON"):
            x = next(r for r in rows if r["site"] == site and r["season"] == sea)
            L.append(line(x, {"HCMC": "HCMC", "Madrid-MSG": r"Mad.\ MSG", "Madrid-SARAH3": r"Mad.\ SARAH",
                               "Uppsala-MSG": r"Upp.\ MSG", "Uppsala-SARAH3": r"Upp.\ SARAH"}[site]
                              if sea == "DJF" else "", sea))
    for x in [r for r in rows if r["site"].startswith("Setup")]:
        L.append(line(x, "Indoor", x["site"][-1]))
    L += [r"\bottomrule\end{tabular}\end{table}"]
    (LATEX / "sizing_table.tex").write_text("\n".join(L) + "\n", encoding="utf-8")


def exploratory():
    X, XB = J("exploratory_q2_test.json"), J("exploratory_q2_boot_test.json")
    if not X or not XB:
        put("Esection", r"\subsection{Exploratory}[[PENDING exploratory E1--E3]]", "missing")
        put("EabstractSentence", "[[PENDING]]", "missing")
        return
    from e_text import e_macros   # written after the E results are known (code/paper/e_text.py)
    for k, (v, src) in e_macros(X, XB).items():
        put(k, v, src)


if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    sys.exit(main())
