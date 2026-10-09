"""Figures for the exploratory Q2 stage (PREREG v1.1): F7 (observed vs predicted Kansal - blackout) and F6'
(blackout / best throttle / Kansal-EWMA / periodic at a_max(TRAIN), same axis). Same style as make_figs.
python -m sim40.make_figs_q2
"""
from __future__ import annotations

import json

import numpy as np

from . import config as cfg
from .events import law_for
from .explore_q2 import load_rows
from .make_figs import COL, MK, W, _save, plt


def f7(rows):
    law = law_for("test")
    aK = np.array([x["kansal_ewma"]["a_bar"] for x in rows])
    aB = np.array([x["blackout_K8"]["a_bar"] for x in rows])
    obs = np.array([x["kansal_ewma"]["replay"] - x["blackout_K8"]["replay"] for x in rows])
    pred = law.eps_star(aK) - law.eps_star(aB)
    fig, ax = plt.subplots(figsize=(W, 2.5))
    ax.scatter(pred, obs, s=3, alpha=0.25, color=COL[0], rasterized=True, label="TEST cases")
    lo, hi = min(pred.min(), obs.min()), max(pred.max(), obs.max())
    ax.plot([lo, hi], [lo, hi], color="#666", ls="--", lw=1, label="observed = predicted")
    ax.axhline(0, color="#999", lw=0.6)
    ax.set(xlabel=r"predicted $\varepsilon^*(\bar a_K)-\varepsilon^*(\bar a_{blk})$",
           ylabel="observed Kansal − blackout")
    ax.legend(frameon=False, loc="upper left", fontsize=6.5)
    _save(fig, "F7_kansal_obs_vs_pred", "test")


def f6p(rows):
    C = np.array([x["C_rel"] for x in rows])
    blk = np.array([x["blackout_K8"]["replay"] for x in rows])
    series = {"Kansal-EWMA": np.array([x["kansal_ewma"]["replay"] for x in rows]),
              r"periodic at $\bar a_K$": np.array([x["per_abarK"]["replay"] for x in rows]),
              # E3 population only (a_max on TRAIN > 0); elsewhere the series is undefined (NaN)
              r"periodic at $a_{max}$ (TRAIN)": np.array([x["per_amax_d0"]["replay"]
                                                         if x["per_amax_d0"]["a_max_train"] > 0 else np.nan
                                                         for x in rows])}
    # best throttle variant per case comes from the throttle stage (same population, same C grid)
    S = json.loads((cfg.RES / "summary_test.json").read_text())
    thr = {}
    for x in S["throttle"]["rows"]:
        if 0 < x["blackout_K8_outage"] < 1:
            k = (x["site"], x["season"], x["r"], x["l"], x["m"], round(x["C_rel"], 9))
            thr[k] = min(x[n] for n in x if n.startswith("thr_") and not n.endswith("_outage"))
    bt = np.array([thr.get((x["site"], x["season"], x["r"], x["l"], x["m"], round(x["C_rel"], 9)), np.nan)
                   for x in rows])
    series = {"best throttle (hindsight)": bt} | series
    bins = np.geomspace(max(C.min(), 1e-3), C.max(), 11)
    idx = np.digitize(C, bins)
    fig, ax = plt.subplots(figsize=(W, 2.6))
    for i, (name, y) in enumerate(series.items()):
        d = y - blk
        mx, my = [], []
        for k in np.unique(idx):
            sel = (idx == k) & np.isfinite(d)
            if sel.sum() >= 20:
                mx.append(np.median(C[sel])); my.append(np.median(d[sel]))
        ax.plot(mx, my, color=COL[i + 1], marker=MK[i + 1], ms=3.5, label=name)
    ax.axhline(0, color="#666", lw=0.8, label="blackout, periodic $K=8$")
    ax.set(xscale="log", xlabel=r"$C\,/\,C^*_{per}(8)$", ylabel="miss − miss(blackout)")
    ax.legend(frameon=False, fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=2)
    _save(fig, "F6p_throttle_kansal_amax", "test")


def main():
    rows = [x for x in load_rows() if 0 < x["blackout_K8"]["outage"] < 1]
    f7(rows)
    f6p(rows)
    print("figures in", cfg.FIGS)


if __name__ == "__main__":
    main()
