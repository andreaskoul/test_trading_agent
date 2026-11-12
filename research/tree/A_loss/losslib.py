"""Branch A, loss mathematics: one fixed small MLP, many objectives.

Model (fixed): MLP n_feat -> 32 -> 16 -> out, on the five characteristics D["Z"] plus four return features computed
from D["e"] (1-, 5-, 21-session hedged return, 21-session volatility), each z-scored across eligible names per date.
Training rows: every session <= train_end with a finite target. A batch is a set of dates; every loss is computed
per date over the masked names and averaged over the dates.
"""
import os
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
torch.set_num_threads(2)

_CACHE = {}


def _xs_z(a, m):
    """z-score each row of a over the names where m is true; elsewhere NaN. Winsorised at +-4."""
    a = np.where(m, a, np.nan)
    with np.errstate(all="ignore"):
        mu, sd = np.nanmean(a, 1, keepdims=True), np.nanstd(a, 1, keepdims=True)
    return np.clip((a - mu) / np.where(sd > 0, sd, np.nan), -4, 4)


def features(D, use_ret=True):
    """(T, N, F) float32 with NaN where unavailable. Row t uses data up to and including row t only."""
    key = (id(D["e"]), use_ret)
    if key in _CACHE:
        return _CACHE[key]
    Z = D["Z"].astype(np.float32)
    if not use_ret:
        X = Z
    else:
        e = D["e"].astype(np.float64)
        ok = np.isfinite(e)
        e0 = np.where(ok, e, 0.0)
        c1 = np.cumsum(e0, 0)
        c2 = np.cumsum(e0 * e0, 0)
        cn = np.cumsum(ok, 0)

        def roll(c, k):
            out = c.copy()
            out[k:] = c[k:] - c[:-k]
            return out
        m = D["elig"] & ok
        f = []
        f.append(_xs_z(e, m))
        for k in (5, 21):
            full = roll(cn, k) >= k * 0.8
            f.append(_xs_z(roll(c1, k), m & full))
        n21 = np.maximum(roll(cn, 21), 1)
        var = roll(c2, 21) / n21 - (roll(c1, 21) / n21) ** 2
        f.append(_xs_z(np.log(np.sqrt(np.maximum(var, 1e-12))), m & (roll(cn, 21) >= 17)))
        R = np.stack(f, 2)
        R = np.where(np.isfinite(R), R, 0.0)            # a missing return feature is neutral
        X = np.concatenate([Z, R.astype(np.float32)], 2)
        X[~np.isfinite(Z).all(2)] = np.nan
    _CACHE[key] = X
    return X


class MLP(nn.Module):
    def __init__(self, n_in, n_out=1, hidden=(32, 16), drop=0.1):
        super().__init__()
        layers, d = [], n_in
        for h in hidden:
            layers += [nn.Linear(d, h), nn.ReLU(), nn.Dropout(drop)]
            d = h
        layers.append(nn.Linear(d, n_out))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------- losses
# s: (B, N) scores (or (B, N, 3) logits for "cls"); y: dict of targets (B, N); m: (B, N) bool mask.

def _mmean(a, m):
    return (a * m).sum(1) / m.sum(1).clamp(min=1)


def _corr(s, y, m):
    mf = m.float()
    s = s - _mmean(s, mf).unsqueeze(1)
    y = y - _mmean(y, mf).unsqueeze(1)
    s, y = s * mf, y * mf
    return (s * y).sum(1) / (s.pow(2).sum(1).sqrt() * y.pow(2).sum(1).sqrt() + 1e-8)


def loss_fn(name, s, T, m, kw):
    mf = m.float()
    if name == "mse_raw":
        return _mmean((s - T["raw"]) ** 2, mf).mean()
    if name == "mse_z":
        return _mmean((s - T["z"]) ** 2, mf).mean()
    if name == "mse_rank":
        return _mmean((s - T["rank"]) ** 2, mf).mean()
    if name == "mse_gauss":
        return _mmean((s - T["gauss"]) ** 2, mf).mean()
    if name == "huber":
        return _mmean(F.huber_loss(s, T["z"], delta=kw.get("delta", 1.0), reduction="none"), mf).mean()
    if name == "ic":
        return -_corr(s, T[kw.get("target", "gauss")], m).mean()
    if name == "ic_sharpe":                                  # mean / std of the per-date IC across the batch
        c = _corr(s, T[kw.get("target", "gauss")], m)
        return -c.mean() / (c.std() + 1e-4)
    if name == "listmle":
        # Plackett-Luce likelihood of the realised ordering, top-weighted on both ends (applied to s and to -s)
        tot = 0.0
        for sign in (1.0, -1.0):
            yy = torch.where(m, sign * T["rank"], torch.full_like(s, -1e9))
            order = yy.argsort(1, descending=True)
            ss = torch.gather(sign * s, 1, order)
            mm = torch.gather(m, 1, order)
            ss = ss.masked_fill(~mm, -1e9)
            lcs = torch.logcumsumexp(ss.flip(1), 1).flip(1)
            tot = tot + _mmean(lcs - ss, mm.float()).mean()
        return tot / 2
    if name == "softmax_ce":
        # cross-entropy between softmax(target / tau) and softmax(score), for the top and (mirrored) for the bottom
        tau = kw.get("tau", 0.5)
        tot = 0.0
        for sign in (1.0, -1.0):
            p = torch.softmax((sign * T["gauss"] / tau).masked_fill(~m, -1e9), 1)
            ls = torch.log_softmax((sign * s).masked_fill(~m, -1e9), 1)
            tot = tot - (p * ls * mf).sum(1).mean()
        return tot / 2
    if name == "pairwise":
        k = kw.get("k", 128)                                # k random columns per batch; all pairs among them
        idx = torch.randperm(s.shape[1])[:k]
        ss, yy, mm = s[:, idx], T["rank"][:, idx], m[:, idx]
        ds = ss.unsqueeze(2) - ss.unsqueeze(1)
        dy = yy.unsqueeze(2) - yy.unsqueeze(1)
        pm = (mm.unsqueeze(2) & mm.unsqueeze(1) & (dy.abs() > kw.get("gap", 0.0))).float()
        l = F.softplus(-ds * torch.sign(dy))
        return (l * pm).sum() / pm.sum().clamp(min=1)
    if name == "cls":
        # three classes: bottom quintile, middle, top quintile
        r = T["rank"]
        c = torch.ones_like(r, dtype=torch.long)
        c[r > 0.3] = 2
        c[r < -0.3] = 0
        l = F.cross_entropy(s.reshape(-1, 3), c.reshape(-1), reduction="none").reshape(r.shape)
        return _mmean(l, mf).mean()
    if name in ("spread", "spread_sharpe"):
        # soft long-short book: weights softmax(s/tau) - softmax(-s/tau) on standardised scores; pay-off on z targets
        tau = kw.get("tau", 0.5)
        mu = _mmean(s, mf).unsqueeze(1)
        sd = (_mmean((s - mu) ** 2, mf).unsqueeze(1) + 1e-8).sqrt()
        u = ((s - mu) / sd / tau).masked_fill(~m, -1e9)
        un = (-(s - mu) / sd / tau).masked_fill(~m, -1e9)
        w = torch.softmax(u, 1) - torch.softmax(un, 1)
        pnl = (w * T[kw.get("target", "z")] * mf).sum(1)
        if name == "spread":
            return -pnl.mean()
        return -pnl.mean() / (pnl.std() + 1e-4)
    raise ValueError(name)


