"""Neural exposure rules, walk-forward on the US century (research/sharpe/PREREG.md, Amendment 2). Research only.

    python research/sharpe/nn.py smoke     # one fit on 1927-1949, validation numbers only (no out-of-sample day)
    python research/sharpe/nn.py read      # ONCE (READ_NN.lock)
"""
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

import core as C

HERE = os.path.dirname(os.path.abspath(__file__))
SPREAD, COST, SEEDS, STEPS, CHECK, PATIENCE = 0.01, 2e-4, range(5), 500, 10, 5
torch.set_num_threads(8)


def inputs(df):
    r = df.mkt
    idx = (1 + r).cumprod()
    s21, s63, s252 = (r.rolling(n).std() for n in (21, 63, 252))
    F = {}
    for L in (1, 5, 21, 63, 126, 252):
        F[f"r{L}"] = (idx / idx.shift(L) - 1) / (s63 * L ** .5)
    for n in (50, 200):
        F[f"ma{n}"] = (idx / idx.rolling(n).mean() - 1) / (s63 * n ** .5)
    F["lv"] = np.log(s21 * 252 ** .5)
    F["vr"] = np.log(s21 / s252)
    F["dd"] = idx / idx.rolling(252).max() - 1
    X = pd.DataFrame(F).clip(-10, 10)
    z = (r / s63.shift(1)).clip(-5, 5)
    Z = pd.concat([z.shift(k) for k in range(125, -1, -1)], axis=1)                  # the last 126 scaled returns, oldest first
    ok = X.notna().all(1) & Z.notna().all(1)
    # row t holds what is known at the close of t; it sets the weight for day t+1
    nxt_ex = (r - df.rf).shift(-1)
    ok &= nxt_ex.notna()
    return X[ok], Z[ok], nxt_ex[ok]


class MLP(nn.Module):
    def __init__(s, n):
        super().__init__()
        s.f = nn.Sequential(nn.Linear(n, 16), nn.Tanh(), nn.Linear(16, 16), nn.Tanh(), nn.Linear(16, 1))

    def forward(s, x):
        return s.f(x).squeeze(-1)


