"""Storage dynamics, Lemma 1 / Corollary 1.1 storage need, greedy a_max (Theorem 2), C*(eps) (Theorem 2b).

Time is split into sub-steps of n slots (n = 600 for 1-minute sub-steps at 10 fps). Harvest per slot is
constant inside a sub-step (zero-order hold of the trace), the policy's activation rate a_j is constant
inside a sub-step (fluid periodic), so storage is monotone inside a sub-step and every constraint can be
checked at sub-step boundaries exactly. The per-activation granularity (one activation costs r-1 at once)
is absorbed by adding (r-1) to fluid storage needs (Remark in THEORY_40 sec. 2).

Units: everything in e_idle. Per sub-step j:
    income_j = n h_j,  idle_j = n (1 + l),  act_j = n a_j (r - 1).
"""
from __future__ import annotations

import numpy as np
from numba import njit


# ------------------------------------------------------------------ Lemma 1 / Corollary 1.1
@njit(cache=True)
def max_drawdown(net):
    """max_{s<=t} (S_s - S_t), S = cumsum(net), S_0 = 0: minimal C with storage >= 0 when starting full."""
    peak = 0.0
    s = 0.0
    dd = 0.0
    for x in net:
        s += x
        if s > peak:
            peak = s
        if peak - s > dd:
            dd = peak - s
    return dd


def storage_need_cyclic(net):
    """Minimal C so that a periodic (cyclic) demand/harvest pattern never empties storage in steady state.
    inf if the cycle has a net deficit (no finite storage sustains it)."""
    net = np.asarray(net, float)
    if net.sum() < -1e-9 * np.abs(net).sum():
        return np.inf
    return float(max_drawdown(np.concatenate([net, net])))


def storage_need_envelope(demand_of_delta, alpha_l):
    """Lemma 1 form: sup_Delta [demand(Delta) - alpha_l(Delta)]^+ over a grid of window lengths."""
    return float(max(0.0, np.max(np.asarray(demand_of_delta) - np.asarray(alpha_l))))


# ------------------------------------------------------------------ simulation with blackout
@njit(cache=True)
def simulate(h, a, n, r, l, C, B0, restart_frac, mode, p0, p1, p2, day_steps, hday_pred):
    """Fluid storage simulation with blackout (outage) and optional state-dependent policy.

    h          harvest per slot, per sub-step (len J)
    a          activation rate per sub-step for mode 0 (fixed schedule); nominal rate a[0] for modes 1-2
    mode 0     fixed schedule a_j
    mode 1     throttle: rate a[0] while B >= p0*C ... drops to p2 (=a_low) when B < p0*C, back when B >= p1*C
    mode 2     Kansal-style EWMA energy-neutral duty cycle: per day, a_d = clip((Hpred_d - idle_d
               + p0*(B - p1*C)) / (act unit), p2, 1); hday_pred[d] = predicted harvest of day d (per day)
    restart    after an outage the node restarts when B >= restart_frac * C
    Returns on_frac (J), rate (J), B_end (J), spill_total.
    """
    J = h.size
    on_frac = np.zeros(J)
    rate = np.zeros(J)
    Bend = np.zeros(J)
    B = B0
    on = True
    low = False
    spill = 0.0
    a_day = a[0]
    for j in range(J):
        if mode == 2 and j % day_steps == 0:
            d = j // day_steps
            idle_day = day_steps * n * (1.0 + l)
            num = hday_pred[d] - idle_day + p0 * (B - p1 * C)
            a_day = num / (day_steps * n * (r - 1.0)) if r > 1.0 else 1.0
            if a_day < p2:
                a_day = p2
            if a_day > 1.0:
                a_day = 1.0
        if mode == 0:
            aj = a[j]
        elif mode == 1:
            if low:
                if B >= p1 * C:
                    low = False
            else:
                if B < p0 * C:
                    low = True
            aj = p2 if low else a[0]
        else:
            aj = a_day
        inc = n * h[j]
        if on:
            spend = n * (1.0 + l + aj * (r - 1.0))
            Bn = B + inc - spend
            if Bn >= -1e-9 * (spend + inc):
                if Bn < 0.0:
                    Bn = 0.0
                if Bn > C:
                    spill += Bn - C
                    Bn = C
                on_frac[j] = 1.0
                rate[j] = aj
                B = Bn
            else:
                # storage empties inside the sub-step: on for f, then off (only leakage drawn while off)
                f = B / (spend - inc) if spend > inc else 1.0
                on_frac[j] = f
                rate[j] = aj
                rest = (1.0 - f) * n * (h[j] - l)
                B = rest if rest > 0.0 else 0.0
                on = False
        else:
            B = B + n * (h[j] - l)
            if B < 0.0:
                B = 0.0
            if B > C:
                spill += B - C
                B = C
            if B >= restart_frac * C:
                on = True
        Bend[j] = B
    return on_frac, rate, Bend, spill


