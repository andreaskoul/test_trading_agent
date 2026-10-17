"""Quant trials · models. Every model maps a fold to predictions on the test decisions:

    fit_predict(X, y, train, test, ...) -> pred (D, N), NaN outside `test`

X is (D, N, F) features already standardised on the fold's training rows; y is (D, N) standardised target.
Sequence models read the L-session history of X for each (d, name).

Paper hyper-parameters (2605.30652, repo model_keep/a_sen_embed_transformer_v7_3): d_model 32, 4 heads,
4 pre-LN layers, ff 128, dropout 0.2, AdamW, max lr 1e-3 with 30% warm-up, lookback 50. Our deviations:
batch 256 (not 64) and early stopping on the last 20% of the training window (max 30 epochs, patience 5)
instead of a fixed 100 epochs.
"""

import math
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn
from sklearn.linear_model import Ridge

import features as F


def device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


DEV = device()


def _rows(X, y, idx):
    """Flatten (d, name) rows with a finite target and finite features."""
    Xr, yr = X[idx].reshape(-1, X.shape[-1]), y[idx].reshape(-1)
    m = np.isfinite(yr) & np.isfinite(Xr).all(1)
    return Xr[m], yr[m]


# ------------------------------------------------------------------------------------------------- ridge
def ridge(X, y, train, test, h, alphas=(0.1, 1, 10, 100, 1000), **_):
    tr, va = F.split_val(train, h=h)
    Xt, yt = _rows(X, y, tr)
    Xv, yv = _rows(X, y, va)
    best = min(alphas, key=lambda a: np.mean((Ridge(alpha=a).fit(Xt, yt).predict(Xv) - yv) ** 2))
    m = Ridge(alpha=best).fit(*_rows(X, y, train))
    pred = np.full(y.shape, np.nan)
    Xs = np.nan_to_num(X[test])
    pred[test] = m.predict(Xs.reshape(-1, X.shape[-1])).reshape(len(test), -1)
    return pred, {"alpha": best}


# ------------------------------------------------------------------------------------------------- nets
class MLP(nn.Module):
    def __init__(self, f, hid=64, p=0.2):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(f, hid), nn.ReLU(), nn.Dropout(p), nn.Linear(hid, hid), nn.ReLU(),
                                 nn.Dropout(p), nn.Linear(hid, 1))

    def forward(self, x):                      # x (B, F)
        return self.net(x).squeeze(-1)


class PosEnc(nn.Module):
    def __init__(self, d, n=512):
        super().__init__()
        pe = torch.zeros(n, d)
        pos = torch.arange(n).float()[:, None]
        div = torch.exp(torch.arange(0, d, 2).float() * (-math.log(10000.0) / d))
        pe[:, 0::2], pe[:, 1::2] = torch.sin(pos * div), torch.cos(pos * div)
        self.register_buffer("pe", pe[None])

    def forward(self, x):
        return x + self.pe[:, : x.size(1)]


class AngularMHA(nn.Module):
    """CSHT-style attention (2510.04357 §4.4): unit-norm queries and keys, scores lambda * cos(q, k)."""

    def __init__(self, d, heads, lam=10.0, p=0.2):
        super().__init__()
        self.h, self.dk, self.lam = heads, d // heads, lam
        self.qkv, self.o, self.drop = nn.Linear(d, 3 * d), nn.Linear(d, d), nn.Dropout(p)

    def forward(self, x, mask=None):           # mask (T, T) bool, True = may attend
        B, T, D = x.shape
        q, k, v = self.qkv(x).view(B, T, 3, self.h, self.dk).permute(2, 0, 3, 1, 4)
        s = self.lam * (Fn.normalize(q, dim=-1) @ Fn.normalize(k, dim=-1).transpose(-1, -2))
        if mask is not None:
            s = s.masked_fill(~mask, float("-inf"))
        a = self.drop(torch.softmax(s, -1))
        return self.o((a @ v).transpose(1, 2).reshape(B, T, D))


class DotMHA(AngularMHA):
    def forward(self, x, mask=None):
        B, T, D = x.shape
        q, k, v = self.qkv(x).view(B, T, 3, self.h, self.dk).permute(2, 0, 3, 1, 4)
        s = (q @ k.transpose(-1, -2)) / math.sqrt(self.dk)
        if mask is not None:
            s = s.masked_fill(~mask, float("-inf"))
        a = self.drop(torch.softmax(s, -1))
        return self.o((a @ v).transpose(1, 2).reshape(B, T, D))


