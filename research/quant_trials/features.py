"""Quant trials · features, targets, folds and metrics on the Stage-0 panel.

Timing (one session of execution gap, so a headline mis-stamped by hours can never reach the target):
    features at decision session d use prices <= close(d) and headlines whose session is <= d;
    target y_h(d) = sum_{k=d+2}^{d+1+h} (r_k - beta_d * r_SPY,k), i.e. close(d+1) -> close(d+1+h),
    cross-sectionally demeaned; it exists only when d+1+h is a session <= 2025-12-31.
"""

import json
import math
import os

import numpy as np
import pandas as pd

import panel as P

PRICE_COLS = ["e1", "e5", "e20", "e60", "vol20", "volz", "spy5", "vix", "beta"]
INTENSITY_COLS = ["n_today", "n_decay5", "days_since"]
FIT_START = pd.Timestamp("2016-01-04")
INNER_FOLDS = (2019, 2020, 2021)


class Panel:
    """Everything on the session calendar S (D sessions) x names (N)."""

    def __init__(self, names=P.UNIVERSE):
        self.names = list(names)
        self.S, self.tsum, self.n = P.load_text(names=self.names)
        px = P.load_prices()
        S = self.S
        close = px["Close"].reindex(S)[self.names]
        vol = px["Volume"].reindex(S)[self.names]
        self.close, self.open = close.values, px["Open"].reindex(S)[self.names].values
        self.volume = vol.values
        spy = px["Close"]["SPY"].reindex(S)
        self.vix = px["Close"]["^VIX"].reindex(S).ffill().values
        r = close.pct_change()
        rm = spy.pct_change()
        self.r, self.rm = r.values, rm.values
        # Welch beta (fund/backtest_levels.py welch_beta) on a trailing 252-session window, shrunk 2/3 + 1/3
        lo, hi = np.minimum(-2 * self.rm, 4 * self.rm)[:, None], np.maximum(-2 * self.rm, 4 * self.rm)[:, None]
        w = pd.DataFrame(np.clip(self.r, lo, hi), index=S)
        m = pd.Series(self.rm, index=S)
        cov = w.rolling(252, min_periods=200).cov(m)
        var = m.rolling(252, min_periods=200).var()
        b = cov.div(var, axis=0)
        self.beta = ((2 / 3) * b.fillna(1.0) + 1 / 3).values
        bprev = np.vstack([np.full((1, len(self.names)), np.nan), self.beta[:-1]])
        self.e = self.r - bprev * self.rm[:, None]                 # residual return of day t, beta from t-1
        self._price_feats()
        self._intensity()
        self._quant_feats()
        self.D, self.N = len(S), len(self.names)

    def _price_feats(self):
        S, e = self.S, pd.DataFrame(self.e, index=self.S)
        f = {}
        for k in (1, 5, 20, 60):
            f[f"e{k}"] = e.rolling(k, min_periods=k).sum().values
        f["vol20"] = pd.DataFrame(self.r, index=S).rolling(20, min_periods=15).std().values
        lv = pd.DataFrame(np.log1p(self.volume), index=S)
        f["volz"] = ((lv - lv.rolling(60, min_periods=40).mean()) / lv.rolling(60, min_periods=40).std()).values
        f["spy5"] = np.repeat(pd.Series(self.rm).rolling(5).sum().values[:, None], len(self.names), 1)
        f["vix"] = np.repeat(np.log(self.vix)[:, None], len(self.names), 1)
        f["beta"] = self.beta
        self.price = np.stack([f[c] for c in PRICE_COLS], -1).astype(np.float32)

    def _quant_feats(self):
        """The shadow quant book's five signals (fund/screen.py), on the session calendar, z-scored across the
        31 names per day, and the frozen ridge score (artefacts/llm/ridge_stocks.json; fit 2004-01..2026-03, so
        in-sample on every historical window)."""
        lp = pd.DataFrame(np.log(self.close), index=self.S)
        lr = lp.diff()
        f = {"mom12_1": (lp.shift(20) - lp.shift(252)).values, "rev1m": -(lp - lp.shift(20)).values,
             "rev1w": -(lp - lp.shift(5)).values, "lowvol": -lr.rolling(60, min_periods=50).std().values,
             "high52": (pd.DataFrame(self.close, index=self.S)
                        / pd.DataFrame(self.close, index=self.S).rolling(252, min_periods=200).max()).values}
        spec = json.load(open(os.path.join(P.ROOT, "artefacts", "llm", "ridge_stocks.json")))
        Z = np.stack([f[c] for c in spec["features"]], -1)
        Z = (Z - np.nanmean(Z, 1, keepdims=True)) / np.nanstd(Z, 1, keepdims=True)
        self.quant = Z.astype(np.float32)
        self.quant_score = (Z @ np.asarray(spec["coef"]) + spec["intercept"]).astype(np.float32)

    def _intensity(self):
        n = self.n.astype(np.float32)
        lam = 0.5 ** (1 / 5)
        dec = np.zeros_like(n)
        since = np.zeros_like(n)
        acc, last = np.zeros(n.shape[1], np.float32), np.full(n.shape[1], 60.0, np.float32)
        for t in range(len(n)):
            acc = lam * acc + n[t]
            last = np.where(n[t] > 0, 0.0, np.minimum(last + 1, 60.0))
            dec[t], since[t] = acc, last
        self.intensity = np.stack([np.log1p(n), np.log1p(dec), np.log1p(since)], -1).astype(np.float32)

    def target(self, h):
        """y_h(d), NaN where the window would run past the panel; cross-sectionally demeaned."""
        D = len(self.S)
        y = np.full((D, len(self.names)), np.nan)
        r, rm = np.nan_to_num(self.r), np.nan_to_num(self.rm)
        cr, cm = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(r, 0)]), np.concatenate([[0], np.cumsum(rm)])
        for d in range(D - 1 - h):
            a, b = d + 2, d + 2 + h                                   # sessions d+2 .. d+1+h inclusive
            y[d] = (cr[b] - cr[a]) - self.beta[d] * (cm[b] - cm[a])
        y[np.isnan(self.r)] = np.nan
        return y - np.nanmean(y, 1, keepdims=True)

    def level_target(self, h):
        """Trial A (the paper's target): the close h sessions ahead."""
        y = np.full(self.close.shape, np.nan)
        y[:-h] = self.close[h:]
        return y

    def state(self, hl):
        """Decayed mean headline vector (D, N, DIM): hl=0 means today's session mean only."""
        if hl == 0:
            with np.errstate(invalid="ignore", divide="ignore"):
                return np.where(self.n[..., None] > 0, self.tsum / np.maximum(self.n, 1)[..., None], 0.0).astype(np.float32)
        lam = np.float32(0.5 ** (1 / hl))
        out = np.empty_like(self.tsum)
        S, W = np.zeros(self.tsum.shape[1:], np.float32), np.zeros(self.n.shape[1], np.float32)
        for t in range(len(self.tsum)):
            S = lam * S + self.tsum[t]
            W = lam * W + self.n[t]
            out[t] = np.where(W[:, None] > 1e-3, S / np.maximum(W, 1e-3)[:, None], 0.0)
        return out


