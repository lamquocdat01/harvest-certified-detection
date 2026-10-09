"""Sanity checks 1.7 (a)-(d) of PROMPT_40 P1+P2 and loader/fluid checks (2.3).

Any failure must be REPORTED, never fixed by editing a theorem (rule in THEORY_40 sec. 7)."""
import itertools

import numpy as np

from sim40 import energy as E
from sim40 import traces as T
from sim40.events import corpus_law

LAW = corpus_law()
RNG = np.random.default_rng(42)


def exact_catch(x, law=LAW):
    """Exact P(catch) of a cyclic 0/1 schedule: onset s uniform, caught iff D > dist(s -> next activation)."""
    x = np.asarray(x, bool)
    Tn = x.size
    if not x.any():
        return 0.0
    idx = np.flatnonzero(x)
    pos = np.arange(Tn)
    nxt = idx[np.searchsorted(idx, pos) % idx.size]
    dist = (nxt - pos) % Tn
    surv = np.r_[law.surv, 0.0]
    return float(surv[np.minimum(dist, surv.size - 1)].mean())


def gap_catch(x, law=LAW):
    """Theorem 1(ii) gap functional: (1/T) sum_i phi(g_i)."""
    idx = np.flatnonzero(x)
    g = np.diff(np.r_[idx, idx[0] + x.size])
    return float(law.phi(g).sum() / x.size)