class Block(nn.Module):
    def __init__(self, d, heads, ff, p, angular):
        super().__init__()
        self.n1, self.n2 = nn.LayerNorm(d), nn.LayerNorm(d)
        self.att = (AngularMHA if angular else DotMHA)(d, heads, p=p)
        self.ff = nn.Sequential(nn.Linear(d, ff), nn.ReLU(), nn.Dropout(p), nn.Linear(ff, d))
        self.drop = nn.Dropout(p)

    def forward(self, x, mask=None):
        x = x + self.drop(self.att(self.n1(x), mask))
        return x + self.drop(self.ff(self.n2(x)))


class SeqTransformer(nn.Module):
    """The paper's TimeSeriesTransformer: project, x sqrt(d), ReLU, positional encoding, pre-LN encoder,
    last step -> linear."""

    def __init__(self, f, d=32, heads=4, layers=4, ff=128, p=0.2, angular=False):
        super().__init__()
        self.d = d
        self.inp, self.pe, self.pdrop = nn.Linear(f, d), PosEnc(d), nn.Dropout(p)
        self.blocks = nn.ModuleList([Block(d, heads, ff, p, angular) for _ in range(layers)])
        self.out = nn.Linear(d, 1)

    def forward(self, x):                      # x (B, L, F)
        z = self.pdrop(self.pe(torch.relu(self.inp(x) * math.sqrt(self.d))))
        for b in self.blocks:
            z = b(z)
        return self.out(z[:, -1]).squeeze(-1)


class CrossSection(nn.Module):
    """Trial E: attention across the names on one date; mask (N, N) True where name i may read name j."""

    def __init__(self, f, mask, d=32, heads=4, layers=2, ff=128, p=0.2, angular=False):
        super().__init__()
        self.inp = nn.Linear(f, d)
        self.blocks = nn.ModuleList([Block(d, heads, ff, p, angular) for _ in range(layers)])
        self.out = nn.Linear(d, 1)
        self.register_buffer("mask", torch.as_tensor(mask, dtype=torch.bool))

    def forward(self, x):                      # x (B, N, F)
        z = torch.relu(self.inp(x))
        for b in self.blocks:
            z = b(z, self.mask)
        return self.out(z).squeeze(-1)


# ------------------------------------------------------------------------------------------------- training
def _train(model, batches_tr, batches_va, epochs=30, patience=5, lr=1e-3, seed=0):
    """batches_*: callables yielding (xb, yb, wb) tensors per epoch. MSE on finite targets."""
    model.to(DEV)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    n_steps = epochs * max(1, batches_tr.n)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=n_steps, pct_start=0.3)
    best, best_state, bad = np.inf, None, 0
    for ep in range(epochs):
        model.train()
        for xb, yb, wb in batches_tr():
            opt.zero_grad()
            loss = (((model(xb) - yb) ** 2) * wb).sum() / wb.sum().clamp(min=1)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
        model.eval()
        num = den = 0.0
        with torch.no_grad():
            for xb, yb, wb in batches_va():
                num += float(((((model(xb) - yb) ** 2) * wb).sum()))
                den += float(wb.sum())
        v = num / max(den, 1)
        if v < best - 1e-6:
            best, bad = v, 0
            best_state = {k: t.detach().clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state)
    return model, {"val_mse": best, "epochs": ep + 1}


def _tensor(a):
    return torch.as_tensor(np.ascontiguousarray(a), dtype=torch.float32, device=DEV)


def _row_batcher(X, y, idx, bs, shuffle, rng):
    Xr, yr = _rows(X, y, idx)

    def gen():
        order = rng.permutation(len(yr)) if shuffle else np.arange(len(yr))
        for i in range(0, len(order), bs):
            j = order[i: i + bs]
            yield _tensor(Xr[j]), _tensor(yr[j]), torch.ones(len(j), device=DEV)
    gen.n = math.ceil(len(yr) / bs)
    return gen


def _seq_pairs(X, y, idx, L):
    """(d, name) pairs with a finite target and a full, finite L-session history."""
    ok = np.isfinite(X).all(-1)
    cum = np.vstack([np.zeros((1, ok.shape[1])), np.cumsum(ok, 0)])
    pairs = []
    for d in idx:
        if d - L + 1 < 0:
            continue
        full = (cum[d + 1] - cum[d - L + 1]) == L
        tgt = np.isfinite(y[d]) if y is not None else np.ones(X.shape[1], bool)
        for i in np.where(full & tgt)[0]:
            pairs.append((d, i))
    return np.array(pairs, int).reshape(-1, 2)


