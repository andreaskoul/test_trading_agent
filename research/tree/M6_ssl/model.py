"""Branch M6: self-supervised representations of return histories, used as frozen features.

Encoder input: the last 60 daily hedged returns D["e"] of a stock, each divided by that stock's trailing 252-session
volatility of e (computed at the window's last row; causal), clipped to +-5.
Pre-training uses windows whose LAST row is <= train_end only, and no labels:
  "mae"  masked reconstruction: 25% of steps hidden, a decoder rebuilds them from the d-dim embedding;
  "con"  contrastive (SimCLR/InfoNCE): two augmented views (jitter, scaling, random crop) of the same stock-window are
         positives; the other windows in the batch are negatives;
  "com"  co-movement (Stock2Vec idea): for a batch of stocks on one date, cosine similarity of their embeddings is
         regressed on the correlation of their windows over the trailing 120 sessions.
The encoder is then frozen; its embedding (cross-sectionally ranked per date) is a feature in a pooled ridge on the
per-date standardised 5-session target (Thursdays <= train_end), alone, with Z (5 characteristics) or with branch C's
32 features, against the same ridge without the embedding (control). "peer": average 5-session hedged return of each
stock's k nearest embedding neighbours on that date (cosine), as one extra feature.
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.set_num_threads(3)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
W = 60
_C = {}


# ---------------------------------------------------------------- inputs
def scaled_e(D):
    k = ("es", id(D["e"]))
    if k not in _C:
        e = pd.DataFrame(D["e"].astype(np.float64))
        vol = e.rolling(252, min_periods=120).std()
        es = (e / vol).clip(-5, 5).to_numpy()
        _C[k] = np.where(np.isfinite(es), es, 0.0).astype(np.float32), np.isfinite(vol.to_numpy())
    return _C[k]


def thu(D):
    S = D["S"]
    return np.where((S.weekday == 3) & (np.arange(len(S)) >= 300))[0]


def window_ok(D):
    """Row t, name i usable: eligible, vol defined, and at least 54 of the 60 window returns present."""
    k = ("wok", id(D["e"]))
    if k not in _C:
        es, vok = scaled_e(D)
        fin = pd.DataFrame(np.isfinite(D["e"]).astype(np.float32)).rolling(W, min_periods=W).sum().to_numpy()
        _C[k] = D["elig"] & vok & (np.nan_to_num(fin) >= 54)
    return _C[k]


def windows(es, t_idx, i_idx):
    """(B, 60) windows ending at rows t_idx for names i_idx."""
    off = np.arange(-W + 1, 1)
    return es[t_idx[:, None] + off[None, :], i_idx[:, None]]


# ---------------------------------------------------------------- encoder
class Enc(nn.Module):
    def __init__(self, d=16, ch=32):
        super().__init__()
        self.net = nn.Sequential(nn.Conv1d(2, ch, 5, padding=2), nn.GELU(),
                                 nn.Conv1d(ch, ch, 5, stride=2, padding=2), nn.GELU(),
                                 nn.Conv1d(ch, ch, 5, stride=2, padding=2), nn.GELU(),
                                 nn.AdaptiveAvgPool1d(4))
        self.out = nn.Linear(ch * 4, d)

    def forward(self, x, mask=None):            # x (B, L); mask (B, L) 1 = hidden
        m = torch.zeros_like(x) if mask is None else mask
        h = self.net(torch.stack([x * (1 - m), m], 1))
        return self.out(h.flatten(1))


def augment(x, g):
    B, L = x.shape
    x = x * (0.7 + 0.6 * torch.rand(B, 1, generator=g))
    x = x + 0.2 * torch.randn(B, L, generator=g)
    Lc = 45
    st = torch.randint(0, L - Lc + 1, (1,), generator=g).item()
    return x[:, st:st + Lc]


def pretrain(D, te, seed, kind, d=16, steps=800, bs=512, lr=2e-3, tau=0.2):
    es, _ = scaled_e(D)
    ok = window_ok(D)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    g = torch.Generator().manual_seed(seed)
    enc = Enc(d)
    dec = nn.Sequential(nn.Linear(d, 64), nn.GELU(), nn.Linear(64, W)) if kind == "mae" else None
    params = list(enc.parameters()) + (list(dec.parameters()) if dec is not None else [])
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    tt, ii = np.where(ok[: te + 1])
    keep = tt >= 300
    tt, ii = tt[keep], ii[keep]
    days = np.unique(tt)
    for s in range(steps):
        if kind == "com":
            t = int(rng.choice(days[days >= 120]))
            names = np.where(ok[t])[0]
            names = rng.choice(names, min(bs // 2, len(names)), replace=False)
            x = torch.from_numpy(windows(es, np.full(len(names), t), names))
            long_ = es[t - 119: t + 1, names].astype(np.float64)
            c = np.corrcoef(long_.T)
            c = torch.from_numpy(np.nan_to_num(c).astype(np.float32))
            z = F.normalize(enc(x), dim=1)
            sim = z @ z.T
            off = ~torch.eye(len(names), dtype=torch.bool)
            loss = ((sim - c)[off] ** 2).mean()
        else:
            j = rng.integers(0, len(tt), bs)
            x = torch.from_numpy(windows(es, tt[j], ii[j]))
            if kind == "mae":
                m = (torch.rand(x.shape, generator=g) < 0.25).float()
                rec = dec(enc(x, m))
                loss = (((rec - x) ** 2) * m).sum() / m.sum()
            else:
                z1 = F.normalize(enc(augment(x, g)), dim=1)
                z2 = F.normalize(enc(augment(x, g)), dim=1)
                lg = z1 @ z2.T / tau
                lab = torch.arange(bs)
                loss = (F.cross_entropy(lg, lab) + F.cross_entropy(lg.T, lab)) / 2
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
    enc.eval()
    return enc, float(loss)


def embed(D, enc, rows):
    """(len(rows), N, d) embeddings, NaN where the window is unusable."""
    es, _ = scaled_e(D)
    ok = window_ok(D)
    N = es.shape[1]
    out = None
    with torch.no_grad():
        for a in range(0, len(rows), 40):
            r = rows[a:a + 40]
            tt, ii = np.where(ok[r])
            if out is None:
                out = np.full((len(rows), N, enc.out.out_features), np.nan, np.float32)
            if len(tt) == 0:
                continue
            z = enc(torch.from_numpy(windows(es, r[tt], ii))).numpy()
            out[a + tt, ii] = z
    return out


# ---------------------------------------------------------------- features and ridge
def xrank(a):
    """Cross-sectional rank of each column of a (T, N, K) array per row, scaled to +-sqrt(3); NaN -> 0."""
    u = np.empty_like(a, dtype=np.float32)
    for k in range(a.shape[2]):
        df = pd.DataFrame(a[:, :, k])
        r = df.rank(axis=1)
        n = df.notna().sum(1).to_numpy()[:, None]
        u[:, :, k] = (((r.to_numpy() - 0.5) / np.maximum(n, 1)) - 0.5) * np.sqrt(12.0)
    return np.where(np.isfinite(u), u, 0.0)


def chars(D, which, rows):
    if which is None:
        return np.zeros((len(rows), D["e"].shape[1], 0), np.float32)
    k = ("ch", which, id(D["e"]))
    if k not in _C:
        if which == "Z":
            Z = np.where(D["elig"][:, :, None], D["Z"], np.nan)
            _C[k] = xrank(Z)
        else:  # branch C's 24 features + 8 market-state interactions (read-only import)
            from C_features import lib
            from C_features.model import FEATS, INTER
            _C[k] = lib.design(D, FEATS, "rank", INTER)[0]
    return _C[k][rows]


def peer_feature(Z, D, rows, k=10):
    """Average 5-session hedged return (rows t-4..t) of each name's k nearest embedding neighbours (cosine)."""
    e = pd.DataFrame(D["e"].astype(np.float64)).rolling(5, min_periods=5).sum().to_numpy()
    out = np.full((len(rows), Z.shape[1]), np.nan)
    for a, t in enumerate(rows):
        m = np.isfinite(Z[a]).all(1) & np.isfinite(e[t])
        idx = np.where(m)[0]
        if len(idx) < 50:
            continue
        z = Z[a][idx]
        z = z - z.mean(0)
        z = z / (np.linalg.norm(z, axis=1, keepdims=True) + 1e-9)
        s = z @ z.T
        np.fill_diagonal(s, -np.inf)
        nb = np.argpartition(-s, k, axis=1)[:, :k]
        out[a, idx] = e[t][idx][nb].mean(1)
    return out


