"""Branch Q6_trade (Layer 3, Amendment 8): trading less, judged under a square-root cost model. Development data only
(S&P 500, Thursdays 2013-2019); signals fixed (Q4's saved trees and IPCA scores, MASTER's frozen 5-day scores).

Book convention is M1's (M1_dyntrade/lib.py simulate): weights w_t chosen on Thursday t from data <= t, entered at the
next close, held 5 sessions, return w_t . y5_t (y5 = beta-hedged residual return; the implicit SPY hedge leg is not
charged, as in every earlier branch). Names leave the book when not eligible / unscored / without y5 (M1's mask). The
first scored week is dropped from every statistic.

COST MODEL (registered: half-spread + k sigma_i sqrt(|dw_i| AUM / ADV_i)), per name and week, as a fraction of AUM:

    cost_i = |dw_i| * ( HS + K * sigma_i * sqrt(|dw_i| * AUM / ADV_i) )

* HS = 2.3 bp: mean quoted half-spread of S&P 500 names one second before 15:59 ET (COST_STUDY.json, sp500.mean_bp).
* sigma_i: daily total-return volatility, past 60 sessions of D["r"] up to t (median of the cross-section if < 40).
* ADV_i: median consolidated daily dollar volume over the past 20 sessions up to t (fetch_dv.py: Yahoo split-adjusted
  close x volume, return-matched to the panel). FINRA `total` is off-exchange SHARE volume and the panel has no price
  level, so it cannot give dollars on its own; it is the fallback for names without a dollar volume (2 names, 2019
  IPOs CTVA/DOW): ADV_$ = FINRA shares x the day's cross-sectional median of (consolidated $ / FINRA share). Scale
  documented in the report: FINRA/consolidated share volume has median 0.22-0.25 by year (0.29-0.31 at the upper
  quartile, which is the unsplit names' level; names that split after a date read low by the split factor).
* K = 0.5 (a priori), the square-root coefficient on daily volatility. Calibration: JKMP (Jensen-Kelly-Malamud-Pedersen,
  RFS forthcoming, via L3_lit) charge 0.1% for a trade of 1% of daily dollar volume (Lambda = 0.2/V); for the typical
  stock of their universe (daily vol about 2%) a square-root law matching that point has K = 0.001 / (0.02 sqrt(0.01))
  = 0.5. Frazzini-Israel-Moskowitz (2012/2018, via L3_lit) estimate impact rising with the square root of the
  fraction of daily volume, average large-cap trade impact 11.2 bp, which this K reproduces for a large cap (vol
  ~1.5%) trading ~2% of ADV. Sensitivity K = 1.0 (Goyal-Jegadeesh-Wu's continuous-session square-root fit, 17.7 bp at
  1% of ADV, via L3_lit) is reported, not used to choose.
* AUM: $10M per book (headline), $100M sensitivity. Flat 5 bp x sum|dw| (harness convention) also reported.
"""
import importlib.util
import os
import sys

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "3")

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
import harness  # noqa: E402

PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "Q6_trade")
Q4PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "Q4_portfolio")
DVFILE = os.path.join(ROOT, ".cache", "tree", "q6_dv.npz")
HS, K, SIG_WIN, ADV_WIN = 2.3e-4, 0.5, 60, 20
AUM, AUM_HI = 1e7, 1e8
FLAT = harness.COST


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


q4 = _mod("q4lib_q6", os.path.join(TREE, "Q4_portfolio", "lib.py"))
m1 = q4.m1
mask, val_rows, zscore, sides, nw_t, max_dd = m1.mask, m1.val_rows, m1.zscore, m1.sides, q4.nw_t, q4.max_dd


# ---------------------------------------------------------------- inputs
def signals(D):
    return {"trees": np.load(os.path.join(Q4PREDS, "sig_trees.npy")),
            "ipca": np.load(os.path.join(Q4PREDS, "sig_ipca.npy")),
            "master": D["master_h5_ref"].astype(np.float64)}


def cost_inputs(D, rows):
    """Per scored Thursday: sigma (daily vol) and ADV ($) for every name, from data <= t. Returns (SIG, ADV, info)."""
    z = np.load(DVFILE, allow_pickle=False)
    dv = z["dv"].astype(np.float64)
    fin = harness.load_extra("finra")["total"].astype(np.float64)
    r = D["r"].astype(np.float64)
    n = r.shape[1]
    SIG, ADV = np.zeros((len(rows), n)), np.zeros((len(rows), n))
    fallback = 0
    for j, t in enumerate(rows):
        rr = r[t - SIG_WIN + 1:t + 1]
        s = np.nanstd(rr, 0, ddof=1)
        ok = np.isfinite(rr).sum(0) >= 40
        s[~ok] = np.nanmedian(s[ok])
        SIG[j] = s
        d = dv[t - ADV_WIN + 1:t + 1]
        f = fin[t - ADV_WIN + 1:t + 1]
        a = np.nanmedian(np.where(d > 0, d, np.nan), 0)
        with np.errstate(all="ignore"):
            px_per_fin = np.nanmedian(np.where((d > 0) & (f > 0), d / f, np.nan))      # $ consolidated per FINRA share
            af = np.nanmedian(np.where(f > 0, f, np.nan), 0) * px_per_fin
        miss = ~np.isfinite(a)
        a[miss] = af[miss]
        m = mask_any(D, t)
        fallback += int((miss & m & np.isfinite(af)).sum())
        still = ~np.isfinite(a)
        a[still] = np.nanpercentile(a[np.isfinite(a)], 10)                            # last resort: 10th percentile
        ADV[j] = a
    return SIG, ADV, {"fallback_name_weeks": fallback}