def _seq_batcher(Xt, y, pairs, L, bs, shuffle, rng):
    """Xt: (D, N, F) tensor on DEV; windows gathered on the device."""
    off = torch.arange(-L + 1, 1, device=DEV)
    yt = _tensor(np.nan_to_num(y))

    def gen():
        order = rng.permutation(len(pairs)) if shuffle else np.arange(len(pairs))
        for i in range(0, len(order), bs):
            pj = torch.as_tensor(pairs[order[i: i + bs]], device=DEV)
            dd = pj[:, :1] + off[None]                        # (B, L)
            xb = Xt[dd, pj[:, 1:2].expand_as(dd)]              # (B, L, F)
            yield xb, yt[pj[:, 0], pj[:, 1]], torch.ones(len(pj), device=DEV)
    gen.n = math.ceil(len(pairs) / bs)
    return gen


def _xs_batcher(Xt, y, idx, bs, shuffle, rng):
    """Cross-section: one sample = one date, all names; names with no target get weight 0."""
    idx = np.array([d for d in idx if np.isfinite(y[d]).sum() >= 10])
    yt = _tensor(np.nan_to_num(y))
    wt = _tensor(np.isfinite(y).astype(np.float32))

    def gen():
        order = rng.permutation(len(idx)) if shuffle else np.arange(len(idx))
        for i in range(0, len(order), bs):
            d = torch.as_tensor(idx[order[i: i + bs]], device=DEV)
            yield Xt[d], yt[d], wt[d]
    gen.n = math.ceil(len(idx) / bs)
    return gen


def net(X, y, train, test, h, kind="mlp", seeds=5, L=50, mask=None, angular=False, bs=256, **_):
    """Seed-averaged predictions of an MLP ('mlp'), the paper's sequence transformer ('seq') or the
    cross-sectional attention model ('xs')."""
    global DEV
    DEV = torch.device("cpu") if kind == "mlp" else device()       # tiny MLPs are faster on CPU (benchmarked)
    tr, va = F.split_val(train, h=h)
    Xc = np.nan_to_num(X).astype(np.float32)
    Xt = _tensor(Xc)
    preds, info = [], []
    for s in range(seeds):
        torch.manual_seed(s)
        rng = np.random.default_rng(s)
        f = X.shape[-1]
        if kind == "mlp":
            model = MLP(f)
            btr, bva = _row_batcher(X, y, tr, bs, True, rng), _row_batcher(X, y, va, bs, False, rng)
        elif kind == "seq":
            model = SeqTransformer(f, angular=angular)
            btr = _seq_batcher(Xt, y, _seq_pairs(X, y, tr, L), L, bs, True, rng)
            bva = _seq_batcher(Xt, y, _seq_pairs(X, y, va, L), L, bs, False, rng)
        elif kind == "xs":
            model = CrossSection(f, mask, angular=angular)
            btr, bva = _xs_batcher(Xt, y, tr, 32, True, rng), _xs_batcher(Xt, y, va, 32, False, rng)
        else:
            raise ValueError(kind)
        t0 = time.time()
        model, inf = _train(model, btr, bva, seed=s)
        print(f"      seed {s}: {inf['epochs']} epochs, val {inf['val_mse']:.4f}, {time.time() - t0:.0f}s", flush=True)
        model.eval()
        pred = np.full(y.shape, np.nan, np.float32)
        with torch.no_grad():
            if kind == "mlp":
                xs = _tensor(Xc[test].reshape(-1, f))
                pred[test] = model(xs).cpu().numpy().reshape(len(test), -1)
            elif kind == "seq":
                pairs = _seq_pairs(X, None, test, L)
                out = []
                for xb, _, _ in _seq_batcher(Xt, y, pairs, L, 1024, False, rng)():
                    out.append(model(xb).cpu().numpy())
                pred[pairs[:, 0], pairs[:, 1]] = np.concatenate(out)
            else:
                pred[test] = model(Xt[torch.as_tensor(test, device=DEV)]).cpu().numpy()
        preds.append(pred)
        info.append(inf)
    return np.nanmean(np.stack(preds), 0) if seeds > 1 else preds[0], {
        "epochs": [i["epochs"] for i in info], "val_mse": float(np.mean([i["val_mse"] for i in info]))}