def target(D, rows):
    y = np.where(D["elig"][rows], D["y5"][rows], np.nan).astype(np.float64)
    y = y - np.nanmean(y, 1, keepdims=True)
    return np.clip(y / (np.nanstd(y, 1, keepdims=True) + 1e-12), -3, 3)


def ridge(X, y, lam):
    m = np.isfinite(y)
    Xm, ym = X[m].astype(np.float64), y[m]
    K = Xm.shape[1]
    A = Xm.T @ Xm / len(ym)
    return np.linalg.solve(A + lam * np.trace(A) / K * np.eye(K), Xm.T @ ym / len(ym))


def mlp_fit(X, y, Xp, seed, hidden=32, epochs=4):
    torch.manual_seed(seed)
    m = np.isfinite(y)
    Xt, yt = torch.from_numpy(X[m].astype(np.float32)), torch.from_numpy(y[m].astype(np.float32))
    net = nn.Sequential(nn.Linear(X.shape[1], hidden), nn.GELU(), nn.Dropout(0.1), nn.Linear(hidden, 1))
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-3)
    g = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        perm = torch.randperm(len(yt), generator=g)
        for a in range(0, len(yt), 4096):
            b = perm[a:a + 4096]
            loss = ((net(Xt[b]).squeeze(1) - yt[b]) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    net.eval()
    with torch.no_grad():
        return net(torch.from_numpy(Xp.astype(np.float32))).squeeze(-1).numpy()


def get_emb(D, te, seed, kind, d, steps):
    """Embeddings for every usable Thursday (cached per process), from an encoder pre-trained on rows <= te."""
    k = ("emb", kind, d, steps, te, seed, id(D["e"]))
    if k not in _C:
        for kk in [x for x in _C if x[0] == "emb" and x[1:4] != (kind, d, steps)]:
            del _C[kk]
        f = os.path.join(HERE, "emb_cache", "%s_d%d_s%d_te%d_seed%d.npy" % (kind, d, steps, te, seed))
        if os.path.exists(f):
            _C[k] = np.load(f).astype(np.float32)
        else:
            enc, last = pretrain(D, te, seed, kind, d=d, steps=steps)
            _C[k] = embed(D, enc, thu(D))
            os.makedirs(os.path.dirname(f), exist_ok=True)
            np.save(f, _C[k].astype(np.float16))
    return _C[k]


def make(kind=None, d=16, steps=800, use_emb=True, base="Z", peer=False, k_peer=10, head="ridge", lam=0.1):
    """kind=None: control (no encoder). base: None | "Z" | "C"."""

    def fit_predict(D, te, rows, seed):
        T = thu(D)
        tr = T[T <= te]
        allr = np.concatenate([tr, rows])
        ok = window_ok(D)[allr]
        parts = [chars(D, base, allr)]
        if kind is not None:
            E = get_emb(D, te, seed, kind, d, steps)
            pos = {t: a for a, t in enumerate(T)}
            Ea = E[[pos[t] for t in allr]]
            if use_emb:
                parts.append(xrank(Ea))
            if peer:
                parts.append(xrank(peer_feature(Ea, D, allr, k_peer)[:, :, None]))
        X = np.concatenate(parts, 2)
        n = len(tr)
        y = target(D, tr)
        y = np.where(ok[:n], y, np.nan)
        Xtr = X[:n].reshape(-1, X.shape[2])
        Xp = X[n:].reshape(-1, X.shape[2])
        if head == "ridge":
            p = Xp @ ridge(Xtr, y.reshape(-1), lam)
        else:
            p = mlp_fit(Xtr, y.reshape(-1), Xp, seed)
        p = p.reshape(len(rows), -1)
        return np.where(ok[n:], p, np.nan)

    return fit_predict


BEST = dict(kind="mae", d=16, base="Z")   # placeholder; updated after scoring
