"""Point-in-time backtest of the shadow `quant` book ("Price factors, whole S&P 500") against SPY buy-and-hold.
Research only: no orders, no LLM, nothing here feeds a decision or score.py.

Each Wednesday since 1997 the book is formed the way fund/screen.py + fund/pm_risk.py form it live:
* universe: the S&P 500 members on that date (data/raw/stocks/sp500_membership.csv), with a Yahoo price;
* signals: screen.py's five price factors, cross-sectional z-scores;
* forecast: the frozen ridge (artefacts/llm/ridge_stocks.json, fit on weeks 2004-01-07 .. 2026-03-31), or a
  walk-forward ridge refit every January on the weeks already closed (alpha 10, same features);
* book: top/bottom 10 at 10% of NAV, sector net <= 30%, dollar net <= 10% of gross, SPY to zero hedge beta
  (Welch 252-day slope-winsorised beta, shrunk a third toward 1);
* marking: shadow_ledger.py's rules: enter at the first session after the as-of, exit at the first session on or
  after as-of + 8 days, 5 bp per side on the change in target weights, cash earns nothing.

Known limits (reported in the output, not hidden): Yahoo has no prices for most delisted names, so coverage of the
point-in-time index is ~40% in 1997 and ~99% in 2026 (survivorship); sectors are today's GICS labels; a few old
tickers now belong to other companies and are excluded by name (REUSED).

    python fund/backtest_quant.py CACHE_DIR         # CACHE_DIR/px.parquet, irx.parquet (downloaded if missing)
"""

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N, UNIT, SECTOR_CAP, DOLLAR_CAP, COST, ALPHA = 10, 0.10, 0.30, 0.10, 5e-4, 10.0
FACTORS = ("mom12_1", "rev1m", "rev1w", "lowvol", "high52")
FIRST, FIT_END = pd.Timestamp("1997-01-01"), pd.Timestamp("2026-03-31")
# Excluded by name: old members whose ticker Yahoo now maps to another company (McDonnell Douglas -> Pediatrix, ...),
# and series with repeated +-25% day-on-day reversals (bad prints; PARA's post-merger history is one)
REUSED = {"MD", "MCIC", "FCN", "CAL", "SCI", "NC", "CSR", "SNT", "AIT", "SII", "KG", "SUN", "CCEP", "FCPT", "BCO",
          "CPWR", "EP", "TKR", "CCK", "DIGI", "COMS", "USBC", "MI", "UPC", "STI", "UK", "DEC", "PARA"}


def load(cache):
    mem = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_membership.csv"), parse_dates=["date"])
    pp, ip = os.path.join(cache, "px.parquet"), os.path.join(cache, "irx.parquet")
    if not os.path.exists(pp):
        import yfinance as yf
        tick = sorted({t.replace(".", "-") for s in mem.tickers for t in s.split(",")} | {"SPY"})
        px = pd.concat([yf.download(tick[i:i + 150], start="1994-06-01", progress=False, auto_adjust=True)["Close"]
                        for i in range(0, len(tick), 150)], axis=1).rename(columns=lambda c: c.replace("-", "."))
        px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
        px.to_parquet(pp)
        irx = yf.download("^IRX", start="1994-06-01", progress=False, auto_adjust=False)["Close"]
        irx.index = pd.to_datetime(irx.index).tz_localize(None).normalize()
        irx.to_parquet(ip)
    px = pd.read_parquet(pp)
    px = px[px.index.dayofweek < 5].where(lambda x: x > 0).dropna(how="all")        # zero prints are missing, not prices
    irx = pd.read_parquet(ip).iloc[:, 0]
    meta = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_current.csv")).set_index("Symbol")["GICS Sector"]
    return mem, px.drop(columns=[c for c in REUSED if c in px]), irx, meta


def signals(px):
    """screen.py's definitions, for every Wednesday at once."""
    days = pd.date_range(px.index.min(), px.index.max(), freq="D")
    d = px.reindex(days).ffill(limit=3)
    wed = d[d.index.dayofweek == 2]
    lw, lr = np.log(wed), np.log(px).diff()
    at = lambda f: f.reindex(days).ffill(limit=3).reindex(wed.index)
    return {"mom12_1": lw.shift(4) - lw.shift(52), "rev1m": -(lw - lw.shift(4)), "rev1w": -(lw - lw.shift(1)),
            "lowvol": -at(lr.rolling(60, min_periods=50).std()),
            "high52": wed / at(px.rolling(252, min_periods=200).max())}, lr


def risk(w, sector, beta):
    """pm_risk.risk: sector cap, dollar-net cap, then SPY to zero beta."""
    w = w.copy()
    sec = sector.reindex(w.index)
    sec = sec.where(sec.notna(), "?" + sec.index.to_series())      # unknown sector (left the index): its own group
    for s, net in w.groupby(sec).sum().items():
        if abs(net) > SECTOR_CAP + 1e-9:
            side = w.index[(sec == s) & (np.sign(w) == np.sign(net))]
            other = net - w[side].sum()
            w[side] *= (np.sign(net) * SECTOR_CAP - other) / w[side].sum()
    L, S = w[w > 0].sum(), -w[w < 0].sum()
    if L + S > 0 and abs(L - S) > DOLLAR_CAP * (L + S) + 1e-9:
        if L > S:
            w[w > 0] *= S * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / L
        else:
            w[w < 0] *= L * (1 + DOLLAR_CAP) / (1 - DOLLAR_CAP) / S
    w = w[w != 0]
    w["SPY"] = -float((w * beta.reindex(w.index)).sum())
    return w


