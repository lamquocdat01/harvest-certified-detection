"""Harvest traces -> per-sub-step harvest series (1-minute sub-steps of n = 600 slots at 10 fps).

Outdoor: Open-Meteo satellite GHI (W/m2), native resolution (Himawari 10 min, MSG 15 min, SARAH-3 30 min).
         Open-Meteo `shortwave_radiation` is the mean over the PRECEDING interval, so the value stamped t
         is held on (t - step, t].
Indoor:  EnHANTS Setups B-F irradiance (uW/cm2), 30 s -> 1 min means (as in P0), gaps <= 10 min interpolated,
         longer gaps cut the record into segments; segments are concatenated (joins listed in metadata).

Interpolation to sub-steps (both conserve energy; the default is exact):
    'zoh'    : zero-order hold of each interval mean -> integral preserved exactly.
    'linear' : linear interpolation between interval MIDPOINTS, clipped at 0, then rescaled per day so the
               daily integral equals the original (sensitivity variant).
Panel scaling (dimensionless): h_t = s * g_t with s chosen so that the horizon-mean harvest per slot equals
(1 + m) * e_ref, e_ref = 1 + l + (r - 1)/K_REF  ("season-neutral panel for the design point K_REF").
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as cfg

SUB_S = 60  # sub-step length (s)


@lru_cache(maxsize=None)
def load_outdoor(site):
    stem = cfg.SITES_OUT[site]
    d = pd.read_csv(cfg.SAT / f"{stem}.csv", parse_dates=["time_utc"])
    s = d.set_index("time_utc")["ghi_wm2"].astype(float)
    step = int(s.index.to_series().diff().dt.total_seconds().median())
    n_nan = int(s.isna().sum())
    s = s.interpolate(limit=int(3600 / step), limit_area="inside").fillna(0.0)  # as P0
    return s, step, n_nan


@lru_cache(maxsize=None)
def load_indoor(setup):
    f = sorted(cfg.ENH.glob(f"{setup.lower()}*/*.txt"))[0]
    d = pd.read_csv(f, sep=r"\s+", skiprows=1, header=None, usecols=range(8),
                    names=["sec", "irr", "y", "mo", "d", "hh", "mm", "ss"])
    t = pd.to_datetime(dict(year=d.y, month=d.mo, day=d.d, hour=d.hh, minute=d.mm, second=d.ss), errors="coerce")
    s = pd.Series(d.irr.values, index=t).dropna()
    s = s[~s.index.duplicated()].sort_index().resample("60s").mean()
    s = s.interpolate(limit=10, limit_area="inside")
    ok = s.notna().values
    idx = np.flatnonzero(np.diff(np.r_[0, ok.astype(int), 0]))
    segs = [s.iloc[a:b] for a, b in zip(idx[::2], idx[1::2]) if b - a > 1]
    return segs, f.name


def _to_substeps(s, step, interp):
    """Series of interval means (stamped at interval end) -> array of 1-min sub-step values."""
    k = step // SUB_S
    v = s.values.astype(float)
    if interp == "zoh" or k == 1:
        return np.repeat(v, k)
    # linear between midpoints
    tm = (np.arange(v.size) + 0.5) * k          # midpoints in sub-step units
    tq = np.arange(v.size * k) + 0.5
    out = np.clip(np.interp(tq, tm, v), 0.0, None)
    # daily integral correction
    per_day = 1440
    ref = np.repeat(v, k)
    for d0 in range(0, out.size, per_day):
        a, b = out[d0:d0 + per_day].sum(), ref[d0:d0 + per_day].sum()
        if a > 0:
            out[d0:d0 + per_day] *= b / a
    return out


def _keep_month(month, split):
    if split in (None, "all"):
        return True
    return (month % 2 == 1) if split == "train" else (month % 2 == 0)


def season_series(site, season, interp="zoh", split=None):
    """Raw (unscaled) harvest per 1-min sub-step for one cell, plus metadata.
    Outdoor season: months concatenated in climatological order (DJF = Dec, Jan, Feb of 2025), treated cyclic.
    Indoor: season 'ALL' = whole valid record (segments concatenated)."""
    if site in cfg.SITES_OUT:
        s, step, n_nan = load_outdoor(site)
        months = cfg.SEASONS[season] if season != "YEAR" else tuple(range(1, 13))
        # interval (t-step, t] belongs to the month of its start
        start = s.index - pd.Timedelta(seconds=step)
        parts = [s[start.month == m] for m in months if _keep_month(m, split)]
        g = np.concatenate([_to_substeps(p, step, interp) for p in parts])
        meta = {"source": cfg.SITES_OUT[site], "step_s": step, "nan_steps_year": n_nan, "days": g.size / 1440,
                "unit": "W/m2", "order": [m for m in months if _keep_month(m, split)], "split": split}
        return g, meta
    segs, fname = load_indoor(site)
    if season not in ("ALL",):
        raise ValueError("indoor traces use season 'ALL'")
    segs = [x[np.array([_keep_month(mm, split) for mm in x.index.month])] for x in segs]
    segs = [x for x in segs if len(x) > 1]
    g = np.concatenate([x.values.astype(float) for x in segs])
    meta = {"source": fname, "step_s": 60, "segments": len(segs), "days": g.size / 1440, "unit": "uW/cm2",
            "split": split}
    return g, meta


def cells():
    out = [(s, sea) for s in cfg.SITES_OUT for sea in cfg.SEASONS]
    out += [(s, "ALL") for s in cfg.SITES_IN]
    return out


def scale_panel(g, r, l, m, k_ref=cfg.K_REF):
    """Dimensionless harvest per slot: mean = (1 + m) * (1 + l + (r - 1)/k_ref)."""
    e_ref = 1.0 + l + (r - 1.0) / k_ref
    return g * ((1.0 + m) * e_ref / g.mean())


def integral_check(site, season):
    g0, meta = season_series(site, season, "zoh")
    g1, _ = season_series(site, season, "linear")
    s, step, _ = (load_outdoor(site) if site in cfg.SITES_OUT else (None, 60, 0))
    return {"zoh_vs_linear_rel": float(abs(g1.sum() - g0.sum()) / g0.sum())}
