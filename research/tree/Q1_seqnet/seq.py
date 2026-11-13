"""Q1_seqnet: sequence networks on each name's last L sessions, fused with static characteristics.

    from seq import make
    fit_predict = make(enc="gru", static="D27", loss="ic", ...)

Every input for prediction row t uses rows <= t only. Training uses Thursdays <= train_end (the harness blanks later
targets); the inner early-stopping split is the last `es_weeks` training Thursdays (8-row gap), never the validation year.
"""
import os
import sys

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, TREE)

torch.set_num_threads(3)

DEFAULT = dict(
    enc="gru",          # None | "gru" | "lstm" | "tcn" | "tfm"
    L=60,               # sessions of history
    chans=("e", "r", "rm", "ae"),   # sequence channels; add "vol" for FINRA abnormal volume (2012+ only)
    seq_rank=False,     # e/r channels as cross-sectional ranks instead of cs z-scores
    static="Z",         # "Z" (5) | "D27" | "C32" | "DC" (both) | None
    d=32,
    loss="mse",         # "mse" | "ic" | "listnet" | "mse+ic"
    horizons=(5,),      # extra heads on longer/shorter horizons; head 0 (5 sessions) predicts
    hw=0.5,             # weight on the extra heads
    epochs=8, lr=1e-3, wd=1e-4, dropout=0.1,
    batch_dates=8,
    es_weeks=0,         # 0 = no early stopping (fixed epochs); else inner validation on the last es_weeks training Thursdays
    refit=False,        # with es_weeks: refit on all training rows for the chosen number of epochs
    n_ens=1,            # models per seed (seeds seed*100+i), ranks averaged
    device="cpu",
    all_days=False,     # train on every session, not only Thursdays
    inorm=False,        # False | "scale" | "center": per-window instance normalisation of the e/r channels
)

_C = {}


def _xrank(a):
    return pd.DataFrame(a).rank(axis=1, pct=True).to_numpy() - 0.5


def _seq_channels(D, c):
    key = ("seq", id(D["e"]), tuple(c["chans"]), c["seq_rank"])
    if key in _C:
        return _C[key]
    elig = D["elig"]
    out = []
    for ch in c["chans"]:
        if ch in ("e", "r"):
            a = D[ch].astype(np.float64)
            if c["seq_rank"]:
                x = _xrank(np.where(np.isfinite(a), a, np.nan)) * np.sqrt(12)
            else:
                with np.errstate(all="ignore"):
                    sd = np.nanstd(a, 1, keepdims=True)
                    x = np.clip(a / sd, -5, 5)
        elif ch == "rm":
            rm = pd.Series(D["rm"].astype(np.float64))
            sd = rm.rolling(250, min_periods=20).std().bfill()
            x = np.repeat(np.clip((rm / sd).to_numpy(), -5, 5)[:, None], D["e"].shape[1], 1)
        elif ch in ("ve", "vr"):                          # own-volatility scaling: trailing 63-session sd ending at row t
            a = pd.DataFrame(D[ch[1]].astype(np.float64))
            sd = a.rolling(63, min_periods=20).std().to_numpy()
            with np.errstate(all="ignore"):
                x = np.clip(a.to_numpy() / sd, -5, 5)
        elif ch == "miss":                                # 1 where the name's residual return is missing
            x = (~np.isfinite(D["e"])).astype(np.float64)
        elif ch == "ae":
            x = _xrank(np.abs(D["e"].astype(np.float64))) * np.sqrt(12)
        elif ch == "vol":
            from harness import load_extra
            F = load_extra("finra")
            tv = F["total"].astype(np.float64)
            lv = pd.DataFrame(np.log(np.where(tv > 0, tv, np.nan)))
            ab = (lv - lv.rolling(60, min_periods=40).mean()).to_numpy()
            x = _xrank(ab) * np.sqrt(12)
        else:
            raise ValueError(ch)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        out.append(x.astype(np.float32))
    X = np.stack(out, 2)                                  # (T, N, C)
    _C[key] = X
    return X