# ------------------------------------------------------------------------------------------------- Siamese
class Tower(nn.Module):
    """2605.30652 §4.3.2: Linear(dim->256), ReLU, Linear(256->64)."""

    def __init__(self, dim, hid=256, out=64):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, hid), nn.ReLU(), nn.Linear(hid, out))

    def forward(self, x):
        return self.net(x)


def siamese(V, labels, epochs=15, pairs_per_epoch=20000, margin=1.0, lr=1e-4, bs=64, seed=0):
    """Contrastive training on (vector, tercile label) items; returns the tower (on CPU) and its last-epoch
    pair accuracy on a held-out 20% of items (the paper's AUC-style check)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    n = len(V)
    perm = rng.permutation(n)
    hold, fit = perm[: n // 5], perm[n // 5:]
    tower = Tower(V.shape[1]).to(DEV)
    opt = torch.optim.Adam(tower.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=2)
    Vt, lt = _tensor(V), torch.as_tensor(labels, device=DEV)

    def batch(pool, k):
        a, b = rng.choice(pool, k), rng.choice(pool, k)
        return torch.as_tensor(a, device=DEV), torch.as_tensor(b, device=DEV)

    def loss_of(a, b):
        same = (lt[a] == lt[b]).float()
        dist = torch.norm(tower(Vt[a]) - tower(Vt[b]), dim=-1)
        return 0.5 * (same * dist ** 2 + (1 - same) * torch.clamp(margin - dist, min=0) ** 2).mean(), dist, same

    for ep in range(epochs):
        tower.train()
        for _ in range(pairs_per_epoch // bs):
            a, b = batch(fit, bs)
            opt.zero_grad()
            loss, _, _ = loss_of(a, b)
            loss.backward()
            opt.step()
        tower.eval()
        with torch.no_grad():
            a, b = batch(hold, 4000)
            vl, dist, same = loss_of(a, b)
        sched.step(float(vl))
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(same.cpu().numpy(), -dist.cpu().numpy())
    return tower.cpu(), float(auc)


# ------------------------------------------------------------------------------------------------- kernels / trees
def rff_ridge(X, y, train, test, h, P=4000, gamma=2.0, seeds=5,
              shrink=(1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 10, 100, 1e3), **_):
    """Kernel learning by random Fourier features + ridge (Kelly, Malamud & Zhou 2024, 'The Virtue of
    Complexity in Return Prediction'): z(x) = [sin(gamma W x), cos(gamma W x)] / sqrt(P), W ~ N(0, I),
    an approximation of a Gaussian kernel. Ridge penalty picked on the last 20% of the training window;
    predictions averaged over `seeds` draws of W. Primal solve via an eigendecomposition of Z'Z (P x P)."""
    tr, va = F.split_val(train, h=h)
    Xt, yt = _rows(X, y, tr)
    Xv, yv = _rows(X, y, va)
    Xa, ya = _rows(X, y, train)
    Xs = np.nan_to_num(X[test]).reshape(-1, X.shape[-1])
    if gamma == "median":                      # median heuristic: kernel = exp(-1/2) at the median distance
        r = np.random.default_rng(0)
        i, j = r.choice(len(Xt), 4000), r.choice(len(Xt), 4000)
        gamma = float(1 / np.sqrt(np.median(((Xt[i] - Xt[j]) ** 2).sum(1))))
    preds, chosen = [], []
    for s in range(seeds):
        W = np.random.default_rng(100 + s).normal(size=(X.shape[-1], P // 2)).astype(np.float32)

        def feats(A):
            Z = gamma * (A.astype(np.float32) @ W)
            return np.hstack([np.sin(Z), np.cos(Z)]) / np.sqrt(P)

        def fit(Z, yy):
            G = Z.T @ Z
            ev, V = np.linalg.eigh(G.astype(np.float64))
            b = V.T @ (Z.T @ yy)
            n = len(yy)
            return lambda z: V @ (b / (ev + z * n))
        Zt = feats(Xt)
        solve = fit(Zt, yt)
        Zv = feats(Xv)
        best = min(shrink, key=lambda z: np.mean((Zv @ solve(z) - yv) ** 2))
        beta = fit(feats(Xa), ya)(best)
        p = np.full(y.shape, np.nan)
        p[test] = (feats(Xs) @ beta).reshape(len(test), -1)
        preds.append(p)
        chosen.append(best)
    return np.mean(preds, 0), {"shrink": chosen, "P": P, "gamma": gamma}


def gbrt(X, y, train, test, h, seeds=5, **_):
    """Gradient-boosted trees (Gu, Kelly & Xiu 2020): shallow histogram GBRT, early stopping on the last
    20% of the training window, seed-averaged."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    tr, va = F.split_val(train, h=h)
    Xt, yt = _rows(X, y, tr)
    Xv, yv = _rows(X, y, va)
    Xs = np.nan_to_num(X[test]).reshape(-1, X.shape[-1])
    preds, iters = [], []
    for s in range(seeds):
        m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.03, max_iter=600, min_samples_leaf=200,
                                          l2_regularization=1.0, max_features=0.8, random_state=s,
                                          early_stopping=False)
        best, best_it = np.inf, 50
        m.fit(Xt, yt)
        for it, pv in enumerate(m.staged_predict(Xv), 1):
            e = np.mean((pv - yv) ** 2)
            if e < best:
                best, best_it = e, it
        m2 = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.03, max_iter=best_it, min_samples_leaf=200,
                                           l2_regularization=1.0, max_features=0.8, random_state=s,
                                           early_stopping=False)
        m2.fit(*_rows(X, y, train))
        p = np.full(y.shape, np.nan)
        p[test] = m2.predict(Xs).reshape(len(test), -1)
        preds.append(p)
        iters.append(best_it)
    return np.mean(preds, 0), {"iters": iters}


# ------------------------------------------------------------------------------------------------- IC-tuned variants
def _val_ic(pred_rows, y, va, shape):
    """Mean daily cross-sectional Spearman IC of predictions on the validation decisions."""
    pr = np.full(shape, np.nan)
    pr[va] = pred_rows
    return np.nanmean(F.weekly_ic(pr, y, va))


def ridge_ic(X, y, train, test, h, alphas=(1e-2, 1e-1, 1, 10, 100, 1e3, 1e4, 1e5), **_):
    """Ridge with the penalty chosen by validation rank IC (the scored objective), not MSE."""
    tr, va = F.split_val(train, h=h)
    Xt, yt = _rows(X, y, tr)
    Xv = np.nan_to_num(X[va]).reshape(-1, X.shape[-1])
    score = {a: _val_ic(Ridge(alpha=a).fit(Xt, yt).predict(Xv).reshape(len(va), -1), y, va, y.shape) for a in alphas}
    best = max(score, key=score.get)
    m = Ridge(alpha=best).fit(*_rows(X, y, train))
    pred = np.full(y.shape, np.nan)
    pred[test] = m.predict(np.nan_to_num(X[test]).reshape(-1, X.shape[-1])).reshape(len(test), -1)
    return pred, {"alpha": best}


def gbrt_ic(X, y, train, test, h, seeds=5, checkpoints=(25, 50, 100, 200, 400, 600), **_):
    """GBRT with the number of trees chosen by validation rank IC among fixed checkpoints (floor 25)."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    tr, va = F.split_val(train, h=h)
    Xt, yt = _rows(X, y, tr)
    Xv = np.nan_to_num(X[va]).reshape(-1, X.shape[-1])
    Xs = np.nan_to_num(X[test]).reshape(-1, X.shape[-1])
    kw = dict(max_depth=3, learning_rate=0.03, min_samples_leaf=200, l2_regularization=1.0, max_features=0.8, early_stopping=False)
    preds, iters = [], []
    for s in range(seeds):
        m = HistGradientBoostingRegressor(max_iter=max(checkpoints), random_state=s, **kw).fit(Xt, yt)
        sc = {}
        for it, pv in enumerate(m.staged_predict(Xv), 1):
            if it in checkpoints:
                sc[it] = _val_ic(pv.reshape(len(va), -1), y, va, y.shape)
        best = max(sc, key=sc.get)
        m2 = HistGradientBoostingRegressor(max_iter=best, random_state=s, **kw).fit(*_rows(X, y, train))
        p = np.full(y.shape, np.nan)
        p[test] = m2.predict(Xs).reshape(len(test), -1)
        preds.append(p)
        iters.append(best)
    return np.mean(preds, 0), {"iters": iters}
