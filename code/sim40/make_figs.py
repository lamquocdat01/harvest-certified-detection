"""Figures F1-F6 from results/summary_<split>.json (IEEEtran single column: 3.5 in wide, fonts >= 8 pt).
Palette = validated categorical slots (dataviz reference); identity also carried by marker + legend.
python -m sim40.make_figs --split test
"""
from __future__ import annotations

import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import config as cfg

COL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7"]
MK = ["o", "s", "^", "D", "v", "P"]
SITES = ["HCMC", "Madrid-MSG", "Madrid-SARAH3", "Uppsala-MSG", "Uppsala-SARAH3", "indoor"]
W = 3.5
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25, "lines.linewidth": 1.4,
                     "pdf.fonttype": 42, "savefig.dpi": 300})
SEL = {"r": 15.0, "l": 0.04, "m": 0.25}


def _grp(site):
    return "indoor" if site.startswith("Setup") else site


def _sel(rows, **kw):
    q = SEL | kw
    return [x for x in rows if all(abs(x[k] - v) < 1e-9 if isinstance(v, float) else x[k] == v for k, v in q.items())]


def _save(fig, name, split):
    cfg.FIGS.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(cfg.FIGS / f"{name}_{split}.{ext}", bbox_inches="tight")
    plt.close(fig)


def f1(S, split):
    rows = _sel(S["main"]["F1"])
    fig, axs = plt.subplots(1, 2, figsize=(W, 1.9), sharey=True)
    for ax, sea in zip(axs, ("DJF", "JJA")):
        for i, site in enumerate(SITES[:5]):
            rr = [x for x in rows if x["site"] == site and x["season"] == sea]
            if not rr:
                continue
            d = rr[0]["C_per_days"]
            ks = sorted(int(k) for k, v in d.items() if v is not None)
            ax.plot(ks, [d[str(k)] for k in ks], color=COL[i], marker=MK[i], ms=3.5, label=site)
        ax.set(xscale="log", yscale="log", xlabel="period K", title=sea)
        ax.set_xticks([8, 16, 32, 64], ["8", "16", "32", "64"])
    axs[0].set_ylabel("C*(K) [days of demand]")
    axs[1].legend(frameon=False, loc="upper right", fontsize=6)
    _save(fig, "F1_frontier_K_Cstar", split)


def f2(S, split):
    import sim40.analyze as A  # noqa
    fig, ax = plt.subplots(figsize=(W, 2.4))
    pts = S["main"].get("F2_points")
    if pts:
        x, y = np.array(pts["floor"]), np.array(pts["replay"])
        ax.scatter(x, y, s=3, alpha=0.25, color=COL[0], label="policy × C cells", rasterized=True)
    ax.plot([0, 1], [0, 1], color="#666", lw=1, ls="--", label="miss = floor")
    v = S["main"]["F2"]
    txt = "; ".join(f"{k}: {d['viol']}/{d['n']}" for k, d in v.items())
    ax.set(xlabel="floor (Thm 1 / Thm 2 / Prop 2′)", ylabel="replayed miss", xlim=(0.15, 1), ylim=(0.15, 1))
    ax.set_title("violations: " + txt, fontsize=6)
    ax.legend(frameon=False, loc="lower right")
    _save(fig, "F2_miss_vs_floor", split)


def f3(S, split):
    eq = [x for x in S["frontier"]["equal_a"] if x["r"] == 15.0 and x["l"] == 0.04 and x["m"] == 0.25 and x["K"] == 8]
    eps = [x for x in S["frontier"]["eps_sizing"] if x["r"] == 15.0 and x["l"] == 0.04 and x["m"] == 0.25]
    fig, axs = plt.subplots(1, 2, figsize=(W, 1.9))
    for i, g in enumerate(SITES):
        e = [x for x in eq if _grp(x["site"]) == g]
        if e:
            axs[0].scatter([x["C_hf"] / x["C_per"] for x in e], [x["dmiss_hf_minus_per"] for x in e], s=12,
                           color=COL[i], marker=MK[i], label=g)
        z = [x for x in eps if _grp(x["site"]) == g]
        if z:
            es = sorted(set(x["eps"] for x in z))
            med = [np.median([x["TS_over_per"] for x in z if x["eps"] == ee]) for ee in es]
            axs[1].plot(es, med, color=COL[i], marker=MK[i], ms=3.5, label=g)
    axs[0].set(xlabel="C_HF / C_per  (a = 1/8)", ylabel="miss_HF − miss_per")
    axs[1].set(xlabel="miss target ε", ylabel="C_TS(ε) / C_per(ε)", ylim=(0, 1.05))
    axs[1].axhline(1, color="#666", lw=0.8, ls=":")
    axs[0].legend(frameon=False, fontsize=5.5, loc="lower right")
    _save(fig, "F3_frontier_spread_vs_hf", split)