def random_policy(kind, Tn, rng):
    if kind == "periodic":
        K = int(rng.integers(1, 200))
        x = np.zeros(Tn, bool)
        x[int(rng.integers(0, K))::K] = True
    elif kind == "bernoulli":
        x = rng.random(Tn) < rng.uniform(0.002, 0.9)
    elif kind == "burst":   # on-blocks of length Bl with in-block rate q
        Bl = int(rng.integers(5, 2000))
        q = rng.uniform(0.05, 1.0)
        per = max(int(round(1 / rng.uniform(0.05, 0.95))), 1)
        x = ((np.arange(Tn) // Bl) % per == 0) & (rng.random(Tn) < q)
    else:                   # diurnal: rate follows a clipped sine of random period
        P = int(rng.integers(50, Tn))
        rate = np.clip(rng.uniform(0.01, 1.0) * np.sin(2 * np.pi * np.arange(Tn) / P), 0, 1)
        x = rng.random(Tn) < rate
    if not x.any():
        x[int(rng.integers(0, Tn))] = True
    return x


def test_a_theorem1_no_violation():
    """(a) 1e4 random oblivious policies x real F_D: catch <= Psi(a) = 1 - eps*(a); gap formula exact."""
    n_viol, worst = 0, -1.0
    kinds = ("periodic", "bernoulli", "burst", "diurnal")
    for i in range(10_000):
        x = random_policy(kinds[i % 4], int(RNG.integers(500, 6000)), RNG)
        c = exact_catch(x)
        bound = float(LAW.psi(x.mean())[0])
        worst = max(worst, c - bound)
        n_viol += c > bound + 1e-12
        assert abs(c - gap_catch(x)) < 1e-12
    assert n_viol == 0, (n_viol, worst)


def test_a2_monte_carlo_events():
    """(a') sampled events (not the exact formula) agree with exact_catch within 4 sigma."""
    for K in (3, 8, 33):
        Tn = 50_000
        x = np.zeros(Tn, bool)
        x[::K] = True
        s = RNG.integers(0, Tn, 200_000)
        d = RNG.choice(np.arange(LAW.pmf.size), size=s.size, p=LAW.pmf)
        idx = np.flatnonzero(x)
        nxt = idx[np.searchsorted(idx, s) % idx.size]
        caught = ((nxt - s) % Tn) < d
        p = exact_catch(x)
        assert abs(caught.mean() - p) < 4 * np.sqrt(p * (1 - p) / s.size)


def test_b_tightness_periodic_and_interleaved():
    """(b) periodic K and interleaved floor/ceil (non-integer K) attain Psi(a) exactly (<= 1e-3 asked)."""
    for K in range(1, 65):
        x = np.zeros(K * 97, bool)
        x[::K] = True
        assert abs(exact_catch(x) - LAW.psi(1 / K)[0]) <= 1e-12
    for Kr in (2.5, 3.3, 7.7, 12.25, 40.1):
        n_act = 400
        pos = np.floor(np.arange(n_act) * Kr).astype(int)          # gaps in {floor K, ceil K}
        x = np.zeros(int(np.floor(n_act * Kr)), bool)
        x[pos] = True
        assert abs(exact_catch(x) - LAW.psi(x.mean())[0]) <= 1e-12
    # converse: gaps 3 and 17 straddle d with pmf > 0 -> strictly below the bound
    x = np.zeros(20, bool)
    x[[0, 3]] = True
    assert exact_catch(x) < LAW.psi(0.1)[0] - 1e-6


def test_c_lemma1_bruteforce():
    """(c) storage never negative (start full)  <=>  C >= max drawdown of (h - e)."""
    for _ in range(300):
        Tn = int(RNG.integers(20, 400))
        r = float(RNG.choice([1.1, 2, 5, 15, 40]))
        l = float(RNG.choice([0, .01, .1]))
        h = RNG.gamma(0.6, 2.0, Tn) * (RNG.random(Tn) < 0.6)
        x = (RNG.random(Tn) < RNG.uniform(0, 0.5)).astype(np.int64)
        Cs = E.max_drawdown(h - (1 + l + x * (r - 1)))
        for C, expect in ((Cs * 1.0000001 + 1e-9, True), (Cs * 0.999 - 1e-6, False)):
            if C <= 0:
                continue
            served, _ = E.simulate_slots(h, x, r, l, C, C)
            assert bool(served.all()) == expect


def test_d_amax_greedy_vs_exhaustive():
    """(d) integer greedy == exhaustive maximum over {0,1}^T (T <= 14); fluid greedy >= it."""
    for _ in range(150):
        Tn = int(RNG.integers(6, 15))
        r = float(RNG.choice([2, 3, 5]))
        l = float(RNG.choice([0, .1]))
        h = RNG.choice([0.0, 0.5, 2.0, 4.0, 6.0], size=Tn)
        C = float(RNG.uniform(1, 12))
        best = -1
        X = np.array(list(itertools.product([0, 1], repeat=Tn)), dtype=np.int64)
        for x in X[np.argsort(-X.sum(1), kind="stable")]:
            if x.sum() <= best:
                break
            served, _ = E.simulate_slots(h, x, r, l, C, C)
            if served.all():
                best = int(x.sum())
        g = E.greedy_int_slots(h, r, l, C, C)
        assert g == best, (g, best, h, C)
        if best >= 0:
            af, ok, _ = E.greedy_amax(h, 1.0, r, l, C, C)
            assert ok and af * Tn >= best - 1e-9


def test_loader_integral():
    """2.3: energy integral before/after interpolation differs <= 0.1 %; zoh equals the native integral."""
    for site, sea in (("HCMC", "JJA"), ("Uppsala-SARAH3", "DJF"), ("Madrid-MSG", "SON")):
        g0, meta = T.season_series(site, sea, interp="zoh")
        g1, _ = T.season_series(site, sea, interp="linear")
        assert abs(g1.sum() - g0.sum()) / g0.sum() <= 1e-3
        s, step, _ = T.load_outdoor(site)
        start = s.index - __import__("pandas").Timedelta(seconds=step)
        native = s[start.month.isin(meta["order"])].sum() * step
        assert abs(g0.sum() * 60 - native) / native <= 1e-9


def test_fluid_vs_slot_level():
    """Fluid 1-min model vs exact slot-level storage, periodic K, 2 days of a real trace at 10 fps."""
    g, _ = T.season_series("Madrid-MSG", "DJF")
    r, l, K = 15.0, 0.04, 8
    h_sub = T.scale_panel(g, r, l, 0.25)[: 2 * 1440]
    h_slot = np.repeat(h_sub, 600)
    x = np.zeros(h_slot.size, np.int64)
    x[::K] = 1
    C = 0.6 * E.max_drawdown(600 * (h_sub - (1 + l + (r - 1) / K)))
    served, Bt = E.simulate_slots(h_slot, x, r, l, C, C)
    on, rt, Be, _ = E.simulate(h_sub, np.full(h_sub.size, 1 / K), 600., r, l, C, C, 0.0, 0, 0., 0., 0., 1440,
                               np.zeros(1))
    assert served.mean() < 1.0                      # the case exercises an outage
    assert abs(served.mean() - on.mean()) < 0.01
    # storage agrees within one activation (r-1) up to the first outage; near-empty flicker differs by
    # at most one sub-step of income (per-minute vs per-slot cut-off) and re-syncs when storage refills to C
    first_out = int(np.argmax(on < 1))
    assert first_out > 0
    assert np.max(np.abs(Bt[599::600][:first_out] - Be[:first_out])) <= (r - 1) + 1e-6
