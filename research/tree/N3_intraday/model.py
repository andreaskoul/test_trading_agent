"""N3 intraday candidates on top of the frozen MASTER 5-day scores. fit_predict(D, train_end, pred_rows, seed).
Features: features.py (row t uses sessions <= t). Missing intraday data -> neutral rank 0, so the universe is MASTER's.
Selected features (rule fixed in screen.py, chosen on 2016 only): id21 (sign -), on21_minus_id21 (sign +)."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import harness as h
import features as fe

_C = {}


def _feats(D):
    if "F" not in _C:
        F = fe.build(D)
        _C["F"] = {k: np.nan_to_num(fe.rank_rows(v), nan=0.0) for k, v in F.items()}
        _C["Mr"] = fe.rank_rows(D["master_h5_ref"].astype(np.float64))
    return _C["F"], _C["Mr"]


def rank_avg(feats_w, w_master):
    def fp(D, te, rows, seed):
        F, Mr = _feats(D)
        s = w_master * Mr[rows]
        for k, w in feats_w.items():
            s = s + w * F[k][rows]
        return s
    return fp


def _train_rows(D, te):
    S = D["S"]
    return np.where((S.weekday == 3) & (S.year >= 2016) & (np.arange(len(S)) <= te))[0]


def _X(F, Mr, t, keys):
    return np.column_stack([Mr[t]] + [F[k][t] for k in keys])


def linear(keys, kind="ridge", lam=1.0):
    """y5 cross-sectional rank on [MASTER rank, feature ranks]; pooled ridge or Fama-MacBeth mean of weekly OLS."""
    def fp(D, te, rows, seed):
        F, Mr = _feats(D)
        bs, Xs, ys = [], [], []
        for t in _train_rows(D, te):
            m = np.isfinite(Mr[t]) & np.isfinite(D["y5"][t]) & D["elig"][t]
            if m.sum() < 50: continue
            X = _X(F, Mr, t, keys)[m]; y = pd.Series(D["y5"][t][m]).rank(pct=True).to_numpy() - .5
            if kind == "fm":
                bs.append(np.linalg.lstsq(X, y, rcond=None)[0])
            else:
                Xs.append(X); ys.append(y)
        if kind == "fm":
            b = np.mean(bs, 0)
        else:
            X, y = np.vstack(Xs), np.concatenate(ys)
            b = np.linalg.solve(X.T @ X + lam * len(y) / 1000 * np.eye(X.shape[1]), X.T @ y)
        _C.setdefault("coefs", []).append((int(te), kind, b.round(4).tolist()))
        out = np.full((len(rows), Mr.shape[1]), np.nan)
        for i, t in enumerate(rows):
            out[i] = _X(F, Mr, t, keys) @ b
        return out
    return fp


# Highest increment_t of the candidates (N3_c2a, t 1.53 on 2017-2019), kept for the record. NOT a finding about
# intraday structure: the control N3_c8 (same weights, plain 21-session close-to-close return) gives t 1.72, and the
# double-ML slope of id21 after partialling out MASTER + Z is -0.020 (t -1.22). Not recommended as a finalist.
fit_predict = rank_avg({"id21": -0.2}, 0.8)


def anchored_fm(keys):
    """MASTER coefficient fixed at its mean weekly IC over 2013..train_end (rank-on-rank slope = IC; training rows
    only); feature coefficients = Fama-MacBeth mean of weekly OLS of the residual y rank on the feature ranks, 2016 on."""
    def fp(D, te, rows, seed):
        F, Mr = _feats(D)
        S = D["S"]
        hist = np.where((S.weekday == 3) & (S.year >= 2013) & (np.arange(len(S)) <= te))[0]
        a = float(np.nanmean(h.weekly_ic(D["master_h5_ref"].astype(np.float64), D, hist)))
        bs = []
        for t in _train_rows(D, te):
            m = np.isfinite(Mr[t]) & np.isfinite(D["y5"][t]) & D["elig"][t]
            if m.sum() < 50: continue
            y = pd.Series(D["y5"][t][m]).rank(pct=True).to_numpy() - .5 - a * Mr[t][m]
            X = np.column_stack([F[k][t][m] for k in keys])
            bs.append(np.linalg.lstsq(X, y, rcond=None)[0])
        b = np.mean(bs, 0)
        _C.setdefault("coefs", []).append((int(te), "anchored", round(a, 4), b.round(4).tolist()))
        return a * Mr[rows] + np.stack([F[k][rows] for k in keys], -1) @ b
    return fp
