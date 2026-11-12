"""Branch M3: conditional autoencoder (Gu, Kelly and Xiu 2021, J. Econometrics), adapted to weekly hedged returns.

  beta network : ranked characteristics Z_{i,t} -> K betas (CA0: linear; CA1: one hidden layer; CA2: two)
  factor network: characteristic-managed portfolios x_{t+1} = (Z_t'Z_t)^-1 Z_t' r_{t+1} -> K factors (linear), as in the paper
  alpha head   : optional Z_{i,t} -> alpha_{i,t} (linear or small net), penalised
  loss         : mean squared error of r_{i,t+1} against alpha_{i,t} + beta_{i,t} . f_{t+1}, plus L1 on weights
  prediction   : alpha_{i,t} + beta_{i,t} . lambda, lambda = mean of training-period factors

Target r: the 5-session hedged return y5 of Thursday rows <= train_end, cross-sectionally demeaned, scaled by its
cross-sectional std and clipped at +-3 (C_features/lib.target). Non-overlapping weekly cross-sections (Thursdays).
Early stopping on the reconstruction loss of the last 15% of training weeks (chronological), never on validation-year IC.
Characteristics: "Z5" = the harness's 5 characteristics, ranked; "C32" = branch C's 24 price features + 8 market-state
interactions, ranked (read-only import of research/tree/C_features/lib.py).
"""
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "C_features"))
import lib as clib  # noqa: E402  (read-only)

torch.set_num_threads(3)

C_FEATS = clib.GROUPS["all"]
C_INTER = [("rev5", "mvol"), ("erev5", "mvol"), ("rev21", "mvol"), ("erev21", "mvol"), ("rev1", "mvol"),
           ("mom252", "mvol"), ("rev5", "mret"), ("mom252", "mret")]
_XC = {}


def chars(D, which):
    key = (id(D["r"]), which)
    if key in _XC:
        return _XC[key]
    if which == "C32":
        X, ok = clib.design(D, C_FEATS, "rank", C_INTER)
    else:
        cols = [clib.xs(D["Z"][:, :, k].astype(np.float64), D["elig"], "rank") for k in range(D["Z"].shape[2])]
        X = np.stack(cols, 2)
        ok = D["elig"] & np.isfinite(X).all(2)
        X = np.where(np.isfinite(X), X, 0.0).astype(np.float32)
    _XC[key] = (X, ok)
    return _XC[key]


class CAE(torch.nn.Module):
    def __init__(self, P, K, hidden, alpha, alpha_hidden):
        super().__init__()
        layers, d = [], P
        for h in hidden:
            layers += [torch.nn.Linear(d, h), torch.nn.BatchNorm1d(h), torch.nn.ReLU()]
            d = h
        layers += [torch.nn.Linear(d, K)]
        self.beta = torch.nn.Sequential(*layers)
        self.fac = torch.nn.Linear(P + 1, K, bias=False)
        self.alpha = None
        if alpha:
            if alpha_hidden:
                self.alpha = torch.nn.Sequential(torch.nn.Linear(P, alpha_hidden), torch.nn.ReLU(),
                                                 torch.nn.Linear(alpha_hidden, 1))
            else:
                self.alpha = torch.nn.Linear(P, 1)

    def forward(self, Z, m, x):
        # Z: (B, N, P), m: (B, N) bool, x: (B, P+1) managed portfolios of the same weeks
        B, N, P = Z.shape
        flat = Z[m]
        b = self.beta(flat)                                             # (n, K)
        wk = torch.arange(B).unsqueeze(1).expand(B, N)[m]
        f = self.fac(x)                                                  # (B, K)
        out = (b * f[wk]).sum(1)
        a = self.alpha(flat).squeeze(1) if self.alpha is not None else None
        if a is not None:
            out = out + a
        return out, f, a

    @torch.no_grad()
    def predict(self, Zf, lam):
        p = self.beta(Zf) @ lam
        if self.alpha is not None:
            p = p + self.alpha(Zf).squeeze(1)
        return p


