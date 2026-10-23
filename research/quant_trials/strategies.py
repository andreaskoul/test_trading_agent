"""Every model x horizon x literature strategy on the S&P 500 predictions (PREREG_quant_transformers.md Amendment 2).
Descriptive only; all returns in % per year.

    python sp500_transformers.py strategies      # after `score`
"""

import io
import os
import urllib.request

import numpy as np
import pandas as pd

import panel as P

COST, MARGIN_SPREAD, UP, DOWN, TREND = 5e-4, 0.0243, 1.3, 0.7, 200
GROSS_SIDE, VOL_TARGET, VOL_CAP, VOL_WEEKS = 0.5, 0.10, 1.5, 13
STRATS = ("S0", "S1", "S2", "S3", "S4")


def dtb3():
    """FRED DTB3, downloaded once and frozen in the cache (Amendment 2)."""
    path = os.path.join(P.CACHE, "dtb3.csv")
    if not os.path.exists(path):
        with urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3", timeout=60) as r:
            s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
        s.columns = ["date", "v"]
        s.dropna().to_csv(path, index=False)
    s = pd.read_csv(path, parse_dates=["date"])
    return s.set_index("date")["v"] / 100


def periods(d, years):
    """Thursday decisions t and holding returns from close(t+1) to the next decision's close(+1)."""
    S = d["S"]
    th = np.where((S.weekday == 3) & (S.year >= min(years)) & (S.year <= max(years)))[0]
    lr = np.vstack([np.zeros((1, d["r"].shape[1])), np.cumsum(np.log1p(np.nan_to_num(d["r"])), 0)])
    lm = np.concatenate([[0], np.cumsum(np.log1p(np.nan_to_num(d["rm"])))])
    out = []
    for k in range(len(th) - 1):
        t, t2 = th[k], th[k + 1]
        if t2 + 2 > len(S):
            break
        out.append((t, np.expm1(lr[t2 + 2] - lr[t + 2]), float(np.expm1(lm[t2 + 2] - lm[t + 2])),
                    (S[t2 + 1] - S[t + 1]).days))
    return out


def vol60(d):
    return pd.DataFrame(d["r"]).rolling(60, min_periods=50).std().values


def targets(pred_t, ok, prev, strat, vol, h):
    """Target stock weights for one decision."""
    n = len(pred_t)
    w = np.zeros(n)
    if ok.sum() < 30:
        return w
    pct = np.full(n, np.nan)
    pct[ok] = pd.Series(pred_t[ok]).rank(pct=True).values
    if strat in ("S0", "S1"):
        top, bot = ok & (pct > 0.9), ok & (pct <= 0.1)
        if strat == "S1" and prev is not None:                # keep earlier names until they leave the 20% band
            top |= ok & (prev > 0) & (pct > 0.8)
            bot |= ok & (prev < 0) & (pct <= 0.2)
        w[top], w[bot] = GROSS_SIDE / max(top.sum(), 1), -GROSS_SIDE / max(bot.sum(), 1)
        return w
    z = np.zeros(n)
    z[ok] = (pred_t[ok] - pred_t[ok].mean()) / pred_t[ok].std()
    raw = np.where(ok & np.isfinite(vol) & (vol > 0), z / np.where(vol > 0, vol, 1), 0.0)
    lo, hi = ok & (pct > 2 / 3) & (raw > 0), ok & (pct <= 1 / 3) & (raw < 0)
    w[lo] = GROSS_SIDE * raw[lo] / raw[lo].sum() if lo.any() else 0
    w[hi] = -GROSS_SIDE * raw[hi] / raw[hi].sum() if hi.any() else 0
    if strat in ("S3", "S4") and prev is not None:
        lam = 1 - 0.5 ** (5 / h)
        w = prev + lam * (w - prev)
    return w


