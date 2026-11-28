"""Volatility-forecasting study: daily variance proxies, features and forward targets per asset class.

    PY=~/.fund-runner/venv-vol/bin/python
    $PY -I research/volforecast/features.py build      # -> .cache/volforecast/panel_<class>.parquet

Model-independent: every model in models.py reads these panels. Every feature at origin t uses data <= t only;
targets use t+1..t+H only. Nothing here fits a model or computes a loss.

Daily variance proxy `rv` (the quantity forecast), by class:
  crypto  5-minute realised variance of the UTC day (Binance), NaN when fewer than 90% of the 288 bars exist.
  etf     regular-session 5-minute RV plus the squared overnight return (close-to-close variance), SPY/QQQ/IWM/DIA.
  stock   residual (SPY-hedged) RV: sum over aligned 5-minute slots of (r_i - b r_SPY,i)^2 plus the squared residual
          overnight return; b is the fund's beta (fund/p11.py residuals: 2/3 x lagged 252-session winsorised OLS +
          1/3). Report sessions +-1 are masked (normal-day variance, the sigma_d of Protocol 11's W11).
  index   squared daily close-to-close log return (no free intraday history); ranges enter as features only.
`r2` is the squared close-to-close return (residual for stocks): the fund's own proxy, kept for a robustness read.
Target y_H(t) = H x mean(rv over the valid days of t+1..t+H), valid when at least 80% of the H days are valid.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import data as DATA  # noqa: E402

HORIZONS = (1, 5, 22, 55)                      # sessions; crypto uses the same wall-clock spans in calendar days
HORIZONS_BY_CLASS = {"crypto": (1, 7, 31, 77), "etf": HORIZONS, "index": HORIZONS, "stock": HORIZONS}
LAGS_BY_CLASS = {"crypto": (7, 30), "etf": (5, 22), "index": (5, 22), "stock": (5, 22)}   # HAR weekly, monthly
COM = (1, 5, 25, 125)                          # S6 EWMA centres of mass (Bollerslev, Hood, Huss, Pedersen 2018)
VALID_SHARE = 0.8
LN2 = math.log(2)
P8 = os.environ.get("P8_CACHE", os.path.join(ROOT, ".claude", "worktrees", "bridge-cse_019vq28qyY43Z526tPMKCbmw",
                                             ".cache", "p8"))
CLASSES = ("crypto", "etf", "index", "stock")


# ===================================================================================== helpers
def roll_mean(x, w, minp):
    return x.rolling(w, min_periods=minp).mean()


def forward_target(rv, H):
    """H x mean of rv over t+1..t+H; NaN unless >= 80% of the H days are valid."""
    v = rv.shift(-1)
    s = v[::-1].rolling(H, min_periods=1).sum()[::-1]
    n = v.notna().astype(float)[::-1].rolling(H, min_periods=1).sum()[::-1]
    pos = np.arange(len(v))
    complete = (len(v) - 1 - pos) >= H                                # t+1..t+H all inside the sample
    y = H * s / n
    return y.where((n >= max(1, math.ceil(VALID_SHARE * H))) & complete)


def har_block(df, col, prefix, mask=None, lags=(5, 22)):
    """Daily, weekly and monthly averages of a daily measure (lags 5/22 sessions; 7/30 days for crypto), plus a
    quarterly one; masked days excluded from the averages (a masked day's daily value is the previous day's)."""
    x = df[col] if mask is None else df[col].where(~mask)
    w, mo = lags
    out = {f"{prefix}_d": x.ffill(limit=1) if mask is not None else x,
           f"{prefix}_w": roll_mean(x, w, max(2, int(0.6 * w))), f"{prefix}_m": roll_mean(x, mo, int(0.7 * mo)),
           f"{prefix}_q": roll_mean(x, 3 * mo, 2 * mo)}
    return pd.DataFrame(out, index=df.index)


def ewma_factors(x, mask=None):
    """S6: EWMAs of rv with centres of mass 1, 5, 25, 125 (masked days skipped), and the expanding long-run mean."""
    v = x if mask is None else x.where(~mask)
    out = {f"ew{c}": v.ewm(com=c, ignore_na=True, min_periods=1).mean() for c in COM}
    out["lr"] = v.expanding(min_periods=20).mean()
    out["n_hist"] = v.notna().cumsum()
    return pd.DataFrame(out, index=x.index)


def ranges(df):
    """Range estimators of the open-to-close (intraday) variance from daily OHLC, and the squared overnight return."""
    o, h, l, c = (np.log(df[k]) for k in ("open", "high", "low", "close"))
    ok = (df["high"] > df["low"]) & (df["open"] > 0)
    pk = ((h - l) ** 2 / (4 * LN2)).where(ok)
    gk = (0.5 * (h - l) ** 2 - (2 * LN2 - 1) * (c - o) ** 2).where(ok)
    rs = ((h - c) * (h - o) + (l - c) * (l - o)).where(ok)
    on = (o - c.shift(1)) ** 2
    return pd.DataFrame({"pk": pk, "gk": gk, "rsr": rs, "on2": on}, index=df.index)


def common_features(df, mask=None, lags=(5, 22)):
    """Everything a model may read at origin t, from the class-specific columns rv, r2, ret (+ OHLC)."""
    F = [har_block(df, "rv", "rv", mask, lags), har_block(df, "r2", "r2", mask, lags), ewma_factors(df["rv"], mask)]
    rng = ranges(df)
    for k in ("pk", "gk", "rsr", "on2"):
        tmp = pd.DataFrame({k: rng[k]})
        F.append(har_block(tmp, k, k, mask, lags))
    neg = df["ret"].clip(upper=0)
    neg = neg if mask is None else neg.where(~mask)
    F.append(pd.DataFrame({"lev_d": neg, "lev_w": roll_mean(neg, lags[0], 3), "lev_m": roll_mean(neg, lags[1], 15)},
                          index=df.index))
    for k in ("bv", "rs_neg", "rs_pos", "rq"):
        if k in df:
            F.append(har_block(df, k, k, mask, lags))
    if "bv" in df:
        j = (df["rv"] - df["bv"]).clip(lower=0)
        F.append(pd.DataFrame({"jump_d": j if mask is None else j.where(~mask)}, index=df.index))
    X = pd.concat(F, axis=1)
    X["ret"] = df["ret"] if mask is None else df["ret"].where(~mask)
    X["dow"] = df.index.dayofweek
    X["gap_days"] = pd.Series(df.index, index=df.index).diff().dt.days      # weekend / holiday before day t
    return X


def targets(df, rv_col="rv", r2_col="r2", horizons=HORIZONS):
    """Forward targets and, for each H, the date on which the target window closes (session t+H of the asset's
    own calendar): a model refit on date tau may train only on rows with end_H < tau."""
    T = {}
    dates = pd.Series(df.index, index=df.index)
    for H in horizons:
        T[f"y{H}"] = forward_target(df[rv_col], H)
        T[f"y{H}_r2"] = forward_target(df[r2_col], H)
        T[f"end{H}"] = dates.shift(-H)
    return pd.DataFrame(T, index=df.index)


def load_daily(rel):
    p = os.path.join(DATA.DAILY, rel)
    m = DATA.load_manifest()
    key = os.path.relpath(p, DATA.CACHE)
    if m["daily"].get(key) != DATA.sha(p):
        raise SystemExit(f"{key}: sha256 differs from the manifest (rule 4)")
    return pd.read_parquet(p)


def vix_series():
    V = load_daily("index_VIX.parquet")["close"]
    return np.log((V / 100) ** 2 / 252).rename("lvix")                       # daily variance implied by VIX, in logs


# ===================================================================================== classes
def build_crypto():
    out = []
    for sym in DATA.CRYPTO:
        D = load_daily(f"crypto_{sym}.parquet").copy()
        D["rv"] = D["rv"].where(D["rv_ok"])
        for k in ("bv", "rs_neg", "rs_pos", "rq"):
            D[k] = D[k].where(D["rv_ok"])
        D["r2"] = D["ret"] ** 2
        D = D.asfreq("D")                                                     # a missing UTC day is a missing row
        X = pd.concat([common_features(D, lags=LAGS_BY_CLASS["crypto"]),
                       targets(D, horizons=HORIZONS_BY_CLASS["crypto"])], axis=1)
        X["asset"] = sym
        out.append(X[D["close"].notna()])
    P = pd.concat(out)
    # market factor for crypto (S8): the cross-coin mean of the daily rv, HAR lags 1/7/30 days
    m = P.groupby(level=0)["rv_d"].mean().sort_index().asfreq("D")
    mk = pd.DataFrame({"mkt_rv_d": m, "mkt_rv_w": roll_mean(m, 7, 4), "mkt_rv_m": roll_mean(m, 30, 21)})
    return P.join(mk, how="left")


def early_closes():
    """NYSE 13:00 early-close sessions: Alpaca serves post-market bars 13:00-16:00 on those days, which a clock filter
    would count as regular session and then double-count against the next overnight return."""
    import pandas_market_calendars as mcal
    s = mcal.get_calendar("NYSE").schedule(DATA.STOCK_START, DATA.END)
    return set(s.index[s["market_close"].dt.tz_convert("America/New_York").dt.hour < 16].normalize())


EARLY = None


def intraday(D, step):
    """The regular-session slot matrix (float), truncated at 13:00 on early-close days."""
    global EARLY
    if EARLY is None:
        EARLY = early_closes()
    pre, n = ("r", 78) if step == 5 else ("q", 26)
    R = D[[f"{pre}{i:02d}" for i in range(1, n + 1)]].astype(float).copy()
    cut = 210 // step                                                         # 09:30 -> 13:00 is 210 minutes
    early = R.index.isin(list(EARLY))
    R.iloc[early, cut:] = np.nan
    return R


def _spy_slots():
    S = load_daily("alpaca/SPY.parquet")
    return S, intraday(S, 5)


def to15(R5):
    """Aggregate 5-minute log returns into 15-minute slots (sum of three; NaN when all three are missing)."""
    a = R5.values.reshape(len(R5), 26, 3)
    s = np.nansum(a, 2)
    s[np.isnan(a).all(2)] = np.nan
    return pd.DataFrame(s, index=R5.index, columns=[f"q{i:02d}" for i in range(1, 27)])


def build_etf():
    out = []
    S, RS = _spy_slots()
    expected = RS.notna().sum(axis=1)                                         # SPY defines the session's slots
    for sym in DATA.ETFS:
        D = load_daily(f"alpaca/{sym}.parquet").copy()
        R = intraday(D, 5)
        ok = R.notna().sum(axis=1) >= 0.9 * expected.reindex(D.index)
        rr = R.values
        D["rv"] = pd.Series(np.nansum(rr ** 2, 1), index=D.index).where(ok) + D["ret_on"] ** 2
        a = np.abs(rr)
        n = np.isfinite(rr).sum(1)
        D["bv"] = pd.Series(np.nansum(a[:, 1:] * a[:, :-1], 1) * (math.pi / 2) * n / np.maximum(n - 1, 1),
                            index=D.index).where(ok) + D["ret_on"] ** 2
        D["rs_neg"] = pd.Series(np.nansum(np.where(rr < 0, rr ** 2, 0), 1), index=D.index).where(ok)
        D["rs_pos"] = pd.Series(np.nansum(np.where(rr > 0, rr ** 2, 0), 1), index=D.index).where(ok)
        D["rq"] = pd.Series(n / 3 * np.nansum(rr ** 4, 1), index=D.index).where(ok)
        D["r2"] = D["ret"] ** 2
        X = pd.concat([common_features(D), targets(D)], axis=1)
        X = X.join(vix_series(), how="left")
        X["asset"] = sym
        out.append(X)
    return pd.concat(out)


def build_index():
    out = []
    for t in DATA.INDICES:
        if t == "^VIX":
            continue
        D = load_daily(f"index_{t.replace('^', '')}.parquet").copy()
        D["r2"] = D["ret"] ** 2
        D["rv"] = D["r2"]
        X = pd.concat([common_features(D), targets(D)], axis=1)
        X = X.join(vix_series(), how="left")
        X["asset"] = t
        out.append(X)
    P = pd.concat(out)
    # S6 market factor for indices: the cross-index mean of the daily proxy on the union calendar, EWMA CoM 5
    m = P.groupby(level=0)["rv_d"].mean().sort_index()
    mk = pd.DataFrame({"mkt_ew5": m.ewm(com=5, min_periods=1).mean(), "mkt_lr": m.expanding(min_periods=20).mean()})
    return P.join(mk, how="left")


def beta_fund(r, rm):
    """fund/p11.py residuals(): b = 2/3 x (252-session slope-winsorised OLS beta, lagged one session) + 1/3."""
    lo, hi = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
    w = r.clip(lower=lo, upper=hi)
    ols = w.rolling(252, min_periods=200).cov(rm) / rm.rolling(252, min_periods=200).var()
    return (2 / 3 * ols + 1 / 3).shift(1)


def report_masks(tickers, index):
    """Report sessions +-1 per ticker: P8 SEC events (to 2026-09-30) and the live Protocol 11 screens after it."""
    E = pd.read_parquet(os.path.join(P8, "events_sealed.parquet"))
    E = E[E["universe"] == "sp500"]
    sess = {t: set() for t in tickers}
    for t, d in zip(E["ticker"], pd.to_datetime(E["t0"])):
        if t in sess:
            sess[t].add(d.normalize())
    p11 = os.path.join(DATA.CACHE, "p11_report_sessions.json")
    if os.path.exists(p11):
        for t, ds in json.load(open(p11)).items():
            if t in sess:
                sess[t] |= {pd.Timestamp(x) for x in ds}
    cal = pd.DatetimeIndex(index)
    pos = {d: i for i, d in enumerate(cal)}
    M = pd.DataFrame(False, index=cal, columns=list(tickers))
    for t, ds in sess.items():
        for d in ds:
            i = pos.get(d)
            if i is None:                                                     # report on a non-session: next session
                j = cal.searchsorted(d)
                if j >= len(cal):
                    continue
                i = j
            M.iloc[max(0, i - 1):i + 2, M.columns.get_loc(t)] = True
    return M


def build_stock():
    S, RS5 = _spy_slots()
    RS = to15(RS5)                                                            # stocks are at 15 minutes
    expected = RS.notna().sum(axis=1)
    rm = S["ret"]
    names, al = DATA.stock_symbols()
    files = {f[:-8] for f in os.listdir(os.path.join(DATA.DAILY, "alpaca")) if f.endswith(".parquet")}
    syms = [s for s in names if s in files and s not in DATA.ETFS]
    mem = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    mem = mem.set_index("date")["tickers"].str.split(",")
    masks = report_masks(syms, S.index)
    out = []
    for sym in syms:
        D = load_daily(f"alpaca/{sym}.parquet").copy().reindex(S.index)
        b = beta_fund(D["ret"], rm)
        Rq = intraday(D, 15)
        R = Rq.values
        E5 = R - b.values[:, None] * RS.values
        ok = (Rq.notna().sum(axis=1) >= 0.9 * expected) & b.notna()
        e_on = D["ret_on"] - b * S["ret_on"]
        D["rv"] = (pd.Series(np.nansum(E5 ** 2, 1), index=D.index) + e_on ** 2).where(ok)
        a = np.abs(E5)
        n = np.isfinite(E5).sum(1)
        D["bv"] = (pd.Series(np.nansum(a[:, 1:] * a[:, :-1], 1) * (math.pi / 2) * n / np.maximum(n - 1, 1),
                             index=D.index) + e_on ** 2).where(ok)
        D["rs_neg"] = pd.Series(np.nansum(np.where(E5 < 0, E5 ** 2, 0), 1), index=D.index).where(ok)
        D["rs_pos"] = pd.Series(np.nansum(np.where(E5 > 0, E5 ** 2, 0), 1), index=D.index).where(ok)
        D["rq"] = pd.Series(n / 3 * np.nansum(E5 ** 4, 1), index=D.index).where(ok)
        e = D["ret"] - b * rm
        D["ret_total"] = D["ret"]
        D["ret"] = e
        D["r2"] = e ** 2
        mk = masks[sym] if sym in masks else pd.Series(False, index=D.index)
        Tg = targets(D.assign(rv=D["rv"].where(~mk), r2=D["r2"].where(~mk)))
        X = pd.concat([common_features(D, mask=mk), Tg], axis=1)
        X["beta"] = b
        X["masked"] = mk
        X["ldvol"] = np.log((D["close"] * D["volume"]).rolling(20, min_periods=10).median())
        X["lprice"] = np.log(D["close"])
        # point-in-time S&P 500 membership at t (forecast origins only for members)
        inm = mem.reindex(D.index, method="ffill")
        X["member"] = [isinstance(v, list) and sym in v for v in inm]
        X["asset"] = sym
        X = X[D["close"].notna()]
        out.append(X)
    P = pd.concat(out)
    E = build_etf()
    spy = E[E["asset"] == "SPY"][["rv_d", "rv_w", "rv_m", "lvix", "ew5", "lr"]]
    spy = spy.rename(columns={"lvix": "mkt_lvix_raw"}).add_prefix("mkt_").rename(columns={"mkt_mkt_lvix_raw": "lvix"})
    return P.join(spy, how="left")


def build(classes=CLASSES):
    os.makedirs(DATA.CACHE, exist_ok=True)
    m = DATA.load_manifest()
    fns = {"crypto": build_crypto, "etf": build_etf, "index": build_index, "stock": build_stock}
    for cls, fn in ((c, fns[c]) for c in classes):
        P = fn()
        P.index.name = "date"
        P = P.reset_index().set_index(["asset", "date"]).sort_index()
        f32 = P.select_dtypes("float64").columns
        P[f32] = P[f32].astype("float32")
        out = os.path.join(DATA.CACHE, f"panel_{cls}.parquet")
        P.to_parquet(out)
        m.setdefault("panels", {})[cls] = DATA.sha(out)
        print(f"{cls}: {P.index.get_level_values(0).nunique()} assets, {len(P):,} asset-days", flush=True)
    DATA.save_manifest(m)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(tuple(sys.argv[2].split(",")) if len(sys.argv) > 2 else CLASSES)
