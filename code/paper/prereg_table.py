"""Table I of the paper: PREREG v1 predictions H1-H7 with criterion, TEST observation and outcome
-> submission_package/IoTJ/latex/prereg_table.tex (CP-B2 Q4, P5).

* Criteria are abridged from the frozen P1/PREREG_40.md (tag prereg-40-v1). Every threshold number of an abridged
  criterion is checked against the numbers of the corresponding PREREG row; a threshold that is not in the row
  aborts the build (no hand-typed threshold can drift).
* Observations and verdicts come from results/prereg_score_test.json only.
* A FAIL is labelled 'favourable' when the observed value misses the band on the side that favours the claim,
  'magnitude' when the sign/direction holds but the size is outside the band (the labels used in the text).
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
PREREG = ROOT / "P1" / "PREREG_40.md"

# key -> (abridged criterion in LaTeX, theorem numbers of PREREG mapped to this paper's labels)
CRIT = {
    "H1": r"0 family-wise violations (replay below floor by $>z_{\mathrm{Bonf}}\cdot$SE, $\alpha=0.05$) of "
          r"Thm.~\ref{thm:floor}, Thm.~\ref{thm:energy}, Prop.~\ref{prop:blackout}; 0 analytic violations "
          r"(tolerance $10^{-6}$)",
    "H2a": r"Kansal tight: $C^*/C_{\mathrm{Kansal}}\in[0.99,1.01]$ in 100\,\% of combos",
    "H2b": r"Kansal with mean harvest: $C^*/C_{\mathrm{Kansal\text{-}mean}}<1$ in $\ge95$\,\% of combos",
    "H2c": r"Average-day: $C^*/C_{\mathrm{avgday}}>1$ in 100\,\%; medians HCMC $\in[1.1,2.5]$, Madrid $\in[2,8]$, "
           r"Uppsala $\in[2,10]$, indoor $\in[5,25]$; max outdoor $\ge15$, indoor $\ge30$",
    "H2d": r"Buchli: $C^*/C_{\mathrm{Buchli}}>1$ in $\ge95$\,\%; median HCMC $\ge2$; Madrid, Uppsala, indoor "
           r"medians $\in[1,2]$",
    "H2e": r"3-day rule: HCMC $C^*<C_{3\mathrm{day}}$ in 100\,\%; Madrid, Uppsala median $<1.2$, max $>2$; "
           r"indoor share $C^*>C_{3\mathrm{day}}$ $\ge40$\,\%",
    "H3a": r"Equal $a$: $\Delta$miss $>0$ in 100\,\%; median at $K=8$ per group $\in[0.18,0.32]$",
    "H3b": r"Equal $a$: $\Delta C<0$ in $\ge95$\,\%; median $C_{\mathrm{HF}}/C_{\mathrm{per}}$ at $K=8$ per group "
           r"$\in[0.1,0.5]$",
    "H3c": r"Bootstrap: $\Delta$miss $>0$ and $\Delta C<0$ significant after Holm in all 25 cells",
    "H4a": r"Equal $\eps$: $C_{\mathrm{TS}}/C_{\mathrm{per}}<1$ in $\ge95$\,\%; median per group $\in[0.2,0.7]$ "
           r"for $\eps\in\{0.5,0.6\}$",
    "H4b": r"$C_{\mathrm{LB}}/C_{\mathrm{TS}}\le1.02$ in 100\,\% of cells",
    "H4c": r"Median $C_{\mathrm{LB}}/C_{\mathrm{TS}}\ge0.9$ at $\eps\ge0.6$; $<0.9$ at $\eps=0.45$ in $\ge3$ of 4 groups",
    "H4d": r"Bootstrap: $C_{\mathrm{TS}}/C_{\mathrm{per}}<1$ significant after Holm in the 6 cells",
    "H5a": r"Best throttle (oracle): $|\Delta|\le0.03$ vs blackout in $\ge95$\,\%; better by $>0.03$ in $\le1$\,\%",
    "H5b": r"Naive throttle $8\to64$ at 20/50\,\%: $\Delta>0$ in $\ge90$\,\%; median $\in[0.01,0.06]$",
    "H5c": r"Median(best throttle $-$ blackout) $>-0.01$ in every group",
    "H6": r"Gate infeasibility agrees with $c>(1-\rho)a_{\mathrm{per}}(r-1)$ in 100\,\%; outage monotone in "
          r"$\ge95$\,\% of pairs",
    "H7": r"Class-A node: HCMC $C^*<1$\,kJ in all 4 seasons; $>2$\,kJ in $\ge2$ Madrid and $\ge2$ Uppsala seasons; "
          r"$<44$\,kJ and $>45$\,J in 100\,\%; $C_{\mathrm{TS}}/C^*<0.6$ in $\ge80$\,\%",
}
FAIL_KIND = {"H4a": "favourable", "H7": "magnitude"}
# numbers in CRIT that are not thresholds (theorem/paper labels, sign conventions, quantity names)
NOT_THRESHOLD: set[str] = set()


def _num(s):
    return set(re.findall(r"(?<![\w.])\d+(?:\.\d+)?", s))


def _prereg_rows():
    rows = {}
    for line in PREREG.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*\*\*(H\d[a-e]?)\*\*", line)
        if m:
            txt = line.replace("−", "-").replace("⁻⁶", "^-6").replace("10⁻⁶", "10^-6")
            rows[m.group(1)] = txt
    return rows


def _check_thresholds():
    rows = _prereg_rows()
    bad = {}
    for k, crit in CRIT.items():
        plain = re.sub(r"\\ref\{[^}]*\}|\\[A-Za-z]+|\{|\}", " ", crit)
        nums = _num(plain) - NOT_THRESHOLD
        miss = sorted(n for n in nums if n not in _num(rows[k]))
        if miss:
            bad[k] = miss
    if bad:
        raise SystemExit(f"prereg_table: thresholds not found in PREREG_40.md rows: {bad}")


def _p(x, d=0):
    return f"{100 * x:.{d}f}\\,\\%"


def _t(n):
    return f"{int(n):,}".replace(",", "{,}")


def _rng(vals, d=2):
    return f"{min(vals):.{d}f}--{max(vals):.{d}f}"


def observed(SC):
    o = {}
    h = SC["H1"]
    o["H1"] = (f"{h['familywise']['T1_any_policy']}/{h['familywise']['T2_energy_floor']}/"
               f"{h['familywise']['P2prime_blackout']} of {_t(h['n']['T1_any_policy'])}/"
               f"{_t(h['n']['T2_energy_floor'])}/{_t(h['n']['P2prime_blackout'])}; analytic {h['analytic']}")
    o["H2a"] = f"{_p(SC['H2a']['share_in_band'])} of {_t(SC['H2a']['n'])}"
    o["H2b"] = f"{_p(SC['H2b']['share_lt1'])} of {_t(SC['H2b']['n'])}"
    c = SC["H2c"]
    m = c["medians"]
    o["H2c"] = (f"{_p(c['share_gt1'])}; {m['HCMC']:.2f}, {m['Madrid']:.2f}, {m['Uppsala']:.2f}, {m['indoor']:.1f}; "
                f"max {c['max_outdoor']:.0f}, {c['max_indoor']:.0f}")
    d = SC["H2d"]
    m = d["medians"]
    o["H2d"] = (f"{_p(d['share_gt1'])} of {_t(d['n'])}; {m['HCMC']:.2f}; {m['Madrid']:.2f}, {m['Uppsala']:.2f}, "
                f"{m['indoor']:.2f}")
    e = SC["H2e"]
    eu = e["europe"]
    o["H2e"] = (f"{_p(e['HCMC_share_lt1'])} (max {e['HCMC_max']:.2f}); {eu['Madrid']['median']:.2f}, "
                f"{eu['Uppsala']['median']:.2f}, max {eu['Madrid']['max']:.2f}, {eu['Uppsala']['max']:.2f}; "
                f"{_p(e['indoor_share_gt1'])}")
    a = SC["H3a"]
    o["H3a"] = f"{_p(a['share_gt0'])} of {_t(a['n'])}; {_rng(a['medians_K8'].values())}"
    b = SC["H3b"]
    o["H3b"] = f"{_p(b['share_lt0'])} of {_t(b['n'])}; {_rng(b['medians_K8'].values())}"
    c = SC["H3c"]
    o["H3c"] = f"{c['n_rej_dmiss']}/{c['n_cells']} and {c['n_rej_dC']}/{c['n_cells']} ({c['holm_tests']} tests)"
    a = SC["H4a"]
    meds = [v for e in a["medians"].values() for v in e.values()]
    o["H4a"] = f"{_p(a['share_lt1'])} of {_t(a['n'])}; {_rng(meds, 3)}"
    b = SC["H4b"]
    o["H4b"] = f"{_p(b['share_le_1_02'])} of {_t(b['n'])}; max {b['max']:.3f}"
    c = SC["H4c"]
    hi = [v for e in c["medians_eps_ge_0_6"].values() for v in e.values()]
    lo = list(c["medians_eps_0_45"].values())
    o["H4c"] = (f"min {min(hi):.3f}; {sum(v < 0.9 for v in lo)} of {len(lo)} ({_rng(lo)})")
    dd = SC["H4d"]["cells"]
    o["H4d"] = f"{sum(v[1] for v in dd.values())}/{len(dd)} ({_rng([v[0] for v in dd.values()])})"
    a = SC["H5a"]
    o["H5a"] = (f"{_p(a['share_within_0_03'])} of {_t(a['n'])}; {_p(a['share_better_gt_0_03'])}; "
                f"median ${a['median']:+.4f}$")
    b = SC["H5b"]
    o["H5b"] = f"{_p(b['share_gt0'], 1)}; median ${b['median']:+.3f}$"
    mb = SC["H5c"]["medians_best_minus_blackout"].values()
    o["H5c"] = f"${min(mb):+.4f}$ to ${max(mb):+.4f}$"
    g = SC["H6"]
    o["H6"] = f"{_t(g['agree'])}/{_t(g['n'])}; {_p(g['monotone_share'])} of {_t(g['pairs'])}"
    s = SC["H7"]
    o["H7"] = (f"HCMC {_rng([x / 1e3 for x in s['HCMC_Cstar_J']])}\\,kJ; Madrid "
               f"{s['seasons_gt_2kJ_pooled']['Madrid']}, Uppsala {s['seasons_gt_2kJ_pooled']['Uppsala']} seasons; "
               f"{s['min_J'] / 1e3:.2f}--{s['max_J'] / 1e3:.1f}\\,kJ; {_p(s['TS_over_Cstar_lt_0_6_share'])}")
    return o


def table(SC):
    _check_thresholds()
    obs = observed(SC)
    keys = [k for k in SC if re.fullmatch(r"H\d[a-e]?", k)]
    assert set(keys) == set(CRIT), (sorted(keys), sorted(CRIT))
    L = [r"\begin{table*}[!t]\centering\caption{Pre-registered predictions (PREREG v1, frozen before TEST) and "
         r"their outcome on TEST. Criteria are abridged from the frozen text with every threshold kept; theorem "
         r"numbers refer to this paper. Scalar details are in the supplement}\label{tab:prereg}",
         r"\footnotesize\setlength{\tabcolsep}{3pt}\renewcommand{\arraystretch}{1.05}",
         # column widths overridable per template (\preregCritW, \preregObsW); defaults = IoT-J layout
         r"\providecommand{\preregCritW}{0.50\textwidth}\providecommand{\preregObsW}{0.335\textwidth}",
         r"\begin{tabular}{@{}lp{\preregCritW}p{\preregObsW}l@{}}\toprule",
         r"\# & Pass criterion (abridged) & Observed on TEST & Outcome\\\midrule"]
    for k in keys:
        v = SC[k]["verdict"]
        out = "PASS" if v == "PASS" else f"FAIL-{FAIL_KIND[k]}"
        L.append(rf"{k} & \raggedright {CRIT[k]} & \raggedright {obs[k]} & {out}\\")
    L += [r"\bottomrule\end{tabular}\end{table*}"]
    return "\n".join(L) + "\n"


def write(SC, latex_dir):
    (pathlib.Path(latex_dir) / "prereg_table.tex").write_text(table(SC), encoding="utf-8")


if __name__ == "__main__":
    print(table(json.loads((ROOT / "results" / "prereg_score_test.json").read_text())))
