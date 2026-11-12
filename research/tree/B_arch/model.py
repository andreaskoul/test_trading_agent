"""Branch B (network architecture): the single best configuration, self-contained.

    from model import fit_predict        # fit_predict(D, train_end, pred_rows, seed) -> (len(pred_rows), n_names)

CONFIG below is the chosen configuration; the rest of the file is the branch's network code (arch.py), copied so
that this file imports only numpy, torch and (for scoring) harness.
"""
CONFIG = dict(xattn=True)     # mlp_Z_xattn: five characteristics -> linear 16 -> self-attention over the date's names -> MLP

import numpy as np
import torch
import torch.nn as nn

torch.set_num_threads(2)

DEFAULT = dict(
    chars=True,        # use Z
    temporal=None,     # None | "gru" | "cnn" | "tfm"
    L=40,              # sessions of history for the temporal encoder
    d=16,              # width
    depth=2,           # hidden layers of the head MLP
    gate=False,        # market-state gate on the fused features (MASTER style)
    xattn=False,       # self-attention over the names of one date
    heads=2,
    norm=True,         # LayerNorm in the head / pre-norm in attention
    residual=False,    # residual head blocks
    dropout=0.1,
    epochs=6, lr=1e-3, wd=1e-4, batch_dates=4,
)

_CACHE = {}


def _prep(D):
    key = id(D["e"])
    if key in _CACHE:
        return _CACHE[key]
    e = D["e"].astype(np.float32)
    with np.errstate(all="ignore"):
        sd = np.nanstd(e, axis=1, keepdims=True)
    sd[~np.isfinite(sd) | (sd <= 0)] = np.nan
    es = np.clip(np.nan_to_num(e / sd, nan=0.0, posinf=0.0, neginf=0.0), -5, 5).astype(np.float32)
    rm = np.nan_to_num(D["rm"].astype(np.float64))
    disp = np.nan_to_num(sd[:, 0].astype(np.float64), nan=0.0)
    T = len(rm)
    M = np.zeros((T, 6), dtype=np.float64)
    c = np.concatenate([[0.0], np.cumsum(rm)])
    c2 = np.concatenate([[0.0], np.cumsum(rm * rm)])
    cd = np.concatenate([[0.0], np.cumsum(disp)])
    for t in range(T):
        a5, a20, a60 = max(0, t - 4), max(0, t - 19), max(0, t - 59)
        M[t, 0] = c[t + 1] - c[a5]
        M[t, 1] = c[t + 1] - c[a20]
        M[t, 2] = np.sqrt(max((c2[t + 1] - c2[a20]) / (t + 1 - a20), 0))
        M[t, 3] = np.sqrt(max((c2[t + 1] - c2[a60]) / (t + 1 - a60), 0))
        M[t, 4] = disp[t]
        M[t, 5] = (cd[t + 1] - cd[a20]) / (t + 1 - a20)
    _CACHE.clear()
    _CACHE[key] = (es, M)
    return es, M


