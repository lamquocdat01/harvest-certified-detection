"""Event corpus for topic 40, built here from per-frame detection records (R18: no inherited CSV).

Rule (same extraction protocol as events_gated of the 09.05 pipeline, re-implemented):
    event = a maximal run of consecutive frames in which the detector reports >= 1 box.
Datasets kept: CDnet2014, LASIESTA, BMC (VIRAT clips are 500-frame truncation stubs -> excluded).
Videos with no detection at all carry no event and are dropped.

Outputs: results/event_corpus_40.csv (dataset, video, n_frames, event_id, onset, duration)
         results/corpus_rebuild_check.json (identity vs events_gated.csv, F_D hash)

Duration law helpers: phi(g) = E[min(g, D)], Psi(a) = E[min(1, a D)] = 1 - eps*(a).
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as cfg

DATASETS = ("CDnet2014", "LASIESTA", "BMC")
OUT_CSV = cfg.RES / "event_corpus_40.csv"


def _events_from_frames(frames):
    ev, on, start = [], False, 0
    for rec in frames:
        act = len(rec.get("boxes", ())) > 0
        if act and not on:
            start, on = rec["frame"], True
        elif not act and on:
            ev.append((start, rec["frame"] - start))
            on = False
    if on:
        ev.append((start, frames[-1]["frame"] - start + 1))
    return ev


def build_corpus(root=cfg.DET):
    rows = []
    for ds in DATASETS:
        for f in sorted((root / ds).glob("*.json")):
            frames = json.loads(f.read_text(encoding="utf-8")).get("frames", [])
            if not frames:
                continue
            evs = _events_from_frames(frames)
            if not evs:
                continue
            stem = f.stem
            video = stem.split("__", 1)[1] if "__" in stem else stem
            for i, (o, d) in enumerate(evs):
                rows.append((ds, video, len(frames), i, o, d))
    return pd.DataFrame(rows, columns=["dataset", "video", "n_frames", "event_id", "onset", "duration"])


def durations_hash(d):
    """Order-free hash of the duration multiset (the F_D law)."""
    return hashlib.sha256(np.sort(np.asarray(d, np.int64)).tobytes()).hexdigest()


def rebuild_and_check():
    ev = build_corpus()
    cfg.RES.mkdir(exist_ok=True)
    ev.to_csv(OUT_CSV, index=False, lineterminator="\n")
    sha_out = hashlib.sha256(OUT_CSV.read_bytes()).hexdigest()
    ref = pd.read_csv(cfg.LEGACY_EVENTS)
    sha_ref = hashlib.sha256(cfg.LEGACY_EVENTS.read_bytes()).hexdigest()
    a = ev[["dataset", "video", "onset", "duration"]].sort_values(["dataset", "video", "onset"]).reset_index(drop=True)
    b = ref[["dataset", "video", "onset", "duration"]].sort_values(["dataset", "video", "onset"]).reset_index(drop=True)
    rows_identical = bool(a.shape == b.shape and (a.values == b.values).all())
    fd_mine, fd_ref = durations_hash(ev.duration), durations_hash(ref.duration)
    res = {
        "rule": "event = maximal run of consecutive frames with >= 1 detection box; datasets CDnet2014, LASIESTA, BMC",
        "detections_root": str(cfg.DET),
        "n_videos": int(ev.groupby(["dataset", "video"]).ngroups), "n_events": int(len(ev)),
        "n_frames_total": int(ev.drop_duplicates(["dataset", "video"]).n_frames.sum()),
        "per_dataset_videos": ev.drop_duplicates(["dataset", "video"]).dataset.value_counts().to_dict(),
        "event_corpus_40_csv_sha256": sha_out,
        "reference": {"path": str(cfg.LEGACY_EVENTS), "sha256": sha_ref, "sha_expected": cfg.LEGACY_EVENTS_SHA,
                      "sha_ok": sha_ref == cfg.LEGACY_EVENTS_SHA, "n_events": int(len(ref))},
        "rows_identical_dataset_video_onset_duration": rows_identical,
        "F_D_hash_mine": fd_mine, "F_D_hash_reference": fd_ref, "F_D_identical": fd_mine == fd_ref,
    }
    assert res["n_videos"] == 121 and res["n_events"] == 3713, res
    assert res["F_D_identical"] and rows_identical, "corpus rebuild differs from events_gated.csv"
    (cfg.RES / "corpus_rebuild_check.json").write_text(json.dumps(res, indent=1))
    return ev, res


@lru_cache(maxsize=1)
def load_corpus():
    if not OUT_CSV.exists():
        rebuild_and_check()
    return pd.read_csv(OUT_CSV)


# ------------------------------------------------------------------ duration law
class DurationLaw:
    """Empirical F_D on integer support. Vectorised phi, Psi for many gaps / rates at once."""

    def __init__(self, durations, weights=None):
        d = np.asarray(durations, np.int64)
        w = np.ones(d.size) if weights is None else np.asarray(weights, float)
        self.dmax = int(d.max())
        pmf = np.bincount(d, weights=w, minlength=self.dmax + 1).astype(float)
        pmf /= pmf.sum()
        self.pmf = pmf
        self.surv = 1.0 - np.cumsum(pmf)            # surv[k] = P(D > k)
        # phi(g) = sum_{k=0}^{g-1} P(D > k); phi(0) = 0; for g > dmax phi = E[D]
        self._phi = np.r_[0.0, np.cumsum(self.surv)]  # length dmax+2, phi[g]; surv[0] = P(D > 0) = 1
        self.mean = float(self._phi[-1])

    def phi(self, g):
        g = np.asarray(g, np.int64)
        return np.where(g <= self.dmax + 1, self._phi[np.minimum(g, self.dmax + 1)], self.mean)

    def psi(self, a):
        """Psi(a) = E[min(1, a D)] = P(D >= ceil(1/a)) + a * E[D; D < 1/a], exact for real a in [0, 1]."""
        a = np.atleast_1d(np.asarray(a, float))
        if not hasattr(self, "_tail"):
            k = np.arange(self.pmf.size)
            self._tail = np.r_[1.0 - np.r_[0.0, np.cumsum(self.pmf)][:-1], 0.0]    # tail[k] = P(D >= k)
            self._s1 = np.r_[0.0, np.cumsum(k * self.pmf)]                         # s1[k] = E[D; D < k]
        with np.errstate(divide="ignore"):
            cut = np.where(a > 0, np.ceil(1.0 / np.maximum(a, 1e-300) - 1e-9), np.inf)
        cut = np.minimum(cut, self.pmf.size).astype(np.int64)
        return np.where(a > 0, self._tail[cut] + a * self._s1[cut], 0.0)

    def eps_star(self, a):
        return 1.0 - self.psi(a)

    def a_eps(self, eps, tol=1e-10):
        """Smallest a with eps*(a) <= eps (eps* is non-increasing and continuous)."""
        if eps >= 1:
            return 0.0
        if self.eps_star(1.0)[0] > eps:
            return np.nan
        lo, hi = 0.0, 1.0
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if self.eps_star(mid)[0] <= eps:
                hi = mid
            else:
                lo = mid
        return hi

    def conditional(self, dmin):
        """Law of D given D >= dmin."""
        k = np.arange(self.pmf.size)
        w = np.where(k >= dmin, self.pmf, 0.0)
        return DurationLaw(k[w > 0], w[w > 0])


def corpus_law(ev=None):
    ev = load_corpus() if ev is None else ev
    return DurationLaw(ev.duration.values)


if __name__ == "__main__":
    _, r = rebuild_and_check()
    print(json.dumps({k: r[k] for k in ("n_videos", "n_events", "F_D_identical", "rows_identical_dataset_video_onset_duration")}))


def video_split(ev=None, seed=42):
    """TRAIN/TEST split of the corpus by video (half/half, seeded permutation)."""
    ev = load_corpus() if ev is None else ev
    keys = sorted(set(ev.dataset + "/" + ev.video))
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(keys))
    train = {keys[i] for i in perm[: len(keys) // 2]}
    return train


def law_for(split=None):
    ev = load_corpus()
    if split in (None, "all"):
        return corpus_law(ev)
    tr = video_split(ev)
    key = ev.dataset + "/" + ev.video
    sel = key.isin(tr) if split == "train" else ~key.isin(tr)
    return DurationLaw(ev.duration.values[sel.values])