class CNN(nn.Module):
    def __init__(s):
        super().__init__()
        s.c = nn.Sequential(nn.Conv1d(1, 8, 5), nn.ReLU(), nn.Conv1d(8, 8, 5, stride=2), nn.ReLU(), nn.AdaptiveAvgPool1d(4), nn.Flatten())
        s.f = nn.Sequential(nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(s, x):
        return s.f(s.c(x.unsqueeze(1))).squeeze(-1)


def net_excess(w, ex):
    dw = torch.cat([torch.zeros(1), (w[1:] - w[:-1]).abs()])
    return w * ex - SPREAD * torch.clamp(w - 1, min=0) / 252 - COST * dw


def sharpe_t(x):
    return x.mean() / (x.std() + 1e-12) * 252 ** .5


def fit(kind, Xtr, ytr, band, seed):
    lo, hi = band
    torch.manual_seed(seed)
    n = len(Xtr)
    cut = int(n * 0.8)
    m = MLP(Xtr.shape[1]) if kind == "MLP" else CNN()
    opt = torch.optim.Adam(m.parameters(), lr=1e-3, weight_decay=1e-4)
    best, state, bad = -1e9, None, 0
    for step in range(1, STEPS + 1):
        m.train()
        opt.zero_grad()
        w = lo + (hi - lo) * torch.sigmoid(m(Xtr[:cut]))
        loss = -sharpe_t(net_excess(w, ytr[:cut]))
        loss.backward()
        opt.step()
        if step % CHECK == 0:
            m.eval()
            with torch.no_grad():
                v = float(sharpe_t(net_excess(lo + (hi - lo) * torch.sigmoid(m(Xtr[cut:])), ytr[cut:])))
            if v > best:
                best, state, bad = v, {k: t.clone() for k, t in m.state_dict().items()}, 0
            else:
                bad += 1
                if bad >= PATIENCE:
                    break
    m.load_state_dict(state)
    m.eval()
    return m, best


def walk(kind, X, Z, y, band, first=1950, last=2026, smoke=False):
    lo, hi = band
    A = torch.tensor((X if kind == "MLP" else Z).to_numpy(), dtype=torch.float32)
    yt = torch.tensor(y.to_numpy(), dtype=torch.float32)
    yrs = X.index.year.to_numpy()
    w = pd.Series(np.nan, index=X.index)
    val = []
    for y0 in range(first, last + 1, 5):
        tr = np.where(yrs < y0)[0]
        te = np.where((yrs >= y0) & (yrs < y0 + 5))[0]
        ws = []
        for seed in SEEDS:
            m, v = fit(kind, A[tr], yt[tr], band, seed)
            val.append(v)
            if smoke:
                continue
            with torch.no_grad():
                ws.append((lo + (hi - lo) * torch.sigmoid(m(A[te]))).numpy())
        if smoke:
            return None, val
        w.iloc[te] = np.mean(ws, 0)
        print(kind, band, y0, f"val Sharpe {np.mean(val[-5:]):.2f}", flush=True)
    return w, val


def main():
    mode = sys.argv[1]
    df = C.us()
    X, Z, y = inputs(df)
    if mode == "smoke":
        for kind in ("MLP", "CNN"):
            _, val = walk(kind, X, Z, y, C.BANDS["policy"], smoke=True)
            print(kind, "validation Sharpe of the five seeds on the 1927-1949 fit:", [round(v, 2) for v in val])
        return
    lock = os.path.join(HERE, "READ_NN.lock")
    if os.path.exists(lock):
        sys.exit("the read was already made: " + open(lock).read())
    open(lock, "w").write(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    res = {"run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bands": {}}
    for b, band in C.BANDS.items():
        R0, W0, rf = C.strategies(df, band)
        Wn = {}
        for kind in ("MLP", "CNN"):
            w, _ = walk(kind, X, Z, y, band)
            Wn[kind] = w.shift(1)                                    # row t's weight applies to day t+1
        idx = Wn["MLP"].dropna().index.intersection(R0.index)
        idx = idx[idx >= "1950-01-03"]
        R = {k: R0.loc[idx, k] for k in ("T200", "TSM", "BH")}
        W = {k: W0.loc[idx, k] for k in ("T200", "TSM", "BH")}
        for kind in ("MLP", "CNN"):
            W[kind] = Wn[kind].loc[idx]
            R[kind] = C.pret(df.mkt.loc[idx], df.rf.loc[idx], W[kind], 2e-4)
        rfi = rf.loc[idx]
        out = {"stats": {k: C.stats(R[k], rfi, W[k]) for k in R}}
        ex = {k: (R[k] - rfi).to_numpy() for k in R}
        out["by_period"] = {p: {k: float(C.sh((R[k] - rfi).loc[a:z].to_numpy())) for k in R} for p, (a, z) in {"1950-1999": ("1950", "1999"), "2000-2026": ("2000", "2026")}.items()}
        out["cost10bp_sharpe"] = {k: float(C.sh((C.pret(df.mkt.loc[idx], df.rf.loc[idx], W[k], 1e-3) - rfi).to_numpy())) for k in W}
        pairs = {"H5": ("MLP", "T200"), "H6": ("CNN", "T200"), "MLP_vs_BH": ("MLP", "BH"), "CNN_vs_BH": ("CNN", "BH"), "T200_vs_BH": ("T200", "BH")}
        rng = np.random.default_rng(C.SEED)
        d = {h: np.empty(C.DRAWS) for h in pairs}
        for i in range(C.DRAWS):
            ix = C.boot_idx(len(idx), rng)
            for h, (a, c) in pairs.items():
                d[h][i] = C.sh(ex[a][ix]) - C.sh(ex[c][ix])
        out["tests"] = {h: {"sharpe_diff": float(C.sh(ex[a]) - C.sh(ex[c])), "p_one_sided": float((d[h] <= 0).mean())} for h, (a, c) in pairs.items()}
        hm = C.holm({h: out["tests"][h]["p_one_sided"] for h in ("H5", "H6")}, alpha=0.01)
        for h in ("H5", "H6"):
            out["tests"][h]["holm_pass_alpha_0.01"] = hm[h]
        out["corr_of_weights_with_T200"] = {k: float(np.corrcoef(W[k], W["T200"])[0, 1]) for k in ("MLP", "CNN")}
        res["bands"][b] = out
    json.dump(res, open(os.path.join(HERE, "RESULT_NN.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
