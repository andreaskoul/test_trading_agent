"""Replica of TrendSpider's "SSO Opus 5.5 Swing 15m" and its pre-registered reads (research/trendspider/PREREG.md).

    python3 research/trendspider/replica.py calibrate   # in-sample 2022-03-24 .. 2026-11-03: the four ambiguity variants
    python3 research/trendspider/replica.py read VARIANT  # once: out-of-sample, robustness grid, PBO, other ETFs

Bars come from download.py (.cache/trendspider). Returns are simple; Sharpe uses daily returns, rf = 0 for every
series alike, annualised with sqrt(252). Results are written to research/trendspider/results/.
"""
import itertools, json, math, os, sys
import numpy as np
import pandas as pd

CACHE, OUT = ".cache/trendspider", "research/trendspider/results"
IS0, IS1 = "2022-03-24", "2026-11-03"
OOS0, OOS1 = "2016-03-01", "2022-03-23"
P0 = dict(fast=50, slow=200, adx_n=10, adx_min=20.0, brk_n=14, volA=1.0, volB=0.5, rsi_n=14, rsi_min=50.0,
          stop=0.035, target=0.15, trail=0.07, t1=25, t2=60, t2_pnl=0.01)
PAGE = dict(total=1.53, win=0.40, avg=0.0096, dd=-0.125)


def load(sym):
    df = pd.read_csv(f"{CACHE}/{sym}_15m.csv", parse_dates=["ts_utc"])
    df["ts"] = df.ts_utc.dt.tz_convert("America/New_York")
    df["day"] = df.ts.dt.date
    return df.reset_index(drop=True)


def wilder(x, n):
    return pd.Series(x).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


def indicators(df, p):
    c, h, l, v = (df[k].to_numpy(float) for k in ("close", "high", "low", "volume"))
    cs = pd.Series(c)
    sma_f, sma_s = cs.rolling(p["fast"]).mean().to_numpy(), cs.rolling(p["slow"]).mean().to_numpy()
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - pc), np.abs(l - pc)], axis=1)
    up, dn = np.r_[0, np.diff(h)], np.r_[0, -np.diff(l)]
    pdm, ndm = np.where((up > dn) & (up > 0), up, 0.0), np.where((dn > up) & (dn > 0), dn, 0.0)
    atr = wilder(tr, p["adx_n"])
    pdi, ndi = 100 * wilder(pdm, p["adx_n"]) / atr, 100 * wilder(ndm, p["adx_n"]) / atr
    adx = wilder(100 * np.abs(pdi - ndi) / np.maximum(pdi + ndi, 1e-12), p["adx_n"])
    hh = pd.Series(h).rolling(p["brk_n"]).max().shift(1).to_numpy()
    vs = pd.Series(v).rolling(20).mean().to_numpy()
    tp = (h + l + c) / 3
    g = df["day"]
    vwap = (pd.Series(tp * v).groupby(g).cumsum() / pd.Series(v).groupby(g).cumsum()).to_numpy()
    d = np.diff(c, prepend=np.nan)
    rs = wilder(np.where(d > 0, d, 0.0), p["rsi_n"]) / np.maximum(wilder(np.where(d < 0, -d, 0.0), p["rsi_n"]), 1e-12)
    rsi = 100 - 100 / (1 + rs)
    same_day = np.r_[False, (g.to_numpy()[1:] == g.to_numpy()[:-1])]
    return dict(c=c, sma_f=sma_f, sma_s=sma_s, adx=adx, hh=hh, vs=vs, vwap=vwap, rsi=rsi, v=v, same_day=same_day)


def signal(df, p, vol_mode, cross_mode):
    x = indicators(df, p)
    k = (lambda f: 1 + f) if vol_mode == "plus" else (lambda f: f)   # "by at least X%": (1+X)·SMA, or X·SMA
    filt = (x["sma_f"] > x["sma_s"]) & (x["adx"] > p["adx_min"])
    a = (x["c"] > x["hh"]) & (x["v"] >= k(p["volA"]) * x["vs"])
    diff = x["vwap"] - x["c"] if cross_mode == "vwap_over" else x["c"] - x["vwap"]
    cross = (diff > 0) & (np.r_[np.nan, diff[:-1]] <= 0) & x["same_day"]
    b = cross & (x["rsi"] > p["rsi_min"]) & (x["v"] >= k(p["volB"]) * x["vs"])
    return np.nan_to_num(filt & (a | b)).astype(bool)