def _static(D, kind):
    key = ("st", id(D["e"]), kind)
    if key in _C:
        return _C[key]
    parts = []
    if kind in ("Z",):
        parts.append(np.nan_to_num(np.clip(D["Z"].astype(np.float32), -4, 4) / 2))
    if kind in ("D27", "DC"):
        import importlib.util
        sp = importlib.util.spec_from_file_location("d_model", os.path.join(TREE, "D_ensembles", "model.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        parts.append(m._features(D) * 2)                  # ranks in [-1, 1]
    if kind in ("C32", "DC"):
        import importlib.util
        sp = importlib.util.spec_from_file_location("c_model", os.path.join(TREE, "C_features", "model.py"))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        parts.append(m._design(D)[0] / np.sqrt(3))        # c's ranks are scaled to sd 1 -> [-1, 1]
    X = np.concatenate(parts, 2).astype(np.float32)
    _C[key] = X
    return X


def _target(D, h, te):
    if h == 5:
        return D["y5"].astype(np.float64)
    e = D["e"].astype(np.float64)
    cs, nanc = np.cumsum(np.nan_to_num(e), 0), np.cumsum(np.isnan(e), 0)
    y = np.full(e.shape, np.nan)
    t = np.arange(0, min(te, te + 5 - h) + 1)
    t = t[t + 1 + h < len(e)]
    y[t] = np.where((nanc[t + 1 + h] - nanc[t + 1]) > 0, np.nan, cs[t + 1 + h] - cs[t + 1])
    return y


class TCN(nn.Module):
    def __init__(self, C, d, dil=(1, 2, 4, 8, 16), dropout=0.1):
        super().__init__()
        self.inp = nn.Conv1d(C, d, 1)
        self.convs = nn.ModuleList([nn.Conv1d(d, d, 3, dilation=k) for k in dil])
        self.dil = dil
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(2 * d, d)

    def forward(self, x):                                  # (n, L, C)
        h = self.inp(x.transpose(1, 2))
        for k, cv in zip(self.dil, self.convs):
            h = h + self.drop(torch.relu(cv(nn.functional.pad(h, (2 * k, 0)))))      # causal
        return self.out(torch.cat([h[..., -1], h.mean(-1)], -1))


class TFM(nn.Module):
    def __init__(self, C, L, d, p=5, layers=2, dropout=0.1):
        super().__init__()
        self.p = p
        self.emb = nn.Linear(C * p, d)
        self.pos = nn.Parameter(torch.zeros(1, L // p, d))
        layer = nn.TransformerEncoderLayer(d, 4, 2 * d, dropout=dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, layers)
        self.out = nn.Linear(2 * d, d)

    def forward(self, x):
        n, L, C = x.shape
        h = self.emb(x.reshape(n, L // self.p, self.p * C)) + self.pos
        h = self.enc(h)
        return self.out(torch.cat([h[:, -1], h.mean(1)], -1))


class RNN(nn.Module):
    def __init__(self, kind, C, d):
        super().__init__()
        self.rnn = (nn.GRU if kind == "gru" else nn.LSTM)(C, d, batch_first=True)

    def forward(self, x):
        o, _ = self.rnn(x)
        return o[:, -1]


class Net(nn.Module):
    def __init__(self, c, C, Fs):
        super().__init__()
        d, p = c["d"], c["dropout"]
        self.enc = None
        if c["enc"] in ("gru", "lstm"):
            self.enc = RNN(c["enc"], C, d)
        elif c["enc"] == "tcn":
            self.enc = TCN(C, d, dropout=p)
        elif c["enc"] == "tfm":
            self.enc = TFM(C, c["L"], d, dropout=p)
        self.st = nn.Sequential(nn.Linear(Fs, d), nn.GELU(), nn.Dropout(p), nn.Linear(d, d)) if Fs else None
        k = (self.enc is not None) + (self.st is not None)
        self.head = nn.Sequential(nn.LayerNorm(k * d), nn.Linear(k * d, d), nn.GELU(), nn.Dropout(p),
                                  nn.Linear(d, len(c["horizons"])))

    def forward(self, xs, xq):
        h = []
        if self.st is not None:
            h.append(self.st(xs))
        if self.enc is not None:
            h.append(self.enc(xq))
        return self.head(torch.cat(h, -1))


def _loss(out, y, g, G, kind):
    """out, y: (n,) for one head; g: (n,) date-group ids 0..G-1. Targets are per-date standardised ranks."""
    if kind == "mse":
        return ((out - y) ** 2).mean()
    cnt = torch.zeros(G, device=out.device).index_add_(0, g, torch.ones_like(out))
    if kind in ("ic", "mse+ic"):
        mo = torch.zeros(G, device=out.device).index_add_(0, g, out) / cnt
        oc = out - mo[g]
        so = torch.sqrt(torch.zeros(G, device=out.device).index_add_(0, g, oc * oc) / cnt + 1e-8)
        cov = torch.zeros(G, device=out.device).index_add_(0, g, (oc / so[g]) * y) / cnt
        l = -cov.mean()                                    # y has mean 0, sd 1 per date: cov = Pearson correlation
        return l + (((out - y) ** 2).mean() * 0.1 if kind == "mse+ic" else 0)
    if kind == "listnet":
        # softmax over each date's names: cross-entropy between target and output top-one distributions
        tz = y * 2.0
        tmax, omax = tz.detach().max().expand(G), out.detach().max().expand(G)   # a shared shift: softmax per date is unchanged
        te, oe = torch.exp(tz - tmax[g]), torch.exp(out - omax[g])
        ts = torch.zeros(G, device=out.device).index_add_(0, g, te)
        os_ = torch.zeros(G, device=out.device).index_add_(0, g, oe)
        pt = te / ts[g]
        logpo = out - omax[g] - torch.log(os_[g])
        return -(torch.zeros(G, device=out.device).index_add_(0, g, pt * logpo)).mean()
    raise ValueError(kind)


def make(**over):
    c = dict(DEFAULT, **over)
    c["horizons"] = tuple(c["horizons"])

    def _rows_data(D, rows, Xs, Ys):
        """Flat arrays for (row, name) pairs: static index, targets (per-date standardised ranks), group ids."""
        ok = D["elig"][rows] & np.isfinite(D["Z"][rows]).all(-1)
        if Ys is not None:
            ok &= np.isfinite(Ys[0][rows])
            keep = ok.sum(1) >= 50
            rows, ok = rows[keep], ok[keep]
        ti, ni = np.nonzero(ok)
        T = rows[ti]
        out = dict(t=T, n=ni, g=ti, rows=rows)
        if Ys is not None:
            ys = []
            for Y in Ys:
                a = Y[rows].copy()
                a[~ok] = np.nan
                r = _xrank(a) * np.sqrt(12)
                ys.append(np.nan_to_num(r[ti, ni]).astype(np.float32))
            out["y"] = np.stack(ys, 1)
        return out

    def _batch(Xq, Xs, t, n, L, dev):
        """Xq: device tensor (N, T+L-1, C) zero-padded at the start; Xs: device tensor (T, N, F)."""
        tt, nn_ = torch.from_numpy(t).to(dev), torch.from_numpy(n).to(dev)
        w = Xq.unfold(1, L, 1)                                         # (N, T, C, L): window ending at row t
        q = w[nn_, tt].transpose(1, 2)
        if c["inorm"]:                                                 # instance norm of the e/r channels over the window
            k = [i for i, ch in enumerate(c["chans"]) if ch in ("e", "r")]
            v = q[..., k]
            if c["inorm"] == "center":
                v = v - v.mean(1, keepdim=True)
            q = torch.cat([v / (v.std(1, keepdim=True) + 1e-3), q[..., [i for i in range(q.shape[2]) if i not in k]]], -1)
        return Xs[tt, nn_], q

    def _predict(net, Xq, Xs, data, L, dev):
        net.eval()
        outs = []
        with torch.no_grad():
            for s in range(0, len(data["t"]), 8192):
                xs, xq = _batch(Xq, Xs, data["t"][s:s + 8192], data["n"][s:s + 8192], L, dev)
                outs.append(net(xs, xq)[:, 0].float().cpu().numpy())
        net.train()
        return np.concatenate(outs) if outs else np.zeros(0)

    def _ic(p, data):
        y = data["y"][:, 0]
        df = pd.DataFrame({"p": p, "y": y, "g": data["g"]})
        return float(df.groupby("g")[["p", "y"]].apply(lambda d: d["p"].corr(d["y"], method="spearman")).mean())

    def _train(D, Xq, Xs, tr, va, seed, epochs):
        dev = torch.device(c["device"])
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        net = Net(c, Xq.shape[2], Xs.shape[2] if Xs is not None else 0).to(dev)
        opt = torch.optim.AdamW(net.parameters(), lr=c["lr"], weight_decay=c["wd"])
        G = len(tr["rows"])
        bd = c["batch_dates"]
        nb = int(np.ceil(G / bd))
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=c["lr"], total_steps=epochs * nb, pct_start=0.2)
        order = np.argsort(tr["g"], kind="stable")
        starts = np.searchsorted(tr["g"][order], np.arange(G + 1))
        hw = torch.tensor([1.0] + [c["hw"]] * (len(c["horizons"]) - 1), device=dev)
        best, best_state, best_ep, hist = -9.0, None, epochs, []
        for ep in range(epochs):
            perm = rng.permutation(G)
            for s in range(0, G, bd):
                gs = perm[s:s + bd]
                sel = np.concatenate([order[starts[k]:starts[k + 1]] for k in gs])
                gl = np.concatenate([np.full(starts[k + 1] - starts[k], i) for i, k in enumerate(gs)])
                xs, xq = _batch(Xq, Xs, tr["t"][sel], tr["n"][sel], c["L"], dev)
                y = torch.from_numpy(tr["y"][sel]).to(dev)
                g = torch.from_numpy(gl).to(dev)
                out = net(xs, xq)
                loss = sum(hw[k] * _loss(out[:, k], y[:, k], g, len(gs), c["loss"]) for k in range(out.shape[1]))
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 1.0)
                opt.step()
                sched.step()
            if va is not None:
                ic = _ic(_predict(net, Xq, Xs, va, c["L"], dev), va)
                hist.append(ic)
                if ic > best:
                    best, best_ep = ic, ep + 1
                    best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        if best_state is not None:
            net.load_state_dict(best_state)
        net.hist = hist
        net.best_ep = best_ep
        return net

    def fit_predict(D, train_end, pred_rows, seed):
        torch.set_num_threads(3)
        dev = torch.device(c["device"])
        q = _seq_channels(D, c)
        L = c["L"]
        Xq = torch.from_numpy(np.concatenate([np.zeros((L - 1,) + q.shape[1:], np.float32), q], 0).transpose(1, 0, 2).copy()).to(dev)
        Xs = _static(D, c["static"]) if c["static"] else np.zeros(D["e"].shape + (0,), np.float32)
        Xs = torch.from_numpy(Xs).to(dev)
        S = D["S"]
        ar = np.arange(len(S))
        base = (ar <= train_end) & (ar >= 60)
        tr_rows = np.where(base & ((S.weekday == 3) | c["all_days"]))[0]
        Ys = [_target(D, h, train_end) for h in c["horizons"]]
        rows = np.asarray(pred_rows)
        pdat = _rows_data(D, rows, Xs, None)
        preds = []
        for i in range(c["n_ens"]):
            sd = seed * 100 + i
            if c["es_weeks"]:
                thu = np.where(base & (S.weekday == 3))[0]
                cut = thu[-c["es_weeks"]]
                a = tr_rows[tr_rows < cut - 8]
                tr, va = _rows_data(D, a, Xs, Ys), _rows_data(D, thu[thu >= cut], Xs, Ys)
                net = _train(D, Xq, Xs, tr, va, sd, c["epochs"])
                if c["refit"]:
                    net = _train(D, Xq, Xs, _rows_data(D, tr_rows, Xs, Ys), None, sd, max(net.best_ep, 2))
            else:
                net = _train(D, Xq, Xs, _rows_data(D, tr_rows, Xs, Ys), None, sd, c["epochs"])
            p = _predict(net, Xq, Xs, pdat, c["L"], torch.device(c["device"]))
            out = np.full((len(rows), D["y5"].shape[1]), np.nan)
            out[pdat["g"], pdat["n"]] = p
            preds.append(pd.DataFrame(out).rank(axis=1, pct=True).to_numpy())
            fit_predict.log.append(dict(train_end=int(train_end), seed=sd, best_ep=getattr(net, "best_ep", None),
                                        hist=[round(x, 4) for x in getattr(net, "hist", [])]))
        with np.errstate(all="ignore"):
            return np.nanmean(preds, 0)

    fit_predict.config = c
    fit_predict.log = []
    return fit_predict
