"""N4_news: causal headline features per name and session, aligned to harness.load() rows and columns.

Timing rule: a headline belongs to the first session whose date is >= its New York date if its New York time is
<= 16:00:00, else to the first session whose date is > its New York date (weekend / holiday headlines go to the next
session). The feature at row t uses only headlines assigned to sessions <= t. Development cut: created_at <=
2019-12-31T23:59:59Z, filtered at load and asserted.

    python research/tree/N4_news/features.py      -> .cache/tree/extra_news_dev.npz
"""
import os
import sys
import time

import numpy as np
np.seterr(divide="ignore", invalid="ignore")
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402
import lexicon  # noqa: E402

NEWS = os.path.join(harness.ROOT, ".cache", "tree", "news")
OUT = os.path.join(harness.ROOT, ".cache", "tree", "extra_news_dev.npz")
CUT = pd.Timestamp("2019-12-31 23:59:59", tz="UTC")
ARCHIVE_START = pd.Timestamp("2015-01-01")
RANKED = ["cnt1", "cnt5", "cnt21", "abn5", "abn21", "nov5", "nov21", "multi21", "tone5", "tone21", "dsl"]
INDIC = ["has5", "has21"]


def load_headlines(names):
    out = {}
    for t in names:
        d = pd.read_parquet(os.path.join(NEWS, f"{t}.parquet"))
        ts = pd.to_datetime(d["created_at"], utc=True)
        d = d.assign(ts=ts)[ts <= CUT]
        assert (d["ts"] <= CUT).all()
        out[t] = d[["ts", "symbols", "headline"]].reset_index(drop=True)
    mx = max((d["ts"].max() for d in out.values() if len(d)), default=None)
    assert mx is None or mx <= CUT, mx
    return out


def assign_sessions(ts, S):
    """ts: tz-aware UTC Series; S: DatetimeIndex of sessions (dates). Returns session index (-1 if after the last)."""
    ny = ts.dt.tz_convert("America/New_York")
    day = ny.dt.tz_localize(None).dt.normalize()
    sec = (ny.dt.hour * 3600 + ny.dt.minute * 60 + ny.dt.second).to_numpy()
    after = sec > 16 * 3600
    sd = S.normalize().to_numpy()
    i = np.searchsorted(sd, day.to_numpy(), side="left")               # first session with date >= day
    j = np.searchsorted(sd, day.to_numpy(), side="right")              # first session with date > day
    k = np.where(after, j, i)
    k[k >= len(sd)] = -1
    return k


def daily(heads, names, S):
    """Per name and session: counts of all / single-symbol / multi-symbol / novel headlines, tone sum (single only)."""
    T, N = len(S), len(names)
    A = {k: np.zeros((T, N)) for k in ("cnt", "single", "multi", "novel", "tsum")}
    for j, t in enumerate(names):
        d = heads.get(t)
        if d is None or not len(d):
            continue
        s = assign_sessions(d["ts"], S)
        d = d.assign(s=s)[s >= 0].sort_values("ts")
        multi = d["symbols"].str.contains(",").to_numpy()
        last, novel = {}, np.zeros(len(d), bool)
        for q, (key, ss) in enumerate(zip(d["headline"].map(lexicon.normalise), d["s"].to_numpy())):
            novel[q] = key not in last or ss - last[key] > 21
            last[key] = ss
        tn = d["headline"].map(lexicon.tone).to_numpy()
        ss = d["s"].to_numpy()
        np.add.at(A["cnt"][:, j], ss, 1)
        np.add.at(A["multi"][:, j], ss, multi)
        np.add.at(A["single"][:, j], ss, ~multi)
        np.add.at(A["novel"][:, j], ss, novel)
        np.add.at(A["tsum"][:, j], ss, np.where(multi, 0.0, tn))
    return A


def _win(a, w, end_lag=0):
    """Sum over sessions t-end_lag-w+1 .. t-end_lag (NaN where the window starts before row 0)."""
    c = np.vstack([np.zeros((1, a.shape[1])), np.cumsum(a, 0)])
    out = np.full(a.shape, np.nan)
    t = np.arange(len(a))
    hi, lo = t - end_lag + 1, t - end_lag - w + 1
    ok = lo >= 0
    out[ok] = c[hi[ok]] - c[lo[ok]]
    return out