def mask_any(D, t):
    return np.isfinite(D["y5"][t]) & D["elig"][t]


# ---------------------------------------------------------------- the square-root simulator
def trade_cost(dw, sig, adv, aum, k=K, hs=HS):
    """Cost (fraction of AUM) of trading dw (fraction of AUM, per name). Returns (spread part, impact part) arrays."""
    a = np.abs(dw)
    spread = a * hs
    impact = a * k * sig * np.sqrt(a * aum / adv)
    return spread, impact


def simulate_sqrt(W, D, rows, aum=AUM, SIG=None, ADV=None, k=K, hs=HS):
    """W: (len(rows), n) weights (fraction of AUM). Returns weekly net, gross, cost, spread, impact, one-way turnover."""
    if SIG is None or ADV is None:
        SIG, ADV = cost_inputs(D, rows)[:2]
    prev = np.zeros(W.shape[1])
    out = {k_: [] for k_ in ("net", "gross", "cost", "spread", "impact", "turn")}
    for j, t in enumerate(rows):
        w = W[j]
        y = np.nan_to_num(D["y5"][t])
        g = float(w @ y)
        dw = w - prev
        sp, im = trade_cost(dw, SIG[j], ADV[j], aum, k, hs)
        c = float(sp.sum() + im.sum())
        out["net"].append(g - c), out["gross"].append(g), out["cost"].append(c)
        out["spread"].append(float(sp.sum())), out["impact"].append(float(im.sum())), out["turn"].append(float(np.abs(dw).sum() / 2))
        prev = w
    return {k_: np.array(v) for k_, v in out.items()}


def simulate_flat(W, D, rows):
    return m1.simulate(W, D, rows)


# ---------------------------------------------------------------- constructions (all from data <= t)
def pct_rank(s, m):
    p = np.zeros(len(s))
    p[m] = pd.Series(s[m]).rank(pct=True).to_numpy()
    return p


def hysteresis(s, m, state, enter=0.1, exit_=0.3):
    """Enter long in the top `enter`, hold while above 1 - exit_; short mirror. Equal weights, sides 0.5."""
    n = len(s)
    p = pct_rank(s, m)
    top = m & ((p > 1 - enter) | (state.get("top", np.zeros(n, bool)) & (p > 1 - exit_)))
    bot = m & ((p <= enter) | (state.get("bot", np.zeros(n, bool)) & (p <= exit_)))
    state["top"], state["bot"] = top, bot
    w = np.zeros(n)
    w[top], w[bot] = 0.5 / top.sum(), -0.5 / bot.sum()
    return w


def decay_scores(scores, D, rows, d=0.5):
    """score_t = rank(r_t + d r_{t-1}), r = centred cross-sectional percentile rank of the signal on its own scored
    week; a name without last week's rank uses r_t alone. Weekly (scored Thursdays) rows only."""
    out = np.full(scores.shape, np.nan)
    prev = None
    for t in rows:
        m = mask(scores, D, t)
        r = np.full(scores.shape[1], np.nan)
        r[m] = pd.Series(scores[t][m]).rank(pct=True).to_numpy() - 0.5
        comb = r + d * np.nan_to_num(prev, nan=0.0) if prev is not None else r
        out[t] = comb
        prev = r
    return out


def neutralise(x, m, beta):
    """Least-squares projection of x (on names m) onto dollar- and beta-neutral, then gross 1."""
    idx = np.where(m & (x != 0))[0] if (m & (x != 0)).sum() > 2 else np.where(m)[0]
    A = np.column_stack([np.ones(len(idx)), np.nan_to_num(beta[idx], nan=1.0)])
    v = x[idx]
    v = v - A @ np.linalg.lstsq(A, v, rcond=None)[0]
    out = np.zeros(len(x))
    out[idx] = v
    g = np.abs(out).sum()
    return out / g if g > 0 else out


def theta_names(theta, adv, m):
    """A priori per-name trade rate: theta_i = clip(theta * sqrt(ADV_i / median ADV over the masked names), 0.05, 1).
    Rationale: in Garleanu-Pedersen the trade rate is (-r + sqrt(r^2 + 4r))/2 with r = gamma / lambda_i; with a cost
    per unit Lambda_i proportional to 1/ADV_i (JKMP: 0.2/V), r_i is proportional to ADV_i and for small r the rate is
    about sqrt(r_i), so the rate scales with sqrt(relative ADV)."""
    med = np.median(adv[m])
    return np.clip(theta * np.sqrt(adv / med), 0.05, 1.0)


