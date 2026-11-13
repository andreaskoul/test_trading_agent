"""Branch Q2_xsattn: cross-name attention and market-state gating over one week's cross-section.

    from model import make, BEST
    pred = harness.walk_forward(make(**BEST), seeds=(0, 1, 2))

Each Thursday is one training sample: the set of eligible names (about 500), each with the 27 inputs of
D_ensembles/model.py (five characteristics D["Z"] and 22 return features, ranked across the eligible names of the
day), optionally the last 60 daily hedged returns (divided by that day's cross-sectional sd). The network:

    token  = Linear(inputs [* market feature gate]) [+ Linear(history)]
    encoder: `depth` pre-norm residual MLP blocks (per name)
    cross:   `nx` blocks of  [h += Attention_across_names(LN h)]  +  h += FF(LN h)
             xs = "none" (ablation: the FF sublayers stay, only the attention term is dropped), "sab" (full self-
             attention over the names), "isab" (induced-point set attention, m points), "pool" (h += W mean(h))
    head:    K expert MLPs; gate = "uniform" (ablation: plain mean of the experts) or "state" (softmax over experts
             from seven causal market-state numbers); fgate = MASTER-style market-guided scaling of the inputs.

Loss per week (listwise): "ic" = minus the Pearson correlation of the output with the cross-sectional rank of y5
(a differentiable rank IC), "mse" = squared error on the standardised rank, "listnet" = softmax cross-entropy.
Inner early stopping: the epoch count is chosen by mean rank IC on the last 52 training Thursdays (fit on the
Thursdays at least two weeks before them); then the network is refitted on all training Thursdays for that many
epochs. Only rows <= train_end are used for fitting; the harness blanks later targets.
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

THREADS = 3
torch.set_num_threads(THREADS)
DEV = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

DEFAULT = dict(
    hist=False, H=60,          # add the last H standardised daily hedged returns as an input
    d=64, depth=2, dropout=0.1,
    xs="none", nx=1, heads=4, m=16,
    K=1, gate="uniform", fgate=False,
    na=False,                  # append 22 missing-value indicators of the return features (else NaN -> 0 only)
    loss="ic", lr=1e-3, wd=1e-3, batch=8, max_epochs=30, patience=8, inner=1,
    refit=True,
)
# Best configuration on development data (REPORT.md): moe_unif_d128, IC 0.0232 (seeds 0-2), 6/7 years positive.
# It has NO cross-name module and NO gate: neither module beat its ablation. Run on MPS; MPS kernels are not bit-
# deterministic, so a re-run reproduces the IC to about +-0.001, not exactly.
BEST = dict(DEFAULT, K=4, d=128, depth=3)
CONTROL_PAIR = dict(module=dict(BEST, xs="pool"), ablation=BEST)   # the nominated module-vs-ablation pair


def fit_predict(D, train_end, pred_rows, seed):
    """The best configuration, harness contract."""
    return _BEST_FP(D, train_end, pred_rows, seed)

_F = {}


# ------------------------------------------------------------------ inputs (copied from D_ensembles/model.py)
def _xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def _features(D):
    e, r = pd.DataFrame(D["e"].astype(np.float64)), pd.DataFrame(D["r"].astype(np.float64))
    f = {}
    for w in (1, 5, 10, 21, 63, 126):
        f[f"e{w}"] = e.rolling(w, min_periods=max(1, int(w * 0.8))).sum()
    f["mom12_1"] = e.shift(21).rolling(231, min_periods=180).sum()
    f["r5"] = r.rolling(5, min_periods=4).sum()
    f["r21"] = r.rolling(21, min_periods=17).sum()
    for w in (10, 21, 63, 250):
        f[f"v{w}"] = e.rolling(w, min_periods=int(w * 0.8)).std()
    f["vratio"] = f["v10"] / f["v63"]
    f["max21"] = e.rolling(21, min_periods=17).max()
    f["min21"] = e.rolling(21, min_periods=17).min()
    f["sharpe63"] = f["e63"] / (f["v63"] * np.sqrt(63))
    f["z5"] = f["e5"] / (f["v63"] * np.sqrt(5))
    f["dd126"] = e.cumsum() - e.cumsum().rolling(126, min_periods=100).max()
    f["beta"] = pd.DataFrame(D["beta"].astype(np.float64))
    cols = []
    for v in f.values():
        a = v.to_numpy().copy()
        a[~D["elig"]] = np.nan
        cols.append(_xrank(a))
    R = np.stack(cols, 2)
    X = np.concatenate([D["Z"].astype(np.float64).clip(-4, 4) / 4, R], 2)
    return np.nan_to_num(X, nan=0.0).astype(np.float32), ~np.isfinite(R)


def _states(D):
    """Daily market state (T, 7), row t uses rows <= t only (as E_regime/lib.py): market trend 21/63/252, log vol 21,
    log(vol21/vol252), log mean dispersion 21, about the average pairwise correlation over 63 sessions."""
    rm = pd.Series(D["rm"].astype(np.float64))
    r = np.where(D["elig"], D["r"], np.nan).astype(np.float64)
    with np.errstate(all="ignore"):
        disp = pd.Series(np.nanstd(r, 1))
        mean_var = pd.DataFrame(r).rolling(63, min_periods=40).var().mean(1)
        ew = pd.Series(np.nanmean(r, 1))
    vol21, vol252 = rm.rolling(21).std(), rm.rolling(252).std()
    S = pd.DataFrame({"trend21": rm.rolling(21).sum(), "trend63": rm.rolling(63).sum(), "trend252": rm.rolling(252).sum(),
                      "vol21": np.log(vol21), "volchg": np.log(vol21 / vol252), "disp21": np.log(disp.rolling(21).mean()),
                      "corr63": ew.rolling(63).var() / mean_var})
    return S.to_numpy()


def _prep(D):
    """Pack every Thursday from row 260 once: inputs, history, mask (eligible and finite Z), name index."""
    key = id(D["e"])
    if key in _F:
        return _F[key]
    X, NA = _features(D)
    St = _states(D)
    e = D["e"].astype(np.float32)
    with np.errstate(all="ignore"):
        sd = np.nanstd(np.where(D["elig"], e, np.nan), axis=1, keepdims=True)
    sd[~np.isfinite(sd) | (sd <= 0)] = np.nan
    es = np.clip(np.nan_to_num(e / sd, nan=0.0, posinf=0.0, neginf=0.0), -5, 5).astype(np.float32)
    S = D["S"]
    rows = np.where((S.weekday == 3) & (np.arange(len(S)) >= 260))[0]
    ok = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(-1)
    N, W, Hm = int(ok.sum(1).max()), len(rows), DEFAULT["H"]
    Xw = np.zeros((W, N, X.shape[2] + NA.shape[2]), np.float32)
    Hw = np.zeros((W, N, Hm), np.float32)
    mk = np.zeros((W, N), bool)
    idx = np.zeros((W, N), np.int64)
    for i, t in enumerate(rows):
        j = np.where(ok[i])[0]
        n = len(j)
        Xw[i, :n, :X.shape[2]] = X[t, j]
        Xw[i, :n, X.shape[2]:] = NA[t, j]
        Hw[i, :n] = es[t - Hm + 1:t + 1, j].T
        mk[i, :n] = True
        idx[i, :n] = j
    _F.clear()
    _F[key] = dict(rows=rows, X=torch.from_numpy(Xw).to(DEV), Hh=torch.from_numpy(Hw).to(DEV), mk=torch.from_numpy(mk).to(DEV),
                  mk_np=mk, idx=idx, St=St)
    return _F[key]


# ------------------------------------------------------------------ network
class FF(nn.Module):
    def __init__(self, d, p):
        super().__init__()
        self.n, self.f = nn.LayerNorm(d), nn.Sequential(nn.Linear(d, 2 * d), nn.GELU(), nn.Dropout(p), nn.Linear(2 * d, d))

    def forward(self, h):
        return h + self.f(self.n(h))


class Cross(nn.Module):
    """One cross-name block. kind "none" keeps only the FF sublayer (the declared ablation)."""

    def __init__(self, kind, d, heads, m, p):
        super().__init__()
        self.kind = kind
        self.n = nn.LayerNorm(d)
        if kind in ("sab", "isab"):
            self.a1 = nn.MultiheadAttention(d, heads, dropout=p, batch_first=True)
        if kind == "isab":
            self.I = nn.Parameter(torch.randn(1, m, d) * 0.02)
            self.n2 = nn.LayerNorm(d)
            self.a2 = nn.MultiheadAttention(d, heads, dropout=p, batch_first=True)
        if kind == "pool":
            self.pw = nn.Linear(d, d)
        self.ff = FF(d, p)

    def forward(self, h, mask):                 # h (B,N,d), mask (B,N) True = real name
        if self.kind == "sab":
            q = self.n(h)
            h = h + self.a1(q, q, q, key_padding_mask=~mask, need_weights=False)[0]
        elif self.kind == "isab":
            q = self.n(h)
            ind = self.I.expand(h.shape[0], -1, -1)
            Hs = ind + self.a1(ind, q, q, key_padding_mask=~mask, need_weights=False)[0]     # induced points read the names
            Hs = self.n2(Hs)
            h = h + self.a2(q, Hs, Hs, need_weights=False)[0]                               # names read the induced points
        elif self.kind == "pool":
            q = self.n(h)
            mf = mask.unsqueeze(-1).float()
            h = h + self.pw((q * mf).sum(1, keepdim=True) / mf.sum(1, keepdim=True).clamp(min=1))
        return self.ff(h)


class Net(nn.Module):
    def __init__(self, c, F, nS):
        super().__init__()
        d, p = c["d"], c["dropout"]
        self.c = c
        self.inp = nn.Linear(F, d)
        self.hp = nn.Linear(c["H"], d) if c["hist"] else None
        self.fg = nn.Linear(nS, F) if c["fgate"] else None
        self.enc = nn.ModuleList([FF(d, p) for _ in range(c["depth"])])
        self.cross = nn.ModuleList([Cross(c["xs"], d, c["heads"], c["m"], p) for _ in range(c["nx"])])
        self.experts = nn.ModuleList([nn.Sequential(nn.LayerNorm(d), nn.Linear(d, d), nn.GELU(), nn.Linear(d, 1)) for _ in range(c["K"])])
        self.g = nn.Linear(nS, c["K"]) if (c["gate"] == "state" and c["K"] > 1) else None

    def forward(self, X, Hh, s, mask):          # X (B,N,F), Hh (B,N,H), s (B,nS)
        X = X if self.c["na"] else X[..., :27]
        if self.fg is not None:                 # MASTER market-guided feature selection: F * softmax(W s)
            X = X * (torch.softmax(self.fg(s), -1) * X.shape[-1]).unsqueeze(1)
        h = self.inp(X)
        if self.hp is not None:
            h = h + self.hp(Hh)
        for b in self.enc:
            h = b(h)
        for b in self.cross:
            h = b(h, mask)
        o = torch.cat([ex(h) for ex in self.experts], -1)          # (B,N,K)
        if self.g is not None:
            return (o * torch.softmax(self.g(s), -1).unsqueeze(1)).sum(-1)
        return o.mean(-1)


# ------------------------------------------------------------------ training
def _loss(kind, out, y, mask):
    mf = mask.float()
    n = mf.sum(1).clamp(min=1)
    if kind == "mse":
        return (((out - y) ** 2) * mf).sum() / mf.sum()
    if kind == "listnet":
        o = out.masked_fill(~mask, -1e9)
        t = (y * 3).masked_fill(~mask, -1e9)
        return -(torch.softmax(t, -1) * torch.log_softmax(o, -1)).sum(-1).mean()
    om = (out * mf).sum(1, keepdim=True) / n.unsqueeze(1)
    oc = (out - om) * mf
    corr = (oc * y).sum(1) / (oc.pow(2).sum(1).sqrt() * y.pow(2).sum(1).sqrt() + 1e-8)
    return -corr.mean()


def _targets(D, P, sel):
    """Standardised cross-sectional rank of y5 on the masked names of the selected Thursdays; mask drops NaN y."""
    y5 = D["y5"]
    W, N = P["mk"].shape[0], P["mk"].shape[1]
    Y = np.zeros((len(sel), N), np.float32)
    M = np.zeros((len(sel), N), bool)
    for k, i in enumerate(sel):
        mk = P["mk_np"][i]
        yy = np.full(N, np.nan)
        yy[mk] = y5[P["rows"][i], P["idx"][i][mk]]
        m = np.isfinite(yy)
        if m.sum() < 50:
            continue
        r = pd.Series(yy[m]).rank().to_numpy()
        Y[k, m] = (r - r.mean()) / r.std()
        M[k, m] = True
    return torch.from_numpy(Y).to(DEV), torch.from_numpy(M).to(DEV)


def _predict(net, P, sel, Sz):
    net.eval()
    outs = []
    with torch.no_grad():
        for s in range(0, len(sel), 16):
            b = torch.as_tensor(sel[s:s + 16], device=DEV)
            outs.append(net(P["X"][b], P["Hh"][b], Sz[b], P["mk"][b]))
    return torch.cat(outs).cpu().numpy()


def _ic(out, Y, M):
    v = []
    for o, y, m in zip(out, Y.cpu().numpy(), M.cpu().numpy()):
        if m.sum() >= 50:
            v.append(pd.Series(o[m]).corr(pd.Series(y[m]), method="spearman"))
    return float(np.mean(v))


def _train(c, P, Sz, sel, Y, M, epochs, seed, val=None):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = Net(c, P["X"].shape[2] if c["na"] else 27, Sz.shape[1]).to(DEV)
    opt = torch.optim.AdamW(net.parameters(), lr=c["lr"], weight_decay=c["wd"])
    hist = []
    best, bad = -9.0, 0
    for ep in range(epochs):
        net.train()
        perm = rng.permutation(len(sel))
        for s in range(0, len(sel), c["batch"]):
            k = torch.as_tensor(perm[s:s + c["batch"]], device=DEV)
            b = torch.as_tensor(sel, device=DEV)[k]
            out = net(P["X"][b], P["Hh"][b], Sz[b], P["mk"][b])      # attend over every eligible name, as at prediction
            loss = _loss(c["loss"], out, Y[k], M[k])
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
        if val is not None:
            vs, vY, vM = val
            hist.append(_ic(_predict(net, P, vs, Sz), vY, vM))
            sm = np.mean(hist[-3:])                         # 3-epoch moving average, less noisy than one epoch
            if sm > best + 1e-4:
                best, bad = sm, 0
            else:
                bad += 1
                if bad >= c["patience"]:
                    break
    return net, hist


def make(**over):
    c = dict(DEFAULT, **over)

    def fit_predict(D, train_end, pred_rows, seed):
        torch.set_num_threads(THREADS)
        P = _prep(D)
        rows = P["rows"]
        St = P["St"]
        mu, sd = np.nanmean(St[260:train_end + 1], 0), np.nanstd(St[260:train_end + 1], 0) + 1e-12
        Sz = torch.from_numpy(np.nan_to_num(np.clip((St[rows] - mu) / sd, -3, 3)).astype(np.float32)).to(DEV)
        tr = np.where(rows <= train_end)[0]
        Y, M = _targets(D, P, tr)
        keep = M.cpu().numpy().sum(1) >= 50
        tr = tr[keep]
        kt = torch.as_tensor(np.where(keep)[0], device=DEV)
        Y, M = Y[kt], M[kt]
        nv = 52
        va, fi = np.arange(len(tr) - nv, len(tr)), np.arange(0, len(tr) - nv - 2)      # two-week gap before validation
        out = 0
        for j in range(c["inner"]):
            sd_ = seed * 100 + j
            tf, tv = torch.as_tensor(fi, device=DEV), torch.as_tensor(va, device=DEV)
            net, hist = _train(c, P, Sz, tr[fi], Y[tf], M[tf], c["max_epochs"], sd_, val=(tr[va], Y[tv], M[tv]))
            sm = [np.mean(hist[max(0, i - 2):i + 1]) for i in range(len(hist))]
            ep = int(np.argmax(sm)) + 1
            if c["refit"]:
                net, _ = _train(c, P, Sz, tr, Y, M, ep, sd_)
            fit_predict.log.append(dict(te=int(train_end), seed=seed, inner=j, epochs=ep, val_ic=float(sm[ep - 1])))
            pr = np.asarray(pred_rows)
            ps = np.searchsorted(rows, pr)
            assert (rows[ps] == pr).all()
            o = _predict(net, P, ps, Sz)
            o = pd.DataFrame(np.where(P["mk_np"][ps], o, np.nan)).rank(axis=1, pct=True).to_numpy()
            out = out + o
        out = out / c["inner"]
        pred = np.full((len(pred_rows), D["y5"].shape[1]), np.nan)
        for i, p in enumerate(ps):
            m = P["mk_np"][p]
            pred[i, P["idx"][p][m]] = out[i][m]
        return pred

    fit_predict.config = c
    fit_predict.log = []
    return fit_predict


_BEST_FP = make(**BEST)