def f4(S, split):
    G = [x for x in S["gate"] if x["r"] == 15.0]
    rhos = sorted(set(x["rho"] for x in G))
    cs = sorted(set(x["c"] for x in G))
    M = np.full((len(cs), len(rhos)), np.nan)
    for i, c in enumerate(cs):
        for j, rho in enumerate(rhos):
            v = [x["outage_at_Cper"] for x in G if x["c"] == c and x["rho"] == rho]
            M[i, j] = np.median(v) if v else np.nan
    fig, ax = plt.subplots(figsize=(W, 2.1))
    im = ax.imshow(M, origin="lower", aspect="auto", cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(rhos)), [f"{r:g}" for r in rhos])
    ax.set_yticks(range(len(cs)), [f"{c:g}" for c in cs])
    rr = np.linspace(min(rhos), max(rhos), 200)
    a_per, r = 1 / 8, 15.0
    cb = (1 - rr) * a_per * (r - 1)
    xj = np.interp(rr, rhos, range(len(rhos)))
    yj = np.interp(cb, cs, range(len(cs)), left=np.nan, right=np.nan)
    ax.plot(xj, yj, color="#eb6834", lw=1.5, label="c*(ρ) = (1−ρ) a_per (r−1)")
    ax.axvline(np.interp(6.07, rhos, range(len(rhos))), color="#4a3aa7", ls="--", lw=1, label="presence gate ρ≈6.1")
    ax.set(xlabel="ρ = a_gate / a_per", ylabel="cue cost c [e_idle/slot]")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="gate outage at C*_per (median)")
    ax.legend(frameon=False, fontsize=6, loc="upper right")
    _save(fig, "F4_gate_map", split)


def f6(S, split):
    T = S.get("throttle", {}).get("rows", [])
    fig, ax = plt.subplots(figsize=(W, 2.2))
    names = ["blackout_K8", "thr_K16_5/10", "thr_K64_20/50", "kansal_ewma"]
    for i, n in enumerate(names):
        xs, ys = [], []
        for x in T:
            if x["r"] == 15.0 and x["l"] == 0.04 and x["m"] == 0.25 and n in x:
                xs.append(x["C_rel"]); ys.append(x[n] - x["blackout_K8"])
        if xs:
            xs, ys = np.array(xs), np.array(ys)
            bins = np.geomspace(xs.min(), xs.max(), 12)
            idx = np.digitize(xs, bins)
            mx = [np.median(xs[idx == k]) for k in np.unique(idx)]
            my = [np.median(ys[idx == k]) for k in np.unique(idx)]
            ax.plot(mx, my, color=COL[i], marker=MK[i], ms=3.5, label=n.replace("_", " "))
    ax.axhline(0, color="#666", lw=0.8)
    ax.set(xscale="log", xlabel="C / C*_per(8)", ylabel="miss − miss(blackout K=8)")
    ax.legend(frameon=False, fontsize=6)
    _save(fig, "F6_throttle_vs_blackout", split)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    S = json.loads((cfg.RES / f"summary_{a.split}.json").read_text())
    for fn in (f1, f2, f3, f4, f6):
        try:
            fn(S, a.split)
        except Exception as e:
            print(fn.__name__, "failed:", repr(e))
    print("figures in", cfg.FIGS)


if __name__ == "__main__":
    main()