def build(kind, scores, D, rows, ADV=None, theta=None):
    """Weights (len(rows) x n) for one configuration kind in
    {"C0", "C1", "C2", "T1", "T2", "T3", "GP"} (GP needs theta and ADV)."""
    n = scores.shape[1]
    if kind == "C2":
        return q4.build({"target": "mvnl", "nt": 2.0}, scores, D, rows)[0]
    W = np.zeros((len(rows), n))
    sc = decay_scores(scores, D, rows) if kind in ("T2", "T3") else scores
    state, prev = {}, np.zeros(n)
    for j, t in enumerate(rows):
        m = mask(scores, D, t)
        s = sc[t]
        mm = m & np.isfinite(s)
        if kind in ("C0", "T2"):
            w = m1.aim_decile(s, mm)
        elif kind == "C1":
            w = q4.t_band(s, mm, state, 0.1)
        elif kind in ("T1", "T3"):
            w = hysteresis(s, mm, state)
        elif kind == "GP":
            aim = q4.t_mvnl(s, mm, D, t)
            if j == 0:
                w = aim
            else:
                th = theta_names(theta, ADV[j], mm)
                p = np.where(mm, prev, 0.0)
                x = np.where(mm, p + th * (aim - p), 0.0)
                w = neutralise(x, mm, D["beta"][t].astype(np.float64))
        else:
            raise ValueError(kind)
        W[j] = w
        prev = w
    return W


# ---------------------------------------------------------------- metrics
def sharpe(x):
    return float(x.mean() / x.std(ddof=1) * np.sqrt(52)) if len(x) > 2 and x.std() > 0 else float("nan")


def evaluate(W, D, rows, SIG, ADV, SIGHI=None):
    """All registered metrics for one weight panel (first week dropped). Returns (row dict, weekly nets dict)."""
    s10 = simulate_sqrt(W, D, rows, AUM, SIG, ADV)
    s100 = simulate_sqrt(W, D, rows, AUM_HI, SIG, ADV)
    sk1 = simulate_sqrt(W, D, rows, AUM, SIG, ADV, k=1.0)
    sf = simulate_flat(W, D, rows)
    sl = slice(1, None)
    years = D["S"][rows[sl]].year.to_numpy()
    a, b = years <= 2016, years >= 2017
    net = s10["net"][sl]
    res = {"net_sharpe": sharpe(net), "net_pct_per_year": 52 * 100 * net.mean(),
           "net_sharpe_100m": sharpe(s100["net"][sl]), "net_pct_per_year_100m": 52 * 100 * s100["net"][sl].mean(),
           "net_sharpe_k1": sharpe(sk1["net"][sl]), "net_pct_per_year_k1": 52 * 100 * sk1["net"][sl].mean(),
           "net_sharpe_flat5": sharpe(sf["net"][sl]), "net_pct_per_year_flat5": 52 * 100 * sf["net"][sl].mean(),
           "gross_sharpe": sharpe(s10["gross"][sl]), "gross_pct_per_year": 52 * 100 * s10["gross"][sl].mean(),
           "cost_pct_per_year": 52 * 100 * s10["cost"][sl].mean(), "spread_pct_per_year": 52 * 100 * s10["spread"][sl].mean(),
           "impact_pct_per_year": 52 * 100 * s10["impact"][sl].mean(),
           "impact_pct_per_year_100m": 52 * 100 * s100["impact"][sl].mean(),
           "vol_pct_per_year": float(net.std(ddof=1) * np.sqrt(52) * 100), "max_drawdown": max_dd(net),
           "turnover_wk": float(s10["turn"][sl].mean()), "mean_gross": float(np.abs(W[sl]).sum(1).mean()),
           "net_sharpe_2013_2016": sharpe(net[a]), "net_sharpe_2017_2019": sharpe(net[b]),
           "net_pct_2013_2016": 52 * 100 * net[a].mean(), "net_pct_2017_2019": 52 * 100 * net[b].mean(),
           "weeks": int(len(net))}
    nets = {"net10": net, "net100": s100["net"][sl], "flat5": sf["net"][sl], "gross": s10["gross"][sl]}
    return res, nets


def vol_matched(W, D, rows, SIG, ADV, target_vol, aum=AUM):
    """Scale the book's weights by c so its gross weekly return vol equals target_vol, re-simulate under the sqrt model
    (so impact grows with the larger book). Returns (c, weekly net)."""
    g = simulate_sqrt(W, D, rows, aum, SIG, ADV)["gross"][1:]
    c = target_vol / g.std(ddof=1)
    return float(c), simulate_sqrt(W * c, D, rows, aum, SIG, ADV)["net"][1:]


def paired(a, b):
    d = a - b
    return {"diff_pct_per_year": float(52 * 100 * d.mean()), "t": nw_t(d)}
