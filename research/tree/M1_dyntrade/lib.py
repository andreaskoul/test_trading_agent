"""Branch M1 (dynamic trading with costs, Garleanu and Pedersen 2013): portfolio construction rules on fixed scores.

Nothing here fits a predictor. Inputs are weekly score panels (rows = sessions, NaN off the scored Thursdays):
* MASTER 5-day scores, D["master_h5_ref"];
* branch D's HGB on 3/5/10/20-session targets, walk-forward 2013-2019, copied once from
  research/tree/D_ensembles/pred_hgb_multihorizon.npy to base_hgb_multihorizon.npy (X2's base c1).

Book (simulate): weights w_t over names, long side +0.5, short side -0.5 (gross 1.0), entered at close t+1 and held
5 sessions; return w_t . y5_t (y5 is already the beta-hedged residual return, as in harness.decile_net); cost
5 bp x sum|w_t - w_{t-1}|. Names leave the book (traded out, cost charged) when they are not eligible, have no score
or no y5 at t (the harness's own mask).

Garleanu-Pedersen (GP), single signal, weekly periods, discount ~ 0:
    x_t = (1 - tau) x_{t-1} + tau * g * aim_t,   aim_t = Markowitz direction (gross 1),   then sides rescaled to 0.5
    tau = a / lambda = (-r + sqrt(r^2 + 4 r)) / 2,  r = gamma / lambda
    g   = 1 / (1 + phi * a / gamma) = 1 / (1 + phi * tau / r),   phi = 1 - (week-on-week rank autocorrelation of scores)
gamma is the risk aversion that makes the GP book's gross 1.0; lambda (quadratic cost Lambda = lambda * Sigma) is set
so that the quadratic cost equals the true linear cost (5 bp x |trade|) on a reference set of trades:
    cal="ref" (principal, declared before any GP outcome was seen): the trades of the tau = 1 book (the aim itself);
    cal="fp": the GP book's own trades (a fixed point; it collapses toward tau ~ 0 when the IC is weak, because the
    implied quadratic cost per unit grows as trades shrink).
r is then a fixed point in tau (through g and the book's gross), solved each week on the PAST scored weeks only
(last 52), with
    mu_i = IC_hat * sigma_i * z_i  (Grinold), z = normal score of the cross-sectional rank, sigma_i = 5-day residual
    vol from the past 250 sessions of D["e"]; IC_hat = realised weekly rank IC over weeks whose y5 ended before t,
    shrunk to a prior of 0.02 with weight 26 weeks.
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.covariance import LedoitWolf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402

COST = harness.COST
IC_PRIOR, IC_N0, CAL_WEEKS, VOL_WIN = 0.02, 26, 52, 250


def val_rows(D, scores):
    """Validation Thursdays 2013-2019 on which the harness scores a book (>= 50 names with score, y5, eligibility)."""
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    return np.array([t for t in rows if mask(scores, D, t).sum() >= 50])


def mask(scores, D, t):
    return np.isfinite(scores[t]) & np.isfinite(D["y5"][t]) & D["elig"][t]


def zscore(s, m):
    z = np.zeros(len(s))
    pct = pd.Series(s[m]).rank(pct=True).to_numpy()
    z[m] = norm.ppf(np.clip(pct - 0.5 / m.sum(), 1e-4, 1 - 1e-4))
    return z


def sides(w):
    """Rescale the long side to +0.5 and the short side to -0.5."""
    w = w.copy()
    p, n = w[w > 0].sum(), -w[w < 0].sum()
    if p > 0:
        w[w > 0] *= 0.5 / p
    if n > 0:
        w[w < 0] *= 0.5 / n
    return w


def resid_vol(D, t):
    e = D["e"][max(0, t - VOL_WIN + 1):t + 1].astype(np.float64)
    v = np.nanstd(e, 0) * np.sqrt(5)
    ok = np.isfinite(v) & (np.isfinite(e).sum(0) >= 150)
    v[~ok] = np.nanmedian(v[ok])
    return v


# ---------------------------------------------------------------- aims (gross 1.0, sides 0.5), each from data <= t
def aim_decile(s, m):
    w = np.zeros(len(s))
    idx = np.where(m)[0]
    pct = pd.Series(s[m]).rank(pct=True).to_numpy()
    top, bot = idx[pct > 0.9], idx[pct <= 0.1]
    w[top], w[bot] = 0.5 / len(top), -0.5 / len(bot)
    return w


def aim_mv_diag(s, m, sig):
    v = np.where(m, zscore(s, m) / sig, 0.0)          # Sigma^-1 mu with mu = IC sigma z, Sigma = diag(sigma^2)
    return sides(v), v


def aim_mv_lw(s, m, sig, D, t):
    idx = np.where(m)[0]
    e = D["e"][max(0, t - VOL_WIN + 1):t + 1][:, idx].astype(np.float64)
    e = np.where(np.isfinite(e), e, 0.0)
    C = LedoitWolf().fit(e).covariance_ * 5
    mu = zscore(s, m)[idx] * sig[idx]
    v = np.zeros(len(s))
    v[idx] = np.linalg.solve(C, mu)
    return sides(v)


# ---------------------------------------------------------------- simulator
def simulate(W, D, rows):
    """W: (len(rows), n) weights. Returns weekly net, gross, cost, one-way turnover (sum|dw|/2)."""
    prev = np.zeros(W.shape[1])
    net, gross, cost, turn = [], [], [], []
    for j, t in enumerate(rows):
        w = W[j]
        y = np.nan_to_num(D["y5"][t])
        g = float(w @ y)
        dw = float(np.abs(w - prev).sum())
        gross.append(g), cost.append(COST * dw), turn.append(dw / 2), net.append(g - COST * dw)
        prev = w
    return {k: np.array(v) for k, v in (("net", net), ("gross", gross), ("cost", cost), ("turn", turn))}


def summary(sim, skip_first=True):
    s = slice(1, None) if skip_first else slice(None)
    n = sim["net"][s]
    return {"net_pct_yr": 52 * n.mean() * 100, "net_sharpe": n.mean() / n.std(ddof=1) * np.sqrt(52),
            "gross_pct_yr": 52 * sim["gross"][s].mean() * 100, "cost_pct_yr": 52 * sim["cost"][s].mean() * 100,
            "turnover_wk": sim["turn"][s].mean()}


# ---------------------------------------------------------------- signal statistics, past only
def realised_ic(scores, D, rows):
    return harness.weekly_ic(scores, D, rows)


def autocorr(scores, D, rows):
    """Spearman of each scored week's scores with the previous scored week's, names scored in both."""
    out = [np.nan]
    for a, b in zip(rows[:-1], rows[1:]):
        m = np.isfinite(scores[a]) & np.isfinite(scores[b]) & D["elig"][b]
        out.append(pd.Series(scores[a][m]).corr(pd.Series(scores[b][m]), method="spearman") if m.sum() > 50 else np.nan)
    return np.array(out)


def gp_rate(us, vsum, sig2, phi, cal="ref", iters=40):
    """Fixed point for the GP trade rate on past weeks. us: unit-gross Markowitz directions (weeks x n); vsum: mean
    sum|Sigma^-1 mu| (mu already scaled by IC_hat); sig2: per-name 5-day residual variance (weeks x n); phi: decay."""
    tau, r = 0.3, 0.1
    b = len(us) // 4                                           # burn-in of the recursion
    for _ in range(iters):
        g = 1.0 / (1.0 + phi * tau / max(r, 1e-9))
        y, ys = np.zeros(us.shape[1]), []
        for u in us:
            y = (1 - tau) * y + tau * g * u
            ys.append(y)
        ys = np.array(ys)
        G = np.abs(ys[b:]).sum(1).mean()                       # gross of the unscaled GP book; gamma makes it 1
        dx = np.diff(ys / G, axis=0)[b:]
        if cal == "ref":                                       # lambda matched on the trades of the tau = 1 book
            dx = np.diff(us, axis=0)
            q = (sig2[1:] * dx ** 2).sum(1).mean() / np.abs(dx).sum(1).mean()
        else:                                                  # "fp": matched on the GP book's own trades
            q = (sig2[1:][b:] * dx ** 2).sum(1).mean() / np.abs(dx).sum(1).mean()   # E dx'Sigma dx / E sum|dx|
        r = vsum * G * q / (2 * COST)                          # gamma / lambda
        new = (-r + np.sqrt(r * r + 4 * r)) / 2
        done = abs(new - tau) < 1e-4
        tau = new if done else 0.5 * tau + 0.5 * new
        if done:
            break
    g = 1.0 / (1.0 + phi * tau / max(r, 1e-9))
    return float(min(max(tau, 0.01), 1.0)), float(g), float(r)


def gp_params(scores, D, rows, cal="ref", cache={}):
    """Per-week (tau, g, r, ic_hat, phi), each from rows <= t only. Cached per score panel."""
    key = (id(scores), cal)
    if key in cache:
        return cache[key]
    ic = realised_ic(scores, D, rows)
    ac = autocorr(scores, D, rows)
    U, VS, S2 = [], [], []
    for t in rows:
        m = mask(scores, D, t)
        sig = resid_vol(D, t)
        u, v = aim_mv_diag(scores[t], m, sig)
        U.append(u), VS.append(np.abs(v).sum()), S2.append(sig ** 2)
    U, VS, S2 = np.array(U), np.array(VS), np.array(S2)
    out = []
    for j, t in enumerate(rows):
        known = [k for k in range(j) if rows[k] + 6 <= t and np.isfinite(ic[k])]      # y5 of week k has ended by t
        ich = (np.sum(ic[known]) + IC_N0 * IC_PRIOR) / (len(known) + IC_N0)
        acs = ac[1:j + 1]
        acs = acs[np.isfinite(acs)]
        if len(acs) < 1 or j < 4:
            out.append((1.0, 1.0, np.nan, ich, np.nan))      # first weeks of 2013: no past to calibrate on
            continue
        phi = max(1 - acs.mean(), 1e-3)
        lo = max(0, j - CAL_WEEKS + 1)
        tau, g, r = gp_rate(U[lo:j + 1], max(ich, 1e-4) * VS[lo:j + 1].mean(), S2[lo:j + 1], phi, cal)
        out.append((tau, g, r, ich, phi))
    cache[key] = np.array(out)
    return cache[key]


# ---------------------------------------------------------------- constructions
def build(kind, scores, D, rows, tau_mult=1.0, hl=1.0, band=0.1, cal="ref"):
    """Weekly weights (len(rows) x n) for one construction."""
    n = scores.shape[1]
    W = np.zeros((len(rows), n))
    prev = np.zeros(n)
    if kind.startswith("gp"):
        P = gp_params(scores, D, rows, cal)
    if kind == "ema":                                          # X2: smooth the cross-sectional rank, then deciles
        R = np.full((len(rows), n), np.nan)
        for j, t in enumerate(rows):
            R[j] = pd.Series(scores[t]).rank(pct=True).to_numpy() - 0.5
        Rs = ema(R, hl)
    top = bot = np.zeros(n, bool)
    for j, t in enumerate(rows):
        m = mask(scores, D, t)
        s = scores[t]
        if kind == "decile":
            w = aim_decile(s, m)
        elif kind == "ema":
            w = aim_decile(Rs[j], m & np.isfinite(Rs[j]))
        elif kind == "band":                                   # enter at the 10% tails, exit only past the 10+band% tails
            idx = np.where(m)[0]
            pct = np.zeros(n)
            pct[idx] = pd.Series(s[m]).rank(pct=True).to_numpy()
            top = m & ((pct > 0.9) | (top & (pct > 0.9 - band)))
            bot = m & ((pct <= 0.1) | (bot & (pct <= 0.1 + band)))
            w = np.zeros(n)
            w[top], w[bot] = 0.5 / top.sum(), -0.5 / bot.sum()
        elif kind == "mv_diag":
            w = aim_mv_diag(s, m, resid_vol(D, t))[0]
        else:
            if kind == "gp_decile":
                a = aim_decile(s, m)
            elif kind == "gp_mv_diag":
                a = aim_mv_diag(s, m, resid_vol(D, t))[0]
            elif kind == "gp_mv_lw":
                a = aim_mv_lw(s, m, resid_vol(D, t), D, t)
            tau, g = P[j, 0], P[j, 1]
            tau = min(1.0, tau * tau_mult)
            w = sides(np.where(m, (1 - tau) * prev + tau * g * a, 0.0))
        W[j] = w
        prev = w
    return W


def ema(R, hl):
    """X2's smoother (copied from research/tree/X2_costs/lib.py): exponentially weighted mean of each stock's past
    ranks, weights renormalised over weeks with a rank; uses rows <= j for row j."""
    w = 0.5 ** (1.0 / hl)
    out = np.full(R.shape, np.nan)
    num, den = np.zeros(R.shape[1]), np.zeros(R.shape[1])
    for j in range(len(R)):
        f = np.isfinite(R[j])
        num, den = w * num + np.where(f, R[j], 0.0), w * den + f
        out[j] = np.where(f, num / np.maximum(den, 1e-12), np.nan)
    return out


def ic_of(W_or_scores, D, rows):
    ic = harness.weekly_ic(W_or_scores, D, rows)
    return float(np.nanmean(ic))
