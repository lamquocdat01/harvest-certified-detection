"""Event-level metrics from a fluid run (on-fraction and activation rate per sub-step).

Assumption A1 (THEORY_40): event onsets are uniform over the horizon and independent of the policy.
Within an on sub-step with rate a the schedule is (interleaved) periodic, so an event starting there is
caught with probability Psi(a) = E[min(1, aD)] (Theorem 1, tight case). An event starting in an outage is
missed (outages last minutes-hours >> D; boundary terms O(E[D]/n) per outage are neglected and bounded
in THEORY_40 Remark 4).
"""
from __future__ import annotations

import numpy as np

from .events import DurationLaw

N_RATE_BINS = 2048


def rate_histogram(on_frac, rate):
    """Weights of onsets per activation-rate value: {rate: weight}, weights sum to the on-time fraction."""
    w = np.asarray(on_frac, float)
    a = np.asarray(rate, float)
    m = w > 0
    vals, inv = np.unique(np.round(a[m], 6), return_inverse=True)
    if vals.size > N_RATE_BINS:  # compress continuous schedules
        edges = np.unique(np.quantile(a[m], np.linspace(0, 1, N_RATE_BINS + 1)))
        idx = np.clip(np.searchsorted(edges, a[m], side="right") - 1, 0, edges.size - 2)
        wsum = np.bincount(idx, weights=w[m], minlength=edges.size - 1)
        asum = np.bincount(idx, weights=w[m] * a[m], minlength=edges.size - 1)
        keep = wsum > 0
        return asum[keep] / wsum[keep], wsum[keep] / w.size
    return vals, np.bincount(inv, weights=w[m]) / w.size


def miss_from_hist(rates, weights, law: DurationLaw):
    return float(1.0 - (weights * law.psi(rates)).sum())


def outage_runs(on_frac, sub_s=60.0):
    """Outage episodes: maximal runs of sub-steps with on_frac < 1; length = off-time in hours."""
    off = 1.0 - np.asarray(on_frac, float)
    b = np.r_[0, (off > 1e-12).astype(int), 0]
    e = np.flatnonzero(np.diff(b))
    starts, ends = e[::2], e[1::2]
    cs = np.r_[0.0, np.cumsum(off)]
    return (cs[ends] - cs[starts]) * sub_s / 3600.0


def latency_quantiles(rates, weights, law: DurationLaw, qs=(0.99,)):
    """Onset->catch latency (slots) of CAUGHT events: P(L = j, caught | a) = a P(D > j) for j < 1/a."""
    rates = np.asarray(rates, float)
    weights = np.asarray(weights, float)
    m = rates > 0
    if not m.any():
        return {f"p{int(q*100)}": None for q in qs} | {"max": None}
    # caught latency < D <= dmax, so the distribution lives on 0..dmax-1 whatever the rate
    Kmax = int(min(np.ceil(1.0 / rates[m].min()), law.dmax))
    surv = np.r_[law.surv, np.zeros(max(0, Kmax - law.surv.size))][:Kmax]
    pmf = np.zeros(Kmax)
    for a, w in zip(rates[m], weights[m]):
        lim = int(np.ceil(1.0 / a - 1e-9))
        pmf[:lim] += w * a * surv[:lim]
    cdf = np.cumsum(pmf) / pmf.sum()
    out = {f"p{int(q*100)}": int(np.searchsorted(cdf, q)) for q in qs}
    out["max"] = int(Kmax - 1)
    return out


def summarize(on_frac, rate, law: DurationLaw, K_nom=None, sub_s=60.0):
    rates, w = rate_histogram(on_frac, rate)
    res = {"miss": miss_from_hist(rates, w, law),
           "outage_frac": float(1.0 - np.mean(on_frac)),
           "a_bar_on": float((np.asarray(on_frac) * np.asarray(rate)).sum() / max(np.sum(on_frac), 1e-12)),
           "a_bar": float(np.mean(np.asarray(on_frac) * np.asarray(rate)))}
    if K_nom is not None:
        res["miss_DgeK"] = miss_from_hist(rates, w, law.conditional(K_nom))
    L = outage_runs(on_frac, sub_s)
    res["n_outages"] = int(L.size)
    res["L_out_h"] = {"p50": float(np.median(L)) if L.size else 0.0, "max": float(L.max()) if L.size else 0.0}
    res["latency"] = latency_quantiles(rates, w, law)
    res["_hist"] = (rates, w)
    return res


def replay_miss(on_frac, rate, durations, n_events=200_000, rng=None, n_sub=600, D_ge=None):
    """EMPIRICAL miss by event replay (not via Psi): onsets uniform over the horizon's slots, durations drawn
    from `durations` (real corpus events), activations = phase-continuous interleaved (Bresenham) sequence
    of the run's rates (rate a_j during the on part of sub-step j, which is its first on_frac_j fraction).
    Event [s, s+d) caught iff the activation counter floor(A + phi) increases inside it."""
    rng = np.random.default_rng(42) if rng is None else rng
    f = np.asarray(on_frac, float)
    a = np.asarray(rate, float)
    J = f.size
    per = a * f * n_sub                                   # activations per sub-step (fluid)
    P = np.r_[0.0, np.cumsum(per)]
    Tn = J * n_sub
    d = np.asarray(durations)[rng.integers(0, len(durations), n_events)]
    if D_ge is not None:
        d = d[d >= D_ge]
    s = rng.integers(0, Tn, d.size)
    e = s + d
    phi = rng.random()

    def A(t):
        t = np.minimum(t, Tn)                             # events running past the horizon end: truncated
        j = np.minimum(t // n_sub, J - 1)
        u = t - j * n_sub
        return P[j] + a[j] * np.minimum(u, f[j] * n_sub)

    caught = np.floor(A(e) + phi) > np.floor(A(s) + phi)
    return float(1.0 - caught.mean()), int(d.size)