def simulate_cyclic(h, a, n, r, l, C, restart_frac=0.05, mode=0, p=(0.0, 0.0, 0.0), day_steps=1440,
                    hday_pred=None, cycles=2, max_cycles=60, tol=1e-6):
    """Cyclic steady state: start full, repeat the cycle until the storage at the end of a cycle equals the
    storage at its start (relative tol) or max_cycles; return the LAST cycle. (A fixed number of passes is
    not enough: with large C a deficit policy can drain for many cycles before its first outage.)"""
    J = h.size
    aa = np.asarray(a, float) if (mode == 0 and np.size(a) == J) else np.atleast_1d(np.asarray(a, float))
    hp = np.zeros(1) if hday_pred is None else np.asarray(hday_pred, float)
    B0 = float(C)
    on = rt = Be = None
    for k in range(max_cycles):
        on, rt, Be, sp = simulate(np.asarray(h, float), aa, float(n), float(r), float(l), float(C), B0,
                                  float(restart_frac), int(mode), float(p[0]), float(p[1]), float(p[2]),
                                  int(day_steps), hp)
        if k + 1 >= cycles and abs(Be[-1] - B0) <= tol * max(C, 1.0):
            break
        B0 = float(Be[-1])
    return on, rt, Be


# ------------------------------------------------------------------ Theorem 2: greedy a_max
@njit(cache=True)
def _need_backward(h, n, l):
    """need_j = minimal storage at the END of sub-step j so that idle-only operation survives j+1..J."""
    J = h.size
    need = np.zeros(J)
    nxt = 0.0
    for j in range(J - 1, -1, -1):
        need[j] = nxt
        v = nxt + n * (1.0 + l) - n * h[j]
        nxt = v if v > 0.0 else 0.0
    return need, nxt  # nxt = storage needed at time 0


@njit(cache=True)
def greedy_amax(h, n, r, l, C, B0, margin=0.0):
    """Maximum total activation energy over the horizon (fluid LP), start B0, free end, never empty.

    Greedy: in each sub-step consume as much activation energy as possible while keeping B_j >= need_j.
    Optimality: see THEORY_40 Lemma 3 (exchange argument). Returns (a_bar, feasible, y per sub-step).
    """
    J = h.size
    need, need0 = _need_backward(h, n, l)
    y = np.zeros(J)
    if need0 > B0 + 1e-9:
        return 0.0, False, y
    for j in range(J):
        if need[j] > C + 1e-9:
            return 0.0, False, y
    B = B0
    ymax = n * (r - 1.0)
    tot = 0.0
    for j in range(J):
        free = B + n * h[j] - n * (1.0 + l) - need[j] - margin
        yj = free if free < ymax else ymax
        if yj < 0.0:
            yj = 0.0
        Bn = B + n * h[j] - n * (1.0 + l) - yj
        if Bn > C:
            Bn = C
        B = Bn
        y[j] = yj
        tot += yj
    return tot / ((r - 1.0) * n * J), True, y


@njit(cache=True)
def greedy_int_slots(h, r, l, C, B0):
    """Slot-level integer version (each activation costs r-1 at once). For the brute-force test (d)."""
    T = h.size
    need = np.zeros(T)
    nxt = 0.0
    for t in range(T - 1, -1, -1):
        need[t] = nxt
        v = nxt + (1.0 + l) - h[t]
        nxt = v if v > 0.0 else 0.0
    if nxt > B0 + 1e-12:
        return -1
    B = B0
    cnt = 0
    for t in range(T):
        base = B + h[t] - (1.0 + l)
        if base - (r - 1.0) >= need[t] - 1e-12:
            base -= (r - 1.0)
            cnt += 1
        if base < -1e-12:
            return -1
        B = base if base < C else C
    return cnt


def amax_of_C(h, n, r, l, C):
    a, ok, _ = greedy_amax(np.asarray(h, float), float(n), float(r), float(l), float(C), float(C))
    return a if ok else np.nan


def C_for_amax(h, n, r, l, a_target, C_hi, tol=1e-4):
    """Smallest C with a_max(C) >= a_target (bisection on log C). inf if unattainable at C_hi."""
    if not (amax_of_C(h, n, r, l, C_hi) >= a_target):
        return np.inf
    lo, hi = 0.0, C_hi
    # first a feasibility floor: idle-only must be feasible
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        v = amax_of_C(h, n, r, l, mid)
        if v >= a_target:
            hi = mid
        else:
            lo = mid
        if hi - lo <= tol * hi:
            break
    return hi


# ------------------------------------------------------------------ periodic storage need (Cor. 1.1)
def C_periodic(h, n, r, l, a):
    """Steady-state storage need of constant-rate operation a (fluid) + (r-1) granularity term."""
    net = n * (np.asarray(h, float) - (1.0 + l + a * (r - 1.0)))
    c = storage_need_cyclic(net)
    return c + (r - 1.0) if np.isfinite(c) else np.inf


def C_schedule(h, n, r, l, a_sched):
    net = n * (np.asarray(h, float) - (1.0 + l + np.asarray(a_sched) * (r - 1.0)))
    c = storage_need_cyclic(net)
    return c + (r - 1.0) if np.isfinite(c) else np.inf