def managed(Z, y, m):
    """x_t = (Z'Z)^-1 Z'r over eligible names, with a constant column (equal-weight portfolio)."""
    W = Z.shape[0]
    xs = np.zeros((W, Z.shape[2] + 1), np.float32)
    for w in range(W):
        z = np.concatenate([np.ones((m[w].sum(), 1)), Z[w][m[w]]], 1).astype(np.float64)
        r = y[w][m[w]].astype(np.float64)
        A = z.T @ z / len(r)
        xs[w] = np.linalg.solve(A + 1e-4 * np.eye(len(A)), z.T @ r / len(r))
    return xs


def make(chars_set="Z5", K=3, hidden=(), alpha=False, alpha_hidden=0, alpha_l2=1e-3, l1=1e-4, lr=3e-3,
         epochs=200, patience=20, batch=16, n_ens=1, val_frac=0.15, start_year=None):
    cache = {}

    def fit_predict(D, te, rows, seed):
        X, ok = chars(D, chars_set)
        S = D["S"]
        k = (id(D["r"]), te)
        if k not in cache:
            y = clib.target(D, te)
            tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
            if start_year:
                tr = tr[S[tr].year >= start_year]
            m = ok[tr] & np.isfinite(y[tr])
            keep = m.sum(1) >= 50
            tr, m = tr[keep], m[keep]
            cache[k] = (tr, m, np.where(m, y[tr], 0.0).astype(np.float32))
        tr, m, yt = cache[k]
        Zt = X[tr]
        x = managed(Zt, yt, m)
        nv = max(int(len(tr) * val_frac), 10)
        itr, iva = np.arange(len(tr) - nv), np.arange(len(tr) - nv, len(tr))
        Zt_, m_, y_, x_ = (torch.from_numpy(a) for a in (Zt, m, yt, x))
        Zp = torch.from_numpy(X[rows])
        preds = []
        for e in range(n_ens):
            torch.manual_seed(1000 * seed + e)
            rng = np.random.default_rng(1000 * seed + e)
            net = CAE(X.shape[2], K, hidden, alpha, alpha_hidden)
            opt = torch.optim.Adam(net.parameters(), lr=lr)
            best, best_state, bad = np.inf, None, 0

            def loss_on(idx, train):
                out, f, a = net(Zt_[idx], m_[idx], x_[idx])
                tgt = y_[idx][m_[idx]]
                L = ((tgt - out) ** 2).mean()
                if train:
                    L = L + l1 * sum(p.abs().sum() for n_, p in net.named_parameters() if "weight" in n_)
                    if a is not None:
                        L = L + alpha_l2 * (a ** 2).mean()
                return L

            for ep in range(epochs):
                net.train()
                perm = rng.permutation(itr)
                for i in range(0, len(perm), batch):
                    opt.zero_grad()
                    loss_on(torch.from_numpy(perm[i:i + batch]), True).backward()
                    opt.step()
                net.eval()
                with torch.no_grad():
                    v = float(loss_on(torch.from_numpy(iva), False))
                if v < best - 1e-6:
                    best, bad = v, 0
                    best_state = {kk: vv.clone() for kk, vv in net.state_dict().items()}
                else:
                    bad += 1
                    if bad >= patience:
                        break
            net.load_state_dict(best_state)
            net.eval()
            with torch.no_grad():
                lam = net.fac(x_).mean(0)                                # mean of training-period factors
                p = net.predict(Zp.reshape(-1, X.shape[2]), lam).reshape(len(rows), -1).numpy()
            # rank within row so ensemble members are averaged on one scale
            p = np.where(ok[rows], p, np.nan)
            import pandas as pd
            preds.append(pd.DataFrame(p).rank(axis=1, pct=True).to_numpy())
        with np.errstate(all="ignore"):
            return np.nanmean(preds, 0)

    return fit_predict


# best configuration (updated as results arrive)
BEST = dict(chars_set="C32", K=3, hidden=(32, 16))  # ca2_c32_k3
fit_predict = make(**BEST)