def raw_features(A, S, start=ARCHIVE_START):
    """Raw (unranked) features; NaN where the window reaches before the archive start."""
    T = len(S)
    s0 = int(np.searchsorted(S.to_numpy(), np.datetime64(start)))
    pre = np.arange(T)[:, None] - s0                                   # sessions since archive start
    cnt = A["cnt"]
    F = {}
    for w in (1, 5, 21):
        x = _win(cnt, w)
        x[(pre < w - 1).ravel()] = np.nan
        F[f"cnt{w}"] = x
    c = np.vstack([np.zeros((1, cnt.shape[1])), np.cumsum(cnt, 0)])
    t = np.arange(T)
    for w, nm in ((5, "abn5"), (21, "abn21")):
        cur = _win(cnt, w) / w
        # baseline: mean daily count over archive sessions max(s0, t-w-125) .. t-w (up to 126, at least 63)
        hi = t - w
        lo = np.maximum(s0, hi - 125)
        nb = hi - lo + 1
        okb = nb >= 63
        m = np.full(cnt.shape, np.nan)
        m[okb] = (c[hi[okb] + 1] - c[lo[okb]]) / nb[okb, None]
        x = np.log((cur + 1 / 21) / (m + 1 / 21))
        x[~(m > 0)] = np.nan                                           # no baseline: explicit missing
        F[nm] = x
    for w in (5, 21):
        n = _win(cnt, w)
        nov = _win(A["novel"], w) / n
        nov[n == 0] = np.nan
        nov[(pre < w - 1).ravel()] = np.nan
        F[f"nov{w}"] = nov
        sg = _win(A["single"], w)
        tn = _win(A["tsum"], w) / sg
        tn[sg == 0] = np.nan
        tn[(pre < w - 1).ravel()] = np.nan
        F[f"tone{w}"] = tn
        h = (n > 0).astype(float)
        h[(pre < w - 1).ravel()] = np.nan
        F[f"has{w}"] = h
    n21 = _win(cnt, 21)
    mu = _win(A["multi"], 21) / n21
    mu[n21 == 0] = np.nan
    mu[(pre < 20).ravel()] = np.nan
    F["multi21"] = mu
    # sessions since last headline (capped 252); before any headline since the archive start: 252
    dsl = np.full(cnt.shape, 252.0)
    last = np.full(cnt.shape[1], -10 ** 6)
    for t in range(s0, T):
        last = np.where(cnt[t] > 0, t, last)
        dsl[t] = np.minimum(t - last, 252)
    dsl[:s0] = np.nan
    F["dsl"] = dsl
    return F


def xrank(a, elig):
    a = a.copy()
    a[~elig] = np.nan
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def ranked(F, elig):
    """(T, N, K) float32: ranked features (NaN -> 0), then indicators coded +-0.5 (0 before the archive / off-elig)."""
    cols = [np.nan_to_num(xrank(F[k], elig), nan=0.0) for k in RANKED]
    for k in INDIC:
        x = F[k] - 0.5
        x[~elig] = np.nan
        cols.append(np.nan_to_num(x, nan=0.0))
    return np.stack(cols, 2).astype(np.float32)


def main():
    t0 = time.time()
    D = harness.load()
    heads = load_headlines(D["names"])
    A = daily(heads, D["names"], D["S"])
    F = raw_features(A, D["S"])
    X = ranked(F, D["elig"])
    n_all = sum(len(d) for d in heads.values())
    note = ("N4_news development headline features (research/tree/N4_news/features.py). Alpaca/Benzinga headlines, "
            f"created_at <= 2019-12-31T23:59:59Z only ({n_all} headline-name rows); archive starts 2015-01-01 (features "
            "NaN/neutral before their windows fill). Session rule: after 16:00:00 New York -> next session; row t uses "
            "sessions <= t. X = ranked features " + ",".join(RANKED) + " (cross-sectional pct rank - 0.5 over eligible "
            "names, NaN -> 0) then indicators " + ",".join(INDIC) + " (+-0.5, 0 when unknown). Tone = HAND word list "
            "(lexicon.py), not Loughran-McDonald; single-symbol headlines only. raw_* = unranked values.")
    np.savez_compressed(OUT, X=X, names_X=np.array(RANKED + INDIC), note=np.array(note),
                        **{f"raw_{k}": v.astype(np.float32) for k, v in F.items()},
                        daily_cnt=A["cnt"].astype(np.float32), daily_multi=A["multi"].astype(np.float32))
    print("saved", OUT, X.shape, f"{time.time() - t0:.0f}s", flush=True)


def load():
    z = np.load(OUT, allow_pickle=False)
    return {k: z[k] for k in z.files}


if __name__ == "__main__":
    main()