# ------------------------------------------------------------------ slot-level reference (validation only)
@njit(cache=True)
def simulate_slots(h, x, r, l, C, B0):
    """Exact slot-level storage with integer activations x_t (blackout: the slot is not served when the
    storage cannot pay for it; only leakage is drawn then). Returns served flags and the storage trace."""
    T = h.size
    served = np.zeros(T, np.int8)
    Bt = np.zeros(T)
    B = B0
    for t in range(T):
        need = 1.0 + l + x[t] * (r - 1.0)
        Bn = B + h[t] - need
        if Bn >= -1e-9:
            served[t] = 1
            B = Bn if Bn < C else C
            if B < 0.0:
                B = 0.0
        else:
            B = B + h[t] - l
            if B < 0.0:
                B = 0.0
            if B > C:
                B = C
        Bt[t] = B
    return served, Bt


# ------------------------------------------------------------------ Theorem 2b / T3(i): energy-tunnel taut string
@njit(cache=True)
def taut_string(L, U):
    """Shortest (taut) path Y with Y[0] = L[0] = U[0], Y[J] = L[J] = U[J] and L <= Y <= U.
    Among all paths in the tube it maximises sum_j Psi(Y[j+1] - Y[j]) for EVERY concave Psi
    (majorisation; energy-tunnel result of Tutuncuoglu & Yener 2012 / Yang & Ulukus 2012)."""
    J = L.size - 1
    Y = np.empty(J + 1)
    i0 = 0
    y0 = L[0]
    Y[0] = y0
    while i0 < J:
        smax = 1e300
        smin = -1e300
        kmax = i0 + 1
        kmin = i0 + 1
        k = i0 + 1
        bent = False
        while k <= J:
            su = (U[k] - y0) / (k - i0)
            sl = (L[k] - y0) / (k - i0)
            if su < smin:
                for t in range(i0 + 1, kmin + 1):
                    Y[t] = y0 + smin * (t - i0)
                y0 = Y[kmin]
                i0 = kmin
                bent = True
                break
            if sl > smax:
                for t in range(i0 + 1, kmax + 1):
                    Y[t] = y0 + smax * (t - i0)
                y0 = Y[kmax]
                i0 = kmax
                bent = True
                break
            if su <= smax:
                smax = su
                kmax = k
            if sl >= smin:
                smin = sl
                kmin = k
            k += 1
        if not bent:
            s = (U[J] - y0) / (J - i0)
            for t in range(i0 + 1, J + 1):
                Y[t] = y0 + s * (t - i0)
            i0 = J
    return Y


def taut_schedule(h, n, r, l, C):
    """Energy-tunnel optimal oblivious schedule, exactly cyclic (no outage when replayed cyclically).

    The cycle is rotated to start right after its largest cumulative surplus (where storage is full in any
    steady state that ever fills) and anchored there: start full, end full. Tube on cumulative activation
    energy Y: S_j <= Y_j <= C + S_j with S = cumsum(n (h - 1 - l)), Y_0 = 0, Y_J = S_J; monotone hull
    (Y non-decreasing). Rates clipped to [0, 1] (clipping only spills energy, never creates an outage).
    Returns None when idle-only operation cannot be sustained over the cycle (blackout regime)."""
    h = np.asarray(h, float)
    J = h.size
    S0 = np.cumsum(n * (h - 1.0 - l))
    rot = int(np.argmax(S0)) + 1
    rot = rot % J
    hr = np.r_[h[rot:], h[:rot]]
    S = np.r_[0.0, np.cumsum(n * (hr - 1.0 - l))]
    if S[-1] < 0:
        return None
    # margin of one activation (r - 1): slot-level integer feasibility and float safety at B = 0
    U = C + S - (r - 1.0)
    U[-1] = S[-1]
    Lo = S.copy()
    Up = np.minimum.accumulate(U[::-1])[::-1]
    Lp = np.maximum.accumulate(Lo)
    if Up[0] < -1e-6 or np.any(Lp > Up + 1e-6 * (1.0 + np.abs(Up))):
        return None
    Lp = np.minimum(Lp, Up)
    Lp[0] = 0.0
    Up[0] = 0.0
    Y = taut_string(Lp, Up)
    a = np.clip(np.diff(Y) / (n * (r - 1.0)), 0.0, 1.0)
    return np.r_[a[J - rot:], a[:J - rot]]


def amax_cyclic_bound(h, n, r, l, C):
    """Valid upper bound on the average activation of ANY cyclic steady-state no-outage policy:
    min(single-pass greedy from full storage, cycle energy balance (h_mean - 1 - l)/(r - 1))."""
    g = amax_of_C(h, n, r, l, C)
    bal = (float(np.mean(h)) - 1.0 - l) / (r - 1.0)
    if not np.isfinite(g):
        return np.nan
    return float(min(g, max(bal, 0.0)))
