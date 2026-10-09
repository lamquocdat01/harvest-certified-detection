"""Policy garden. Every policy returns (on_frac, rate) per 1-min sub-step of the cyclic horizon (steady state).

Oblivious (Theorems 1-2b apply):
  periodic(K)        constant rate 1/K, blackout when storage empties, restart at 5 % of C
  harvest_following  rate proportional to the harvest surplus over idle, scaled to a target mean rate
  greedy_amax        offline schedule attaining a_max(C) (Theorem 2 extreme; never empties storage)
  throttle(K, K')    periodic K, drops to K' when storage < 20 % C, back at 50 % C (throttling, not blackout)
  kansal_ewma        Kansal-style energy-neutral duty cycle: per-day rate from an EWMA harvest predictor
                     (alpha = 0.5) plus storage feedback (gain 0.5 toward 50 % C), rate in [1/256, 1]
Cue-based (Corollary 3 only): gate energy per slot 1 + l + c + a_g (r - 1) (fluid; no miss model here).
"""
from __future__ import annotations

import numpy as np

from . import energy as E

N_SUB = 600       # slots per 1-min sub-step at 10 fps
RESTART = 0.05
DAY = 1440


def periodic(h, r, l, C, K):
    on, rt, B = E.simulate_cyclic(h, np.array([1.0 / K]) * np.ones(h.size), N_SUB, r, l, C, RESTART, mode=0)
    return on, rt


def hf_schedule(h, r, l, a_target):
    """Rate proportional to the surplus over idle, mean = a_target (bisection on the gain)."""
    sur = np.maximum(h - (1.0 + l), 0.0) / max(r - 1.0, 1e-12)
    if sur.mean() <= 0:
        return np.zeros_like(h)
    lo, hi = 0.0, 1.0
    while np.clip(hi * sur, 0, 1).mean() < a_target and hi < 1e12:
        hi *= 2
    if np.clip(hi * sur, 0, 1).mean() < a_target:
        return np.clip(hi * sur, 0, 1)
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if np.clip(mid * sur, 0, 1).mean() < a_target:
            lo = mid
        else:
            hi = mid
    return np.clip(hi * sur, 0, 1)


def harvest_following(h, r, l, C, a_target):
    sched = hf_schedule(h, r, l, a_target)
    on, rt, B = E.simulate_cyclic(h, sched, N_SUB, r, l, C, RESTART, mode=0)
    return on, rt


def greedy_schedule(h, r, l, C):
    a, ok, y = E.greedy_amax(h, float(N_SUB), float(r), float(l), float(C), float(C), float(r - 1.0))
    return (y / (N_SUB * (r - 1.0)) if ok else None), (a if ok else np.nan)


def greedy(h, r, l, C):
    sched, a = greedy_schedule(h, r, l, C)
    if sched is None:
        return None
    # run from full storage, single pass (the greedy is defined with B0 = C, free end)
    on, rt, B, sp = E.simulate(h, sched, float(N_SUB), float(r), float(l), float(C), float(C), RESTART, 0,
                               0.0, 0.0, 0.0, DAY, np.zeros(1))
    return on, rt


def throttle(h, r, l, C, K, K_low=64, lo=0.2, hi=0.5):
    """Periodic K; drop to K_low when storage < lo*C, back to K when storage >= hi*C."""
    on, rt, B = E.simulate_cyclic(h, np.array([1.0 / K]), N_SUB, r, l, C, RESTART, mode=1,
                                  p=(lo, hi, 1.0 / K_low))
    return on, rt


def kansal_pred(h):
    days = h.size // DAY
    H = h[:days * DAY].reshape(days, DAY).sum(1) * N_SUB
    pred = np.empty(days)
    pred[0] = H.mean()
    for d in range(1, days):
        pred[d] = 0.5 * pred[d - 1] + 0.5 * H[d - 1]
    return pred


def kansal_ewma(h, r, l, C):
    days = h.size // DAY
    hh = h[:days * DAY]
    on, rt, B = E.simulate_cyclic(hh, np.array([0.0]), N_SUB, r, l, C, RESTART, mode=2, p=(0.5, 0.5, 1.0 / 256),
                                  day_steps=DAY, hday_pred=kansal_pred(hh))
    return on, rt


def gate_storage_need(h, r, l, a_g, c):
    """Corollary 3: fluid storage need of a gate with cue cost c per slot and activation rate a_g."""
    return E.C_periodic(h, N_SUB, r, l + c, a_g)


def taut(h, r, l, C):
    """Energy-tunnel optimal oblivious policy (T3(i) frontier), cyclic, no outage by construction."""
    a = E.taut_schedule(h, float(N_SUB), float(r), float(l), float(C))
    if a is None:
        return None
    on, rt, B = E.simulate_cyclic(h, a, N_SUB, r, l, C, RESTART, mode=0)
    return on, rt