def fold_index(p, test_year, h, start=FIT_START, end_year=None):
    """Decision indices: train = sessions from `start` whose target ends before the first test session
    (h-session embargo), test = sessions in `test_year` (or test_year..end_year)."""
    S = p.S
    yrs = S.year
    test = np.where((yrs >= test_year) & (yrs <= (end_year or test_year)))[0]
    test = test[test + 1 + h <= test[-1]]                     # whole target window inside the test period
    first = test[0]
    train = np.where((S >= start) & (np.arange(len(S)) + 1 + h < first))[0]
    return train, test


def split_val(train, frac=0.2, h=5):
    """Last `frac` of the training decisions for early stopping, with an h-session gap."""
    cut = int(len(train) * (1 - frac))
    return train[: max(cut - h - 1, 1)], train[cut:]


def thursdays(p, idx):
    return idx[p.S[idx].weekday == 3]


# ---------------------------------------------------------------------------------------------------- metrics
def nw_t(x, L=2):
    """Newey-West t of the mean (fund/score.py nw_t)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 3 or x.std() == 0:
        return np.nan
    e = x - x.mean()
    s = e @ e / len(x)
    for k in range(1, min(L, len(x) - 1) + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


def nw_lag(h):
    return max(2, math.ceil(h / 5))


def weekly_ic(pred, y, idx):
    """Spearman IC across names per decision in idx (rows with >= 10 valid names)."""
    out = []
    for d in idx:
        m = ~np.isnan(pred[d]) & ~np.isnan(y[d])
        if m.sum() < 10:
            out.append(np.nan)
            continue
        a = pd.Series(pred[d][m]).rank().values
        b = pd.Series(y[d][m]).rank().values
        out.append(np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else np.nan)
    return np.array(out)


def sector_ids(names):
    """Sector cluster per name (panel.SECTORS); the five unclustered names form one 'other' group."""
    lab = {t: g for g, ts in P.SECTORS.items() for t in ts}
    return np.array([lab.get(t, "other") for t in names])


def neutralise(a, groups):
    """Demean each row within groups (sector-neutral predictions or targets)."""
    out = a.copy()
    for g in np.unique(groups):
        m = groups == g
        out[:, m] = a[:, m] - np.nanmean(a[:, m], 1, keepdims=True)
    return out


def tercile_spread(pred, y, idx):
    out = []
    for d in idx:
        m = ~np.isnan(pred[d]) & ~np.isnan(y[d])
        if m.sum() < 10:
            out.append(np.nan)
            continue
        q = pd.Series(pred[d][m]).rank(pct=True).values
        out.append(y[d][m][q > 2 / 3].mean() - y[d][m][q <= 1 / 3].mean())
    return np.array(out)


def ndcg_at(pred, y, idx, k=5):
    out = []
    for d in idx:
        m = ~np.isnan(pred[d]) & ~np.isnan(y[d])
        if m.sum() < 10:
            out.append(np.nan)
            continue
        rel = pd.Series(y[d][m]).rank(pct=True).values
        order = np.argsort(-pred[d][m])[:k]
        ideal = np.sort(rel)[::-1][:k]
        disc = 1 / np.log2(np.arange(2, k + 2))
        out.append((rel[order] * disc).sum() / (ideal * disc).sum())
    return np.array(out)