def simulate(df, sig, p, cost):
    """Signal on bar i's close -> fill at bar i+1's open; exits judged on closes, filled at the next open."""
    o, c = df.open.to_numpy(float), df.close.to_numpy(float)
    n = len(c)
    eq = np.empty(n)
    cash, units, entry, peak, nbar, pending = 1.0, 0.0, 0.0, 0.0, 0, None
    trades = []
    for i in range(n):
        if pending == "buy":
            entry = o[i] * (1 + cost); units = cash / entry; cash = 0.0; peak = c[i]; nbar = 0; ent_i = i
        elif pending == "sell":
            px = o[i] * (1 - cost); cash = units * px; trades.append((ent_i, i, px / entry - 1)); units = 0.0
        pending = None
        if units:
            nbar += 1
            peak = max(peak, c[i])
            pnl = c[i] / entry - 1
            if (pnl < -p["stop"] or pnl > p["target"] or c[i] < peak * (1 - p["trail"])
                    or (nbar >= p["t1"] and pnl < 0) or (nbar >= p["t2"] and pnl < p["t2_pnl"])):
                pending = "sell"
        elif sig[i]:
            pending = "buy"
        eq[i] = cash + units * c[i]
    daily = pd.Series(eq, index=df.ts).groupby(df["day"].to_numpy()).last()
    daily.index = pd.to_datetime(daily.index)
    return daily, trades, eq


def stats(daily, t0=None, t1=None):
    s = daily.loc[t0:t1] if t0 or t1 else daily
    r = s.pct_change().dropna()
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    tot = s.iloc[-1] / s.iloc[0]
    return dict(cagr=tot ** (1 / yrs) - 1, total=tot - 1, vol=r.std() * 252 ** .5,
                sharpe=r.mean() / r.std() * 252 ** .5 if r.std() else 0.0, maxdd=(s / s.cummax() - 1).min(), days=len(r))


def trade_stats(trades, df, t0, t1):
    ts = df.ts.dt.tz_localize(None)
    sel = [t for t in trades if pd.Timestamp(t0) <= ts.iloc[t[0]] <= pd.Timestamp(t1) + pd.Timedelta(days=1)]
    r = np.array([t[2] for t in sel]) if sel else np.array([0.0])
    hold = np.array([t[1] - t[0] for t in sel]) if sel else np.array([0])
    return dict(trades=len(sel), win=float((r > 0).mean()), avg=float(r.mean()), med_bars=float(np.median(hold)))


def bench(sym):
    df = load(sym)
    px = df.groupby("day").close.last(); px.index = pd.to_datetime(px.index)
    bh = px / px.iloc[0]
    sig = (px > px.rolling(200).mean()).shift(1).fillna(False).astype(bool)
    tf = (1 + px.pct_change().fillna(0).where(sig, 0.0)).cumprod()
    return bh, tf


def run(sym, p, vm, cm, cost):
    df = load(sym)
    daily, trades, _ = simulate(df, signal(df, p, vm, cm), p, cost)
    return df, daily, trades


def calibrate():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for vm, cm in itertools.product(["plus", "times"], ["vwap_over", "close_over"]):
        df, daily, trades = run("SSO", P0, vm, cm, 0.0)
        s, t = stats(daily, IS0, IS1), trade_stats(trades, df, IS0, IS1)
        dist = abs(math.log((1 + s["total"]) / (1 + PAGE["total"]))) + abs(t["win"] - PAGE["win"])
        rows.append(dict(variant=f"{vm}/{cm}", **s, **t, dist=dist))
    out = pd.DataFrame(rows).sort_values("dist")
    print(out.round(4).to_string(index=False))
    out.to_csv(f"{OUT}/calibration_in_sample.csv", index=False)
    print("replica:", out.iloc[0].variant)


def perturb(rng):
    q = {}
    for k, v in P0.items():
        f = rng.choice([0.8, 1.0, 1.2])
        q[k] = max(2, int(round(v * f))) if isinstance(v, int) else v * f
    if q["fast"] >= q["slow"]:
        q["fast"] = q["slow"] // 4
    return q


def pbo(R, S=16):
    """Probability of backtest overfitting by CSCV (Bailey, Borwein, López de Prado, Zhu 2014). R: T x N returns."""
    T, N = R.shape
    blocks = np.array_split(np.arange(T), S)
    m = np.array([R[b].sum(0) for b in blocks]); q = np.array([(R[b] ** 2).sum(0) for b in blocks])
    n = np.array([len(b) for b in blocks])
    lam = []
    for comb in itertools.combinations(range(S), S // 2):
        i = np.zeros(S, bool); i[list(comb)] = True
        def sr(mask):
            k = n[mask].sum(); mu = m[mask].sum(0) / k
            return mu / np.sqrt(np.maximum(q[mask].sum(0) / k - mu ** 2, 1e-18))
        best = np.argmax(sr(i))
        oos = sr(~i)
        w = (oos < oos[best]).sum() / (N + 1) + 1 / (N + 1) / 2
        lam.append(math.log(w / (1 - w)))
    lam = np.array(lam)
    return float((lam <= 0).mean())


def deflated_sharpe(r, n_trials, sr_trials_sd):
    """Bailey & López de Prado (2014): P(true SR > 0) after selecting the best of n_trials. Daily units."""
    from scipy.stats import norm, skew, kurtosis
    T, sr = len(r), r.mean() / r.std()
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    em = 0.5772156649
    sr0 = 0.0 if n_trials <= 1 else sr_trials_sd * ((1 - em) * norm.ppf(1 - 1 / n_trials) + em * norm.ppf(1 - 1 / (n_trials * math.e)))
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)
    return float(norm.cdf(z)), float(sr0 * 252 ** .5)


