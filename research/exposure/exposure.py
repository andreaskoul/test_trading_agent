"""Market exposure policies on a century of daily data (research/exposure/PREREG.md). Run once:

    python3 research/exposure/exposure.py

Inputs: .cache/exposure/F-F_Research_Data_Factors_daily.csv (Ken French), .cache/trendspider/SPY_15m.csv (Alpaca).
Output: research/exposure/results.json.
"""
import json, math, os
import numpy as np
import pandas as pd

FF = ".cache/exposure/F-F_Research_Data_Factors_daily.csv"
OUT = "research/exposure/results.json"
TARGET, CAP, SPREAD, SEED = 0.16, 1.5, 0.01, 20261104


def french():
    raw = pd.read_csv(FF, skiprows=4, names=["d", "mkt_rf", "smb", "hml", "rf"], dtype=str)
    raw = raw[raw.d.str.strip().str.fullmatch(r"\d{8}", na=False)]
    df = pd.DataFrame({"mkt": raw.mkt_rf.astype(float) / 100 + raw.rf.astype(float) / 100, "rf": raw.rf.astype(float) / 100})
    df.index = pd.to_datetime(raw.d.str.strip(), format="%Y%m%d")
    return df


def weights(r):
    """Policy weights for day t, using information up to the close of t-1."""
    m = r.index.to_period("M")
    month_start = np.r_[True, m[1:] != m[:-1]]
    w = {"P0": pd.Series(1.0, index=r.index)}
    # P1: expanding volatility of all past data, set on each month's first session
    ev = r.expanding(min_periods=252).std().shift(1) * 252 ** .5
    w["P1"] = pd.Series(np.where(month_start, np.minimum(CAP, TARGET / ev), np.nan), index=r.index).ffill()
    # P2: realised volatility of the previous calendar month
    mv = r.groupby(m).std() * 252 ** .5
    prev = mv.shift(1).reindex(m).to_numpy()
    w["P2"] = pd.Series(np.where(month_start, np.minimum(CAP, TARGET / prev), np.nan), index=r.index).ffill()
    # P3: owner's sleeve, 1.3x above the 200-session average of the total-return index at the previous close
    idx = (1 + r).cumprod()
    ma = idx.rolling(200).mean()
    up = (idx > ma).where(ma.notna()).shift(1)
    w["P3"] = pd.Series(np.where(up.isna(), np.nan, np.where(up == True, 1.3, 0.7)), index=r.index)
    return w


def policy_returns(r, rf, w, cost):
    dw = w.diff().abs().fillna(0.0)
    return w * r + (1 - w) * rf - np.maximum(w - 1, 0) * SPREAD / 252 - cost * dw


def stats(rp, rf, w=None):
    ex = rp - rf
    wealth = (1 + rp).cumprod()
    yrs = len(rp) / 252
    out = dict(cagr=float(wealth.iloc[-1] ** (1 / yrs) - 1), vol=float(rp.std() * 252 ** .5),
               sharpe=float(ex.mean() / ex.std() * 252 ** .5), maxdd=float((wealth / wealth.cummax() - 1).min()),
               worst_12m=float((wealth / wealth.shift(252) - 1).min()), years=round(yrs, 1))
    if w is not None:
        out.update(avg_w=float(w.mean()), max_w=float(w.max()), turnover_per_yr=float(w.diff().abs().sum() / yrs))
    return out


def stationary_boot_idx(n, block, rng):
    out, tot = [], 0
    while tot < n:
        L = rng.geometric(1 / block); s = rng.integers(n)
        out.append((s + np.arange(L)) % n); tot += L
    return np.concatenate(out)[:n]


def sharpe_np(x):
    return x.mean() / x.std() * 252 ** .5


def holm(p, alpha=0.05):
    order = sorted(p, key=p.get); m = len(p); res, ok = {}, True
    for i, k in enumerate(order):
        ok = ok and p[k] <= alpha / (m - i)
        res[k] = ok
    return res


def run(r, rf, cost):
    w = weights(r)
    start = max(s.first_valid_index() for s in w.values())
    start = (start + pd.offsets.MonthBegin(1)) if start.day != 1 else start
    sl = slice(start, None)
    R = {k: policy_returns(r, rf, v, cost).loc[sl] for k, v in w.items()}
    W = {k: v.loc[sl] for k, v in w.items()}
    return R, W, rf.loc[sl], start


