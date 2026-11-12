"""Branch E candidates. Each factory returns a fit_predict(D, train_end, pred_rows, seed)."""
import numpy as np
import torch

from lib import zstates, weekly_stats, wsolve, apply

torch.set_num_threads(2)


def ew_ridge(halflife=52, lam=0.1):
    """Ridge with exponentially decaying weights on past weeks (halflife in weeks)."""
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        w = 0.5 ** ((tr[-1] - tr) / 5.0 / halflife)
        return apply(D, rows, np.tile(wsolve(A, c, w, lam), (len(rows), 1)))
    return f


def rolling_ridge(window=104, lam=0.1):
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        w = np.zeros(len(tr)); w[-window:] = 1
        return apply(D, rows, np.tile(wsolve(A, c, w, lam), (len(rows), 1)))
    return f


def interaction_ridge(cols=(2, 3, 6), lam=0.1, lam_int=None):
    """Coefficients linear in the state: b(s) = B0 + B1 s. Pooled ridge on Z and Z x state."""
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        Zs, _ = zstates(D, te)
        s = np.c_[np.ones(len(Zs)), Zs[:, list(cols)]]
        st = s[tr]                                     # (W, q)
        q, k = st.shape[1], A.shape[1]
        G = np.einsum("wa,wb,wij->aibj", st, st, A).reshape(q * k, q * k) / len(tr)
        h = np.einsum("wa,wi->ai", st, c).reshape(q * k) / len(tr)
        pen = np.r_[np.full(k, lam), np.full((q - 1) * k, lam if lam_int is None else lam_int)]
        B = np.linalg.solve(G + np.diag(pen), h).reshape(q, k)
        return apply(D, rows, np.nan_to_num(s[rows]) @ B)
    return f


def panic_rule(lam=0.1, vol_q=0.67, off=(0,), flip=False, base="ridge", halflife=None):
    """Base ridge; in a panic (market one-year return < 0 and 21-day volatility above its train quantile) the
    momentum coefficient is set to zero (or flipped)."""
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        w = np.ones(len(tr)) if halflife is None else 0.5 ** ((tr[-1] - tr) / 5.0 / halflife)
        b = wsolve(A, c, w, lam)
        _, S = zstates(D, te)
        thr = np.nanquantile(S[:te + 1, 3], vol_q)
        B = np.tile(b, (len(rows), 1))
        panic = (S[rows, 2] < 0) & (S[rows, 3] > thr)
        for j in off:
            B[panic, j] = -B[panic, j] if flip else 0.0
        return apply(D, rows, B)
    return f


def kernel_ridge(cols=(2, 3, 6), h=1.0, lam=0.1, halflife=None, shrink=0.0, panic_off=(), vol_q=0.67):
    """Weight past weeks by the similarity of their market state to today's (Gaussian kernel, bandwidth h in
    train standard deviations). shrink mixes in uniform weights."""
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        Zs, _ = zstates(D, te)
        st = Zs[tr][:, list(cols)]
        ok = np.isfinite(st).all(1)
        tr, A, c, st = tr[ok], A[ok], c[ok], st[ok]
        B = []
        for t in rows:
            d2 = ((st - Zs[t, list(cols)]) ** 2).sum(1)
            w = np.exp(-d2 / (2 * h * h * len(cols)))
            w = w / w.sum() * (1 - shrink) + shrink / len(w)
            if halflife is not None:
                w = w * 0.5 ** ((tr[-1] - tr) / 5.0 / halflife)
            B.append(wsolve(A, c, w, lam))
        B = np.array(B)
        if panic_off:
            _, S = zstates(D, te)
            panic = (S[rows, 2] < 0) & (S[rows, 3] > np.nanquantile(S[:te + 1, 3], vol_q))
            for j in panic_off:
                B[panic, j] = 0.0
        return apply(D, rows, B)
    return f


def exp_weights(eta=20.0, signed=True, halflife=None):
    """Online exponential-weights (Hedge) over single-characteristic experts (each sign is an expert).
    Gain of an expert in a week = its rank IC. Weights are frozen at train_end."""
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        g = np.c_[ic, -ic] if signed else ic
        d = np.ones(len(tr)) if halflife is None else 0.5 ** ((tr[-1] - tr) / 5.0 / halflife)
        L = (g * d[:, None]).sum(0)
        w = np.exp(eta * (L - L.max()) / np.sqrt(len(tr))); w /= w.sum()
        b = w[:5] - w[5:] if signed else w
        return apply(D, rows, np.tile(b, (len(rows), 1)))
    return f


def ic_timing(window=52, mode="t"):
    """Factor timing: weight of each characteristic = its trailing mean IC (or t-statistic) over the last
    `window` weeks ending at train_end."""
    def f(D, te, rows, seed):
        tr, A, c, ic = weekly_stats(D, te)
        x = ic[-window:]
        b = x.mean(0) / x.std(0) if mode == "t" else x.mean(0)
        if mode == "sign":
            b = np.sign(x.mean(0))
        return apply(D, rows, np.tile(b, (len(rows), 1)))
    return f


def hypernet(cols=(0, 1, 2, 3, 4, 5, 6), hidden=8, epochs=300, lr=0.01, wd=1e-2, lam=0.1, experts=0):
    """Small hypernetwork: state -> the five characteristic weights. Trained on the weekly squared loss written
    through the sufficient statistics: loss_w = 0.5 b'A_w b - b'c_w. experts>0 gives a mixture of experts instead
    (softmax gate over `experts` learned weight vectors)."""
    def f(D, te, rows, seed):
        torch.manual_seed(seed)
        tr, A, c, ic = weekly_stats(D, te)
        Zs, _ = zstates(D, te)
        st = Zs[tr][:, list(cols)]
        ok = np.isfinite(st).all(1)
        A_, c_, s_ = (torch.tensor(a[ok], dtype=torch.float32) for a in (A, c, st))
        k = A.shape[1]
        if experts:
            gate = torch.nn.Linear(len(cols), experts)
            W = torch.nn.Parameter(0.01 * torch.randn(experts, k))
            params = list(gate.parameters()) + [W]
            net = lambda s: torch.softmax(gate(s), -1) @ W
        else:
            mlp = torch.nn.Sequential(torch.nn.Linear(len(cols), hidden), torch.nn.Tanh(), torch.nn.Linear(hidden, k))
            params = list(mlp.parameters())
            net = mlp
        opt = torch.optim.AdamW(params, lr=lr, weight_decay=wd)
        for _ in range(epochs):
            b = net(s_)
            loss = (0.5 * torch.einsum("wi,wij,wj->w", b, A_, b) - (b * c_).sum(1) + 0.5 * lam * (b * b).sum(1)).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        with torch.no_grad():
            B = net(torch.tensor(np.nan_to_num(Zs[rows][:, list(cols)]), dtype=torch.float32)).numpy().astype(np.float64)
        return apply(D, rows, B)
    return f