def read(variant):
    vm, cm = variant.split("/")
    os.makedirs(OUT, exist_ok=True)
    res = {"variant": variant, "windows": {"in_sample": [IS0, IS1], "out_of_sample": [OOS0, OOS1]}}
    spy_bh, spy_tf = bench("SPY"); sso_bh, sso_tf = bench("SSO")
    tab = {}
    for cost in (0.0002, 0.0):
        df, daily, trades = run("SSO", P0, vm, cm, cost)
        for w, (a, b) in res["windows"].items():
            tab[f"replica cost {cost*1e4:.0f}bp | {w}"] = {**stats(daily, a, b), **trade_stats(trades, df, a, b)}
        if cost:
            rep_daily = daily
            ex = daily.loc[OOS0:OOS1]; ex = ex[(ex.index.year != 2020)]
            r = ex.pct_change().dropna(); r = r[r.index.year != 2020]
            tab["replica cost 2bp | out_of_sample ex-2020"] = dict(sharpe=r.mean() / r.std() * 252 ** .5,
                                                                    cagr=(1 + r).prod() ** (252 / len(r)) - 1)
            for y in range(2016, 2027):
                s = daily.loc[str(y)]
                tab[f"replica cost 2bp | {y}"] = dict(ret=s.iloc[-1] / daily.loc[:str(y - 1)].iloc[-1] - 1 if y > 2016 else s.iloc[-1] / s.iloc[0] - 1)
    for name, ser in [("SPY buy&hold", spy_bh), ("SPY >200d else cash", spy_tf), ("SSO buy&hold", sso_bh), ("SSO >200d else cash", sso_tf)]:
        for w, (a, b) in res["windows"].items():
            tab[f"{name} | {w}"] = stats(ser, a, b)
        for y in range(2016, 2027):
            s = ser.loc[str(y)]
            tab[f"{name} | {y}"] = dict(ret=s.iloc[-1] / ser.loc[:str(y - 1)].iloc[-1] - 1 if y > 2016 else s.iloc[-1] / s.iloc[0] - 1)
    res["table"] = tab
    oos = tab["replica cost 2bp | out_of_sample"]["sharpe"]
    res["verdict_oos"] = bool(oos > tab["SPY buy&hold | out_of_sample"]["sharpe"] and oos > tab["SSO >200d else cash | out_of_sample"]["sharpe"])

    # robustness grid and PBO
    rng = np.random.default_rng(20261104)
    df = load("SSO")
    cols, oos_sr, is_sr = [rep_daily.pct_change()], [], []
    spy_oos = tab["SPY buy&hold | out_of_sample"]["sharpe"]
    for k in range(300):
        q = perturb(rng)
        d, _, _ = simulate(df, signal(df, q, vm, cm), q, 0.0002)
        cols.append(d.pct_change())
        oos_sr.append(stats(d, OOS0, OOS1)["sharpe"]); is_sr.append(stats(d, IS0, IS1)["sharpe"])
    R = pd.concat(cols, axis=1).loc[OOS0:IS1].dropna().to_numpy()
    res["grid"] = dict(n=300, share_oos_beats_spy=float(np.mean(np.array(oos_sr) > spy_oos)),
                       oos_sharpe_median=float(np.median(oos_sr)), oos_sharpe_p10_p90=[float(np.percentile(oos_sr, 10)), float(np.percentile(oos_sr, 90))],
                       is_sharpe_median=float(np.median(is_sr)), corr_is_oos=float(np.corrcoef(is_sr, oos_sr)[0, 1]),
                       pbo=pbo(R))
    # deflated Sharpe of the replica's in-sample record, if it was the best of N tries
    r_is = rep_daily.loc[IS0:IS1].pct_change().dropna().to_numpy()
    sd = float(np.std(is_sr)) / 252 ** .5
    res["deflated_sharpe_in_sample"] = {str(n): dict(zip(["p_true_sr_gt_0", "sr0_annual"], deflated_sharpe(r_is, n, sd))) for n in (1, 10, 100, 1000)}
    # other instruments, descriptive
    res["other_etfs"] = {}
    for sym in ("SPY", "QLD", "UPRO"):
        if os.path.exists(f"{CACHE}/{sym}_15m.csv"):
            d_, daily, trades = run(sym, P0, vm, cm, 0.0002)
            bh, tf = bench(sym)
            res["other_etfs"][sym] = {w: dict(replica=stats(daily, a, b), buyhold=stats(bh, a, b), trend200=stats(tf, a, b))
                                     for w, (a, b) in res["windows"].items()}
    json.dump(res, open(f"{OUT}/read.json", "w"), indent=1, default=float)
    pd.DataFrame(tab).T.to_csv(f"{OUT}/read_table.csv")
    print(json.dumps({k: res[k] for k in ("verdict_oos", "grid", "deflated_sharpe_in_sample")}, indent=1, default=float))


if __name__ == "__main__":
    {"calibrate": calibrate, "read": lambda: read(sys.argv[2])}[sys.argv[1]]()