def backtest(d, pred, h, strat, years, rf, vol):
    S, spy = d["S"], pd.Series(d["spy"])
    ma = spy.rolling(TREND, min_periods=TREND).mean().values
    rows, prev, base_prev, prev_spy, prev_s, hist = [], None, None, 0.0, None, []
    for t, R, Rm, days in periods(d, years):
        ok = np.isfinite(pred[t]) & d["elig"][t]
        base = targets(pred[t], ok, base_prev, strat, vol[t], h)   # S4 adjusts its unscaled S3 book
        w, scale = base, 1.0
        if strat == "S4":
            if len(hist) >= VOL_WEEKS:
                v = np.std(hist[-VOL_WEEKS:], ddof=1) * np.sqrt(52)
                scale = min(VOL_CAP, VOL_TARGET / v) if v > 0 else VOL_CAP
            w = w * scale
        beta = np.nan_to_num(d["beta"][t], nan=1.0)
        w_spy = -float((w * beta).sum())
        dw = np.abs(w - (prev if prev is not None else 0)).sum() + abs(w_spy - prev_spy)
        gross = float((w * np.nan_to_num(R)).sum() + w_spy * Rm)
        book = gross - COST * dw
        if strat == "S4":
            hist.append(book / scale if scale > 0 else 0.0)  # the unscaled book's returns set the next scale
        r_ann = float(rf.asof(S[t] - pd.Timedelta(days=1))) + MARGIN_SPREAD
        mrate = r_ann * days / 360
        s = UP if np.isfinite(ma[t]) and d["spy"][t] > ma[t] else DOWN
        net = float(w.sum()) + w_spy
        sleeve = s * Rm - COST * abs(s - (prev_s if prev_s is not None else s))
        total = sleeve + book - max(s + net - 1, 0) * mrate
        rows.append({"t": t, "year": S[t].year, "days": days, "book": book, "total": total, "spy": Rm, "s": s,
                     "mrate": mrate, "turnover": dw})
        prev, base_prev, prev_spy, prev_s = w, base, w_spy, s
    return pd.DataFrame(rows)


def stats(df, sbar=None):
    if df.empty:
        return {}
    yrs = df.days.sum() / 365.25
    ann = lambda x: float(np.prod(1 + x) ** (1 / yrs) - 1)
    sbar = df.s.mean() if sbar is None else sbar
    rm = sbar * df.spy - np.maximum(sbar - 1, 0) * df.mrate
    out = {"book_pct_yr": ann(df.book) * 100, "book_sleeve_pct_yr": ann(df.total) * 100,
           "spy_pct_yr": ann(df.spy) * 100, "risk_matched_pct_yr": ann(rm) * 100}
    out["vs_spy_pct_yr"] = out["book_sleeve_pct_yr"] - out["spy_pct_yr"]
    out["vs_risk_matched_pct_yr"] = out["book_sleeve_pct_yr"] - out["risk_matched_pct_yr"]
    per_wk = df.total * 7 / df.days
    out["sharpe"] = float(per_wk.mean() / per_wk.std() * np.sqrt(52)) if per_wk.std() > 0 else np.nan
    v = np.cumprod(1 + df.total.values)
    out["max_dd_pct"] = float((v / np.maximum.accumulate(np.concatenate([[1], v]))[1:] - 1).min()) * 100
    out["turnover_pct_yr"] = float(df.turnover.sum() / yrs) * 100
    return out


SPANS = {"2013-25": (2013, 2025), "2013-19": (2013, 2019), "2020-25": (2020, 2025), "2022": (2022, 2022)}


def run_all(d, preds, years, models, out_md, hs=(5, 10, 20), spans=SPANS):
    rf, vol = dtb3(), vol60(d)
    rows = []
    for m in models:
        for h in hs:
            for st in STRATS:
                df = backtest(d, preds[(m, h)], h, st, years, rf, vol)
                for name, (a, b) in spans.items():
                    sub = df[(df.year >= a) & (df.year <= b)]
                    if len(sub):
                        rows.append({"model": m, "h": h, "strategy": st, "span": name, **stats(sub)})
    tab = pd.DataFrame(rows)
    tab.to_csv(out_md.replace(".md", ".csv"), index=False)
    with open(out_md, "w") as f:
        f.write("# Every model on every literature strategy, S&P 500 2013-2025 (descriptive; PREREG_quant_transformers "
                "Amendment 2)\n\nAll returns in % per year. Book: long/short, 50% + 50% of NAV, beta-hedged. "
                "+ sleeve: the owner's dynamic SPY sleeve (1.3x / 0.7x). Costs: 5 bp per side, margin DTB3 + 2.43%, "
                "idle cash 0, ETB borrow $0. These predictions were seen at scoring: the strategy is chosen on "
                "forward weeks only. S5 runs forward only (no quantiles in the saved parts).\n\n")
        for name in spans:
            f.write(f"## {name}\n\n" + tab[tab.span == name].drop(columns="span").round(2).to_markdown(index=False)
                    + "\n\n")
    return tab