def hedge_beta(lr, asof, names):
    last = lr.loc[:asof].tail(252)
    rm = last["SPY"]
    lo, hi = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
    wins = last[names].clip(lower=lo, upper=hi, axis=0)
    bw = wins.apply(lambda s: s.cov(rm) / rm[s.notna()].var())
    return (2 / 3) * bw.fillna(1.0) + 1 / 3


def ridge(X, y):
    Xc, yc = X - X.mean(0), y - y.mean()
    coef = np.linalg.solve(Xc.T @ Xc + ALPHA * np.eye(X.shape[1]), Xc.T @ yc)
    return coef


def run(cache):
    mem, px, irx, meta = load(cache)
    spec = json.load(open(os.path.join(ROOT, "artefacts/llm/ridge_stocks.json")))
    assert tuple(spec["features"]) == FACTORS
    sig, lr = signals(px)
    days = px.index
    mdates = mem.date.values
    weds = [a for a in sig["mom12_1"].index if a >= FIRST and len(days[days > a])]
    # cross-sections: z-scores of point-in-time members, and each week's realised holding-period return
    xs, cover = {}, []
    for a in weds:
        members = [t for t in mem.tickers.iloc[np.searchsorted(mdates, np.datetime64(a), "right") - 1].split(",")]
        have = [t for t in members if t in px.columns]
        sg = pd.DataFrame({f: sig[f].loc[a].reindex(have) for f in FACTORS}).dropna()
        cover.append({"asof": a, "members": len(members), "priced": len(sg)})
        if len(sg) < 100:
            continue
        Z = (sg - sg.mean()) / sg.std()
        t0 = days[days > a][0]
        nxt = days[days >= a + pd.Timedelta(days=8)]
        t1 = nxt[0] if len(nxt) else days[-1]
        p0 = px.loc[t0].reindex(Z.index.tolist() + ["SPY"])
        p1 = px.loc[:t1].reindex(columns=p0.index).ffill(limit=5).iloc[-1]   # delisted mid-week: last print
        xs[a] = {"Z": Z, "t0": t0, "t1": t1, "closed": bool(len(nxt)), "ret": (p1 / p0 - 1)}
    cover = pd.DataFrame(cover).set_index("asof")
    asofs = sorted(xs)

    # walk-forward coefficients: refit each January on the weeks whose exit is before Jan 1 (min 4 years of weeks)
    wf, cur = {}, None
    for a in asofs:
        if cur is None or a.year != cur[0]:
            past = [b for b in asofs if xs[b]["closed"] and xs[b]["t1"] < pd.Timestamp(f"{a.year}-01-01")]
            if len(past) >= 4 * 52:
                X = np.vstack([xs[b]["Z"].to_numpy() for b in past])
                y = np.concatenate([(xs[b]["ret"].reindex(xs[b]["Z"].index) - xs[b]["ret"].reindex(xs[b]["Z"].index).mean())
                                    .fillna(0).to_numpy() for b in past])
                cur = (a.year, ridge(X, y))
            else:
                cur = (a.year, None)
        wf[a] = cur[1]

    frozen = np.asarray(spec["coef"])
    out = {}
    for model in ("frozen", "walkforward"):
        prev, rows = pd.Series(dtype=float), []
        for a in asofs:
            c = frozen if model == "frozen" else wf[a]
            x = xs[a]
            if c is None:
                continue
            f = pd.Series(x["Z"].to_numpy() @ c, index=x["Z"].index).sort_values()
            raw = pd.concat([pd.Series(UNIT, index=f.index[-N:]), pd.Series(-UNIT, index=f.index[:N])])
            beta = hedge_beta(lr, a, raw.index.tolist())
            w = risk(raw, meta, beta)
            idx = w.index.union(prev.index)
            cost = float((w.reindex(idx, fill_value=0) - prev.reindex(idx, fill_value=0)).abs().sum() * COST)
            r = x["ret"].reindex(w.index).fillna(0)
            stock = w.drop("SPY")
            spy_r = float(x["ret"]["SPY"])
            rf = float(irx.loc[:a].dropna().iloc[-1]) / 100 * (x["t1"] - x["t0"]).days / 365
            rows.append({"asof": a, "entry": x["t0"], "exit": x["t1"], "closed": x["closed"],
                         "book": (1 - cost) * (1 + float((w * r).sum())) - 1, "cost": cost,
                         "long_leg": float((stock[stock > 0] * r[stock[stock > 0].index]).sum()),
                         "short_leg": float((stock[stock < 0] * r[stock[stock < 0].index]).sum()),
                         "hedge": float(w["SPY"] * spy_r), "spy_w": float(w["SPY"]), "spy": spy_r, "rf": rf,
                         "gross": float(stock.abs().sum()), "net": float(stock.sum()),
                         "max_abs_name_ret": float(r.drop("SPY").abs().max()),
                         "longs": ",".join(stock[stock > 0].index), "shorts": ",".join(stock[stock < 0].index)})
            prev = w
        out[model] = pd.DataFrame(rows).set_index("asof")
    return out, cover, wf


if __name__ == "__main__":
    cache = sys.argv[1]
    out, cover, wf = run(cache)
    for k, df in out.items():
        df.to_csv(os.path.join(cache, f"weekly_{k}.csv"))
    cover.to_csv(os.path.join(cache, "coverage.csv"))
    json.dump({str(k.date()): (None if v is None else list(map(float, v))) for k, v in wf.items()},
              open(os.path.join(cache, "walkforward_coef.json"), "w"))
    for k, df in out.items():
        print(k, len(df), df.index.min().date(), df.index.max().date())