class Temporal(nn.Module):
    def __init__(self, kind, L, d):
        super().__init__()
        self.kind = kind
        if kind == "gru":
            self.rnn = nn.GRU(1, d, batch_first=True)
        elif kind == "cnn":
            self.c1 = nn.Conv1d(1, d, 5, stride=2, padding=2)
            self.c2 = nn.Conv1d(d, d, 5, stride=2, padding=2)
            self.out = nn.Linear(2 * d, d)
        elif kind == "tfm":
            self.p = 5
            self.emb = nn.Linear(self.p, d)
            self.pos = nn.Parameter(torch.zeros(1, L // self.p, d))
            self.enc = nn.TransformerEncoderLayer(d, 2, 2 * d, dropout=0.1, batch_first=True, norm_first=True)
        else:
            raise ValueError(kind)

    def forward(self, x):                       # (n, L)
        if self.kind == "gru":
            return self.rnn(x.unsqueeze(-1))[1][0]
        if self.kind == "cnn":
            h = torch.relu(self.c2(torch.relu(self.c1(x.unsqueeze(1)))))
            return self.out(torch.cat([h.mean(-1), h.amax(-1)], -1))
        h = self.emb(x.reshape(x.shape[0], -1, self.p)) + self.pos
        return self.enc(h).mean(1)


class Net(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.c, d = c, c["d"]
        self.zin = nn.Linear(5, d) if c["chars"] else None
        self.temp = Temporal(c["temporal"], c["L"], d) if c["temporal"] else None
        if c["gate"]:
            self.gate = nn.Linear(6, d)
        if c["xattn"]:
            self.an = nn.LayerNorm(d) if c["norm"] else nn.Identity()
            self.attn = nn.MultiheadAttention(d, c["heads"], dropout=c["dropout"], batch_first=True)
            self.fn = nn.LayerNorm(d) if c["norm"] else nn.Identity()
            self.ff = nn.Sequential(nn.Linear(d, 2 * d), nn.GELU(), nn.Linear(2 * d, d))
        self.blocks = nn.ModuleList([nn.Sequential(nn.LayerNorm(d) if c["norm"] else nn.Identity(), nn.Linear(d, d), nn.GELU(),
                                                   nn.Dropout(c["dropout"])) for _ in range(c["depth"])])
        self.out = nn.Linear(d, 1)

    def forward(self, Z, E, M, mask):           # Z (B,N,5)  E (B,N,L)  M (B,6)  mask (B,N) True = real name
        B, N = mask.shape
        h = 0
        if self.zin is not None:
            h = h + self.zin(Z)
        if self.temp is not None:
            ht = torch.zeros(B, N, self.c["d"])
            ht[mask] = self.temp(E[mask])
            h = h + ht
        if self.c["gate"]:
            h = h * (torch.softmax(self.gate(M), -1) * self.c["d"]).unsqueeze(1)
        if self.c["xattn"]:
            q = self.an(h)
            h = h + self.attn(q, q, q, key_padding_mask=~mask, need_weights=False)[0]
            h = h + self.ff(self.fn(h))
        for b in self.blocks:
            h = h + b(h) if self.c["residual"] else b(h)
        return self.out(h).squeeze(-1)


def _tensors(D, es, Mz, rows, c, with_y):
    Z, elig, L = D["Z"], D["elig"], c["L"]
    ok = elig[rows] & np.isfinite(Z[rows]).all(-1)
    if with_y:
        ok &= np.isfinite(D["y5"][rows])
        keep = ok.sum(1) >= 50
        rows, ok = rows[keep], ok[keep]
    N = int(ok.sum(1).max()) if len(rows) else 1
    T = len(rows)
    Zt = np.zeros((T, N, 5), np.float32)
    Et = np.zeros((T, N, L), np.float32)
    Yt = np.zeros((T, N), np.float32)
    mk = np.zeros((T, N), bool)
    idx = np.zeros((T, N), np.int64)
    for i, t in enumerate(rows):
        j = np.where(ok[i])[0]
        n = len(j)
        if n == 0:
            continue
        Zt[i, :n] = np.clip(Z[t, j], -5, 5)
        if c["temporal"]:
            w = es[max(0, t - L + 1):t + 1, j].T
            Et[i, :n, L - w.shape[1]:] = w
        if with_y:
            y = D["y5"][t, j].astype(np.float64)
            Yt[i, :n] = np.clip((y - y.mean()) / (y.std() + 1e-12), -3, 3)
        mk[i, :n] = True
        idx[i, :n] = j
    f = torch.from_numpy
    return f(Zt), f(Et), f(Mz[rows].astype(np.float32)), f(mk), f(Yt), idx


def make(**over):
    c = dict(DEFAULT, **over)

    def fit_predict(D, train_end, pred_rows, seed):
        torch.set_num_threads(2)
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        es, M = _prep(D)
        mu, sg = M[60:train_end + 1].mean(0), M[60:train_end + 1].std(0) + 1e-12
        Mz = np.clip((M - mu) / sg, -4, 4)
        S = D["S"]
        tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= train_end) & (np.arange(len(S)) >= 60))[0]
        Zt, Et, Mt, mk, Yt, _ = _tensors(D, es, Mz, tr, c, True)
        net = Net(c)
        opt = torch.optim.AdamW(net.parameters(), lr=c["lr"], weight_decay=c["wd"])
        T, bd = len(Zt), c["batch_dates"]
        steps = c["epochs"] * int(np.ceil(T / bd))
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=c["lr"], total_steps=steps, pct_start=0.2)
        net.train()
        for _ in range(c["epochs"]):
            perm = rng.permutation(T)
            for s in range(0, T, bd):
                b = torch.from_numpy(perm[s:s + bd])
                out = net(Zt[b], Et[b], Mt[b], mk[b])
                loss = ((out - Yt[b]) ** 2)[mk[b]].mean()        # the fixed loss
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
                sched.step()
        net.eval()
        rows = np.asarray(pred_rows)
        Zp, Ep, Mp, mp, _, idx = _tensors(D, es, Mz, rows, c, False)
        pred = np.full((len(rows), D["y5"].shape[1]), np.nan)
        with torch.no_grad():
            for s in range(0, len(rows), 8):
                o = net(Zp[s:s + 8], Ep[s:s + 8], Mp[s:s + 8], mp[s:s + 8]).numpy()
                for i in range(o.shape[0]):
                    m = mp[s + i].numpy()
                    pred[s + i, idx[s + i][m]] = o[i][m]
        return pred

    fit_predict.config = c
    return fit_predict


fit_predict = make(**CONFIG)