def _targets(y, m):
    """Per-date transforms of the target over masked names: raw (global scale), z, rank in [-.5,.5], gaussianised."""
    yy = np.where(m, y, np.nan).astype(np.float64)
    n = m.sum(1, keepdims=True).clip(1)
    order = np.argsort(np.argsort(np.where(m, yy, np.inf), 1), 1).astype(np.float64)   # 0..n-1 among masked
    u = (order + 0.5) / n
    rank = np.where(m, u - 0.5, 0.0)
    gauss = np.where(m, np.sqrt(2) * torch.erfinv(torch.tensor(2 * np.clip(u, 1e-4, 1 - 1e-4) - 1)).numpy(), 0.0)
    with np.errstate(all="ignore"):
        mu, sd = np.nanmean(yy, 1, keepdims=True), np.nanstd(yy, 1, keepdims=True)
    z = np.where(m, np.clip((yy - mu) / np.where(sd > 0, sd, 1.0), -5, 5), 0.0)
    raw = np.where(m, yy / np.nanstd(yy), 0.0)
    return {k: torch.tensor(v, dtype=torch.float32) for k, v in dict(raw=raw, z=z, rank=rank, gauss=gauss).items()}


def make(loss, use_ret=True, epochs=8, batch=64, lr=1e-3, wd=1e-4, hidden=(32, 16), drop=0.1, stride=1, **kw):
    """Return a harness-compatible fit_predict for one objective. `loss` may be a list: scores are rank-averaged."""
    losses = [loss] if isinstance(loss, str) else list(loss)

    def fit_one(D, X, te, rows, seed, lname):
        torch.manual_seed(seed)
        np.random.seed(seed)
        tr = np.arange(21, te + 1, stride)
        y = D["y5"][tr]
        m = np.isfinite(y) & D["elig"][tr] & np.isfinite(X[tr]).all(2)
        keep = m.sum(1) >= 50
        tr, y, m = tr[keep], y[keep], m[keep]
        T = _targets(y, m)
        Xt = torch.tensor(np.where(np.isfinite(X[tr]), X[tr], 0.0), dtype=torch.float32)
        mt = torch.tensor(m)
        net = MLP(X.shape[2], 3 if lname == "cls" else 1, hidden, drop)
        opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=wd)
        g = torch.Generator().manual_seed(seed)
        net.train()
        for _ in range(epochs):
            perm = torch.randperm(len(tr), generator=g)
            for i in range(0, len(perm) - batch // 2, batch):
                b = perm[i:i + batch]
                out = net(Xt[b])
                s = out if lname == "cls" else out.squeeze(-1)
                l = loss_fn(lname, s, {k: v[b] for k, v in T.items()}, mt[b], kw)
                opt.zero_grad()
                l.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
        net.eval()
        Xp = X[rows]
        ok = np.isfinite(Xp).all(2)
        with torch.no_grad():
            out = net(torch.tensor(np.where(np.isfinite(Xp), Xp, 0.0), dtype=torch.float32))
            if lname == "cls":
                p = torch.softmax(out, -1)
                out = p[..., 2] - p[..., 0]
            else:
                out = out.squeeze(-1)
        return np.where(ok, out.numpy().astype(np.float64), np.nan)

    def fit_predict(D, te, rows, seed):
        import pandas as pd
        X = features(D, use_ret)
        ps = [fit_one(D, X, te, rows, seed, ln) for ln in losses]
        if len(ps) == 1:
            return ps[0]
        return np.mean([pd.DataFrame(p).rank(axis=1, pct=True).to_numpy() for p in ps], 0)

    return fit_predict