def main():
    ff = french()
    r, rf = ff.mkt, ff.rf
    res = {"data": dict(first=str(ff.index[0].date()), last=str(ff.index[-1].date()), sessions=len(ff))}
    R, W, rfs, start = run(r, rf, 0.0002)
    res["evaluation_start"] = str(start.date())
    res["full"] = {k: stats(R[k], rfs, W[k]) for k in R}
    # tests vs P0
    ex = {k: (R[k] - rfs).to_numpy() for k in R}
    rng = np.random.default_rng(SEED); n = len(rfs)
    diffs = {k: [] for k in ("P1", "P2", "P3")}
    for _ in range(5000):
        ix = stationary_boot_idx(n, 20, rng)
        s0 = sharpe_np(ex["P0"][ix])
        for k in diffs:
            diffs[k].append(sharpe_np(ex[k][ix]) - s0)
    p = {k: float(np.mean(np.array(v) <= 0)) for k, v in diffs.items()}
    hp = holm(p)
    res["tests"] = {k: dict(sharpe_diff=res["full"][k]["sharpe"] - res["full"]["P0"]["sharpe"], p_one_sided=p[k],
                            ci90=[float(np.percentile(diffs[k], 5)), float(np.percentile(diffs[k], 95))],
                            holm_sharpe_ok=bool(hp[k]),
                            drawdown_ok=bool(res["full"][k]["maxdd"] >= res["full"]["P0"]["maxdd"]),
                            PASS=bool(hp[k] and res["full"][k]["maxdd"] >= res["full"]["P0"]["maxdd"])) for k in diffs}
    # risk-matched P0 for each candidate (constant weight at the candidate's volatility, same financing)
    res["risk_matched_P0"] = {}
    for k in ("P1", "P2", "P3"):
        c = res["full"][k]["vol"] / res["full"]["P0"]["vol"]
        rp = policy_returns(r, rf, pd.Series(c, index=r.index), 0.0002).loc[start:]
        res["risk_matched_P0"][k] = dict(weight=round(c, 3), **stats(rp, rfs))
    # sub-periods and costs
    res["sub_periods"] = {}
    for a, b in (("1926", "1962"), ("1963", "1999"), ("2000", "2026")):
        res["sub_periods"][f"{a}-{b}"] = {k: stats(R[k].loc[a:b], rfs.loc[a:b], W[k].loc[a:b]) for k in R}
    R10, W10, rf10, _ = run(r, rf, 0.0010)
    res["costs_10bp"] = {k: stats(R10[k], rf10, W10[k]) for k in R10}
    # modern check on SPY
    spy = pd.read_csv(".cache/trendspider/SPY_15m.csv", parse_dates=["ts_utc"])
    spy["day"] = spy.ts_utc.dt.tz_convert("America/New_York").dt.date
    px = spy.groupby("day").close.last(); px.index = pd.to_datetime(px.index)
    rs = px.pct_change().dropna()
    rfm = rf.reindex(rs.index).ffill().fillna(rf.iloc[-1])
    w = weights(rs)
    res["modern_spy"] = {}
    for k, v in w.items():
        rp = policy_returns(rs, rfm, v, 0.0002).loc["2016-03-01":]
        res["modern_spy"][k] = stats(rp, rfm.loc["2016-03-01":], v.loc["2016-03-01":])
    res["modern_spy"]["note"] = "P1 on SPY uses only SPY's own history from 2016 (expanding vol from 2017)"
    json.dump(res, open(OUT, "w"), indent=1)
    show = lambda d: pd.DataFrame({k: v for k, v in d.items() if isinstance(v, dict)}).T.round(3).to_string()
    print("evaluation from", res["evaluation_start"]); print(show(res["full"]))
    print(json.dumps(res["tests"], indent=1)); print(show(res["risk_matched_P0"]))
    for k, v in res["sub_periods"].items(): print(k); print(show(v))
    print("10bp"); print(show(res["costs_10bp"])); print("modern SPY"); print(show(res["modern_spy"]))


if __name__ == "__main__":
    main()
