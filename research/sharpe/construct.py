"""Position placement and drawdown control on the MASTER 5-day scores (research/sharpe/PREREG.md, Amendment 3).
Development on a seen sample; research only. Run from anywhere:

    python research/sharpe/construct.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
QT = os.environ.get("QT_ROOT", os.path.join(os.path.dirname(ROOT), "quant-tf"))
sys.path.insert(0, os.path.join(QT, "research", "quant_trials"))
import sp500_test as T          # noqa: E402
import strategies as ST         # noqa: E402

SEED, DRAWS, BLOCK, GROSS_SIDE, DD_MAX = 20261110, 5000, 4, 0.5, 0.25
YEARS = range(2013, 2026)


def sectors(names):
    ev = pd.read_parquet(os.path.join(ROOT, ".cache", "p8", "events.parquet"))
    m = ev.groupby("ticker").sector.last()
    return np.array([m.get(n, "Unknown") for n in names])


def deciles(score, ok, groups=None):
    w = np.zeros(len(score))
    if ok.sum() < 30:
        return w
    top, bot = np.zeros(len(score), bool), np.zeros(len(score), bool)
    if groups is None:
        groups = np.zeros(len(score), int)
    for g in np.unique(groups[ok]):
        m = ok & (groups == g)
        pct = pd.Series(score[m]).rank(pct=True).values
        idx = np.where(m)[0]
        top[idx[pct > 0.9]] = True
        bot[idx[pct <= 0.1]] = True
    w[top], w[bot] = GROSS_SIDE / max(top.sum(), 1), -GROSS_SIDE / max(bot.sum(), 1)
    return w


def panic_flags(d):
    spy = pd.Series(d["spy"])
    r = spy.pct_change()
    v21 = r.rolling(21).std()
    return ((spy / spy.shift(252) < 1) & (v21 > v21.rolling(780).median())).fillna(False).values


def run(d, pred, kind, cost, sec, grp, panic):
    """Weekly rows of the whole fund under one construction. Mirrors strategies.backtest."""
    S, spy = d["S"], pd.Series(d["spy"])
    ma = spy.rolling(ST.TREND, min_periods=ST.TREND).mean().values
    rf = RF
    rows, prev, prev_spy, prev_s, hist, wealth = [], None, 0.0, None, [], [1.0]
    for t, R, Rm, days in ST.periods(d, YEARS):
        ok = np.isfinite(pred[t]) & d["elig"][t]
        score = pred[t]
        if kind == "C1":
            w = deciles(score, ok, grp)
        elif kind == "C2":
            w = np.zeros(len(score))
            Zc = d["Z"][t]
            m = ok & np.isfinite(Zc).all(1) & np.isfinite(d["beta"][t])
            if m.sum() >= 60:
                y = (score[m] - score[m].mean()) / score[m].std()
                b = d["beta"][t][m]
                X = np.column_stack([Zc[m], (b - b.mean()) / b.std(), pd.get_dummies(sec[m]).to_numpy(float)])
                res = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
                full = np.full(len(score), np.nan)
                full[m] = res
                w = deciles(full, m)
        elif kind == "C3":
            w = np.zeros(len(score))
            win = d["r"][max(0, t - 251):t + 1]
            m = ok & (np.isfinite(win).sum(0) >= 200)
            if m.sum() >= 60:
                A = np.nan_to_num(win[:, m] - np.nanmean(win[:, m], 0))
                cov = LedoitWolf(assume_centered=True).fit(A).covariance_
                z = (score[m] - score[m].mean()) / score[m].std()
                x = np.linalg.solve(cov, z)
                ww = np.zeros(m.sum())
                pos, neg = x > 0, x < 0
                ww[pos], ww[neg] = GROSS_SIDE * x[pos] / x[pos].sum(), -GROSS_SIDE * x[neg] / x[neg].sum()
                w[m] = ww
        else:
            w = deciles(score, ok)
        scale = 1.0
        if kind == "C4" and panic[t]:
            scale = 0.0
        if kind == "C5":
            if len(hist) >= ST.VOL_WEEKS:
                v = np.std(hist[-ST.VOL_WEEKS:], ddof=1) * np.sqrt(52)
                scale = min(ST.VOL_CAP, ST.VOL_TARGET / v) if v > 0 else ST.VOL_CAP
        base = w
        w = w * scale
        s = ST.UP if np.isfinite(ma[t]) and d["spy"][t] > ma[t] else ST.DOWN
        if kind == "C6":
            peak = max(wealth[-52:])
            mlt = float(np.clip(1 - (1 - wealth[-1] / peak) / DD_MAX, 0, 1))
            w, s = w * mlt, s * mlt
        beta = np.nan_to_num(d["beta"][t], nan=1.0)
        w_spy = -float((w * beta).sum())
        dw = np.abs(w - (prev if prev is not None else 0)).sum() + abs(w_spy - prev_spy)
        book = float((w * np.nan_to_num(R)).sum() + w_spy * Rm) - cost * dw
        if kind == "C5":
            b_spy = -float((base * beta).sum())
            hist.append(float((base * np.nan_to_num(R)).sum() + b_spy * Rm))
        mrate = (float(rf.asof(S[t] - pd.Timedelta(days=1))) + ST.MARGIN_SPREAD) * days / 360
        sleeve = s * Rm - cost * abs(s - (prev_s if prev_s is not None else s))
        total = sleeve + book - max(s + float(w.sum()) + w_spy - 1, 0) * mrate
        wealth.append(wealth[-1] * (1 + total))
        rows.append({"year": S[t].year, "days": days, "book": book, "total": total, "spy": Rm, "turnover": dw})
        prev, prev_spy, prev_s = w, w_spy, s
    return pd.DataFrame(rows)


def summ(df):
    out = {}
    for name, (a, b) in {"2013-25": (2013, 2025), "2013-19": (2013, 2019), "2020-25": (2020, 2025)}.items():
        x = df[(df.year >= a) & (df.year <= b)]
        yrs = x.days.sum() / 365.25
        wk, bk = x.total * 7 / x.days, x.book * 7 / x.days
        v = np.cumprod(1 + x.total.values)
        dd = float((v / np.maximum.accumulate(np.concatenate([[1], v]))[1:] - 1).min())
        ann = float(np.prod(1 + x.total) ** (1 / yrs) - 1)
        out[name] = {"pct_per_year": 100 * ann, "vol_pct": 100 * float(wk.std() * 52 ** .5), "sharpe": float(wk.mean() / wk.std() * 52 ** .5),
                     "worst_fall_pct": 100 * dd, "return_over_fall": ann / abs(dd), "book_sharpe": float(bk.mean() / bk.std() * 52 ** .5) if bk.std() > 0 else float("nan"),
                     "turnover_x_per_year": float(x.turnover.sum() / yrs), "spy_pct_per_year": 100 * float(np.prod(1 + x.spy) ** (1 / yrs) - 1)}
    return out


def boot(a, b, rng):
    """One-sided p that Sharpe(a) > Sharpe(b), paired stationary bootstrap of weekly returns."""
    sh = lambda x: x.mean() / x.std()
    n, d = len(a), np.empty(DRAWS)
    for i in range(DRAWS):
        ix, tot = [], 0
        while tot < n:
            L = rng.geometric(1 / BLOCK); s = rng.integers(n)
            ix.append((s + np.arange(L)) % n); tot += L
        ix = np.concatenate(ix)[:n]
        d[i] = sh(a[ix]) - sh(b[ix])
    return float((d <= 0).mean())


def holm(p, alpha=0.05):
    order = sorted(p, key=p.get); m = len(p); res, ok = {}, True
    for i, k in enumerate(order):
        ok = ok and p[k] <= alpha / (m - i)
        res[k] = bool(ok)
    return res


def main():
    global RF
    d = T.build()
    RF = ST.dtb3()
    pred = np.load(os.path.join(QT, ".cache", "quant_trials", "sp500_tf_master_h5.npz"))["h5"]
    sec = sectors(d["names"])
    cnt = pd.Series(sec).value_counts()
    grp = np.array([s if (s != "Unknown" and cnt[s] >= 10) else "Pooled" for s in sec])
    grp = pd.factorize(grp)[0]
    panic = panic_flags(d)
    res = {"sectors_known": int((sec != "Unknown").sum()), "names": len(sec)}
    for cost, tag in ((5e-4, "5bp"), (1e-4, "1bp")):
        D = {k: run(d, pred, k, cost, sec, grp, panic) for k in ("S0", "C1", "C2", "C3", "C4", "C5", "C6")}
        out = {k: summ(v) for k, v in D.items()}
        if tag == "5bp":
            rng = np.random.default_rng(SEED)
            wk = {k: (v.total * 7 / v.days).to_numpy() for k, v in D.items()}
            p = {k: boot(wk[k], wk["S0"], rng) for k in ("C1", "C2", "C3", "C4", "C5", "C6")}
            hm = holm(p)
            res["tests"] = {k: {"sharpe_diff": float((wk[k].mean() / wk[k].std() - wk["S0"].mean() / wk["S0"].std()) * 52 ** .5), "p_one_sided": p[k], "holm_pass": hm[k]} for k in p}
            res["panic_weeks_share"] = float(np.mean([panic[t] for t, *_ in ST.periods(d, YEARS)]))
        res[tag] = out
    json.dump(res, open(os.path.join(HERE, "RESULT_CONSTRUCT.json"), "w"), indent=1)
    print(json.dumps(res.get("tests"), indent=1))
    for tag in ("5bp", "1bp"):
        print(tag)
        for k, v in res[tag].items():
            a = v["2013-25"]
            print(f"  {k}: {a['pct_per_year']:.1f}%/yr vol {a['vol_pct']:.1f} Sharpe {a['sharpe']:.2f} fall {a['worst_fall_pct']:.1f} ret/fall {a['return_over_fall']:.2f} book Sharpe {a['book_sharpe']:.2f} turn {a['turnover_x_per_year']:.0f}x | 13-19 {v['2013-19']['pct_per_year']:.1f} ({v['2013-19']['sharpe']:.2f}) | 20-25 {v['2020-25']['pct_per_year']:.1f} ({v['2020-25']['sharpe']:.2f})")


if __name__ == "__main__":
    main()
