"""Technicals desk · historical test of the rule policy before it is pre-registered (draft Amendment 8).

No LLM is involved, so the past is usable. The news view is replaced by a deterministic stand-in: a
large-cap NEWS DAY is a session whose open gaps at least 1.5 ATR from the previous close on at least twice
the usual volume (mostly earnings and guidance), and the view is the gap's direction. The fund's timing is
reproduced exactly: the view enters at the close of the first Thursday after the news day (the Wednesday
decision, the Thursday trade), with the Position Lifecycle book's horizon for earnings-type news,
H = 15 - news age, and its residual-volatility unit W = sigma_e x sqrt(H).

Books, per event, all on beta-hedged residual returns e = r - beta x r_SPY, 5 bp per side on every trade:
* lifecycle  enter in full at the Thursday close; exit at -2 W, +3 W or the horizon (Amendment 7 barriers)
* technical  the Technical Timing book's rule policy (fund/tech_policy.py)
* placebo    the same policy on a map whose zones are moved to random distances (count, strength and
             scale kept): if the levels carry information, technical must beat placebo
plus a small, pre-declared parameter grid for the policy, chosen on 2012-2021 only and read once on
2022-2025 (the holdout).

    python fund/backtest_levels.py download     # daily bars, S&P 500 members 2010-2025 (yfinance) -> .cache/bt/
    python fund/backtest_levels.py run          # events, books, grid -> .cache/bt/trades.parquet
    python fund/backtest_levels.py report       # -> reports/research/technicals_backtest.md

Caveat, stated in the report: yfinance has no bars for most delisted members, so the sample leans to
survivors; this inflates every book's long-side return alike and is controlled by the paired comparisons.
"""

import json
import math
import os
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import levels as LV                    # noqa: E402
import tech_policy as TP               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BT = os.path.join(ROOT, ".cache", "bt")
os.makedirs(BT, exist_ok=True)
START, END = "2010-01-01", "2026-01-01"
FIT = ("2012-01-01", "2021-12-31")
HOLD = ("2022-01-01", "2025-12-31")
GAP_ATR, RELVOL, MIN_PX = 1.5, 2.0, 5.0
H_TYPE, H_MIN, H_MAX, STALE_AT = 15, 3, 20, 2      # Amendment 7: earnings / guidance horizon, clamps, stale rule
STOP_K, TARGET_K, SPAN, FLOOR = 2.0, 3.0, 60, 0.75
COST = 5e-4
GRID = {"RR_SKIP": (0.5, 1.0, 1.5), "TRAIL_ATR": (2.5, 3.0, 4.0), "STOP_MAX_W": (2.0, 2.5, 3.0)}
BASE = {"RR_SKIP": 1.0, "TRAIL_ATR": 3.0, "STOP_MAX_W": 2.5}          # the literature defaults in the plan


# ----------------------------------------------------------------------------- data
@lru_cache(None)
def members():
    mem = pd.read_csv(os.path.join(ROOT, "data/raw/stocks/sp500_membership.csv"), parse_dates=["date"])
    mem = mem[(mem.date >= pd.Timestamp(START) - pd.Timedelta(days=400)) & (mem.date < END)]
    return mem


def download():
    import yfinance as yf
    mem = members()
    tick = sorted({t for s in mem.tickers for t in s.split(",")})
    print(f"{len(tick)} tickers were S&P 500 members at some point since {START}")
    out = os.path.join(BT, "bars")
    os.makedirs(out, exist_ok=True)
    todo = [t for t in tick + ["SPY"] if not os.path.exists(os.path.join(out, f"{t}.parquet"))]
    for k in range(0, len(todo), 80):
        chunk = todo[k:k + 80]
        ymap = {t: t.replace(".", "-") for t in chunk}
        for attempt in range(3):
            try:
                df = yf.download(list(ymap.values()), start=START, end=END, auto_adjust=False, progress=False,
                                 threads=True, group_by="ticker")
                break
            except Exception as e:
                print("retry", e); time.sleep(10)
        else:
            continue
        for t, y in ymap.items():
            try:
                g = df[y] if isinstance(df.columns, pd.MultiIndex) else df
            except KeyError:
                continue
            g = g.rename(columns=str.lower).dropna(subset=["close"])
            if len(g) < 300:
                continue
            g.index = pd.to_datetime(g.index).tz_localize(None)
            g[["open", "high", "low", "close", "adj close", "volume"]].to_parquet(os.path.join(out, f"{t}.parquet"))
        print(f"downloaded {min(k + 80, len(todo))}/{len(todo)}", flush=True)
    have = len([f for f in os.listdir(out) if f.endswith(".parquet")])
    print(f"bars for {have} tickers in {out}")


BAD_RANGE = 250      # a 52-week range above 250 ATR is a corrupt history (a reused ticker), not a stock


@lru_cache(None)
def bad_tickers():
    """Tickers whose yfinance history is not one company's (reused symbols: CPWR, AMCR, PARA, EP, ...)."""
    p = os.path.join(BT, "bad_tickers.json")
    if os.path.exists(p):
        return frozenset(json.load(open(p)))
    bad = []
    for f in sorted(os.listdir(os.path.join(BT, "bars"))):
        b = pd.read_parquet(os.path.join(BT, "bars", f))
        atr = LV.Chart(b).atr
        r = (b["high"].rolling(252).max() - b["low"].rolling(252).min()) / atr
        if float(r.max()) > BAD_RANGE:
            bad.append(f[:-8])
    json.dump(bad, open(p, "w"))
    return frozenset(bad)


def load(t):
    p = os.path.join(BT, "bars", f"{t}.parquet")
    if not os.path.exists(p) or (t != "SPY" and t in bad_tickers()):
        return None
    return pd.read_parquet(p)


# ----------------------------------------------------------------------------- context shared by all tickers
@lru_cache(None)
def context():
    """SPY returns and its 200-day regime; breadth = share of members (that day) above their 50-day average."""
    p = os.path.join(BT, "context.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    spy = load("SPY")
    mem = members()
    m_by_day = mem.set_index("date").tickers.map(lambda s: set(s.split(",")))
    above, count = None, None
    for f in sorted(os.listdir(os.path.join(BT, "bars"))):
        t = f[:-8]
        if t == "SPY":
            continue
        b = load(t)
        if b is None:
            continue
        a = (b["close"] > b["close"].rolling(50, min_periods=50).mean()).astype(float)
        ok = b["close"].rolling(50, min_periods=50).mean().notna().astype(float)
        days = m_by_day.reindex(b.index, method="ffill")
        isin = days.map(lambda s: t in s if isinstance(s, set) else False).astype(float)
        above = (a * isin) if above is None else above.add(a * isin, fill_value=0)
        count = (ok * isin) if count is None else count.add(ok * isin, fill_value=0)
    ctx = pd.DataFrame({"spy_ret": spy["adj close"].pct_change(),
                        "spy_above_200": spy["close"] > spy["close"].rolling(200).mean(),
                        "breadth50": (above / count).reindex(spy.index)})
    ctx.to_parquet(p)
    return ctx


# ----------------------------------------------------------------------------- one ticker
def welch_beta(r, rm):
    lo, hi = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
    w = r.clip(lower=lo, upper=hi)
    v = rm[w.notna()].var()
    b = w.cov(rm) / v if v and np.isfinite(v) else 1.0
    return (2 / 3) * (b if np.isfinite(b) else 1.0) + 1 / 3


def placebo_map(lm, rng):
    """Zones moved to random distances: each zone's distance from the close is scaled by U(0.5, 1.5) and
    given a random sign; count, strength, width and the news-day candle are kept."""
    c = lm["close"]
    Z = []
    for z in lm["zones"]:
        d = (z["mid"] - c) * rng.uniform(0.5, 1.5) * (1 if rng.random() < 0.5 else -1)
        w = (z["hi"] - z["lo"]) / 2
        Z.append({**z, "mid": c + d, "lo": c + d - w, "hi": c + d + w})
    Z.sort(key=lambda z: z["mid"])
    return {**lm, "zones": Z}


def run_ticker(t):
    b = load(t)
    if b is None or t == "SPY":
        return []
    ctx = context()
    mem = members()
    first_in = mem[mem.tickers.str.contains(rf"(?:^|,){t.replace('.', '[.]')}(?:,|$)", regex=True)].date
    if not len(first_in):
        return []
    in_lo, in_hi = first_in.min(), first_in.max()
    b = b[b.index.isin(ctx.index)]
    r = b["adj close"].pct_change()
    rm = ctx["spy_ret"].reindex(b.index)
    charts = {1: LV.Chart(b, 1), -1: LV.Chart(b, -1)}
    chL = charts[1]
    gap = (b["open"] - b["close"].shift(1)) / chL.atr.shift(1)
    ev_days = b.index[(gap.abs() >= GAP_ATR) & (chL.relvol >= RELVOL) & (b["close"] >= MIN_PX)
                      & (b.index >= FIT[0]) & (b.index <= HOLD[1]) & (b.index >= in_lo) & (b.index <= in_hi)]
    idx = {d: i for i, d in enumerate(b.index)}
    out = []
    last_entry = None
    for j_day in ev_days:
        j = idx[j_day]
        side = 1 if gap.iloc[j] > 0 else -1
        # entry: the first Thursday strictly after the news day (Wednesday decision, Thursday close trade)
        k = j + 1
        while k < len(b) and b.index[k].dayofweek != 3:
            k += 1
        if k >= len(b) - 25 or k - j > 7:
            continue
        if last_entry is not None and k <= last_entry:      # one position per name at a time
            continue
        age = k - j
        H_raw = H_TYPE - age
        if H_raw <= STALE_AT:
            continue
        H = int(min(max(H_raw, H_MIN), H_MAX))
        if k < 260:
            continue
        beta = welch_beta(r.iloc[k - 251:k + 1], rm.iloc[k - 251:k + 1])
        e = (r - beta * rm)
        e_hist = e.iloc[:k + 1].dropna()
        sig = max(float(e_hist.ewm(span=SPAN).std().iloc[-1]), FLOOR * float(e_hist.iloc[-252:].std()))
        W = sig * math.sqrt(H)
        pz = side * float(e.iloc[j:k + 1].sum()) / (sig * math.sqrt(age + 1))
        ch = charts[side]
        span = H + TP.P["WAIT_DAYS"] + 1
        days = b.index[k:k + span + 1]
        try:
            maps = [ch.levels(d, event_day=j_day) for d in days]
            prev0 = ch.levels(b.index[k - 1], event_day=j_day if k - 1 >= j else None)
        except (ValueError, KeyError):
            continue
        es = (side * e.iloc[k + 1:k + span + 1]).to_numpy()
        rg = ctx.loc[days[0]]
        rec = {"ticker": t, "news_day": j_day, "entry_day": days[0], "side": side, "age": age, "H": H, "W": W,
               "beta": beta, "priced_z": pz, "gap_atr": float(gap.iloc[j]), "year": days[0].year,
               "breadth50": float(rg["breadth50"]) if np.isfinite(rg["breadth50"]) else None,
               "spy_above_200": bool(rg["spy_above_200"])}
        # lifecycle book: full at entry, -2W / +3W / horizon
        R, pnl, mae, mfe, why = 0.0, 0.0, 0.0, 0.0, "horizon"
        for s in range(H):
            R += es[s]; pnl += es[s]
            mae, mfe = min(mae, R), max(mfe, R)
            if R <= -STOP_K * W:
                why = "stop"; break
            if R >= TARGET_K * W:
                why = "target"; break
        rec.update(lc_pnl=pnl - 2 * COST, lc_exit=why, lc_days=s + 1, lc_mae_w=mae / W, lc_mfe_w=mfe / W,
                   full_pnl=float(es[:H].sum()) - 2 * COST)
        # technical policy: the defaults, the grid, and the placebo on the defaults
        rng = np.random.default_rng(zlib.crc32(f"{t}{j_day.date()}".encode()))
        pmaps = [placebo_map(m, rng) for m in maps]
        pprev = placebo_map(prev0, rng)
        variants = [("tech", BASE, maps, prev0), ("placebo", BASE, pmaps, pprev)]
        for a in GRID["RR_SKIP"]:
            for tr in GRID["TRAIL_ATR"]:
                for sm in GRID["STOP_MAX_W"]:
                    g = {"RR_SKIP": a, "TRAIL_ATR": tr, "STOP_MAX_W": sm}
                    if g != BASE:
                        variants.append((f"g_{a}_{tr}_{sm}", g, maps, prev0))
        for name, g, M, pv in variants:
            res = simulate(M, pv, es, W, H, pz, g, rg)
            for kk, vv in res.items():
                rec[f"{name}_{kk}"] = vv
        out.append(rec)
        last_entry = k + rec["lc_days"]
    return out


def simulate(maps, prev0, es, W, H, pz, g, rg):
    """Run the rule policy over the maps (maps[0] = the entry close). Returns P&L per planned position
    (residual, net of 5 bp per side on every change of size), exposure, actions."""
    old = {k: TP.P[k] for k in g}
    TP.P.update({k: v for k, v in g.items() if k != "TRAIL_ATR"})
    try:
        lm0 = maps[0]
        W_px = W * abs(lm0["close"])
        plan = TP.plan_entry(lm0, W_px, pz, prev0)
        reg = TP.regime(rg["spy_above_200"], rg["breadth50"] if np.isfinite(rg["breadth50"]) else None, lm0.get("bbw_pct"))
        reg["trail_atr"] = g["TRAIL_ATR"] - (0.5 if reg["momentum"] else 0.0)
        lot = TP.Lot(plan, lm0, W, H, reg)
        frac = lot.frac
        pnl, cost, expo, R, mae, mfe = 0.0, COST * frac, 0.0, 0.0, 0.0, 0.0
        acts, last = [], plan["action"]
        prev = lm0
        for s in range(1, len(maps)):
            if frac == 0 and not lot.waiting and lot.entered is False and s > 1:
                break
            x = es[s - 1]
            pnl += frac * x
            expo += frac
            if lot.entered:
                R += x
                mae, mfe = min(mae, R), max(mfe, R)
            steps = lot.step(maps[s], R, prev, pz)
            for nf, why in steps:
                cost += COST * abs(nf - frac)
                frac = nf
                acts.append(why)
                last = why
            prev = maps[s]
            if lot.entered and frac == 0:
                break
            if not lot.waiting and not lot.entered and s > TP.P["WAIT_DAYS"]:
                break
        if frac > 0:
            cost += COST * frac
            last = "end"
        return {"pnl": pnl - cost, "expo": expo, "plan": plan["action"], "exit": last, "n_act": len(acts),
                "mae_w": mae / W, "mfe_w": mfe / W, "rr": plan["rr"], "risk_w": plan["risk_w"]}
    finally:
        TP.P.update(old)


def run():
    context()
    tick = sorted(f[:-8] for f in os.listdir(os.path.join(BT, "bars")) if f.endswith(".parquet") and f != "SPY.parquet")
    rows = []
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as ex:
        for n, res in enumerate(ex.map(run_ticker, tick, chunksize=4)):
            rows += res
            if n % 50 == 0:
                print(f"{n}/{len(tick)} tickers, {len(rows)} events", flush=True)
    T = pd.DataFrame(rows)
    T.to_parquet(os.path.join(BT, "trades.parquet"))
    print(f"{len(T)} events -> {BT}/trades.parquet")


# ----------------------------------------------------------------------------- report
def weekly_t(x: pd.Series, by: pd.Series):
    """Mean per event, and a t-statistic on weekly means (events of one Thursday are not independent)."""
    w = x.groupby(by).mean()
    return float(x.mean()), float(w.mean() / (w.std(ddof=1) / math.sqrt(len(w)))) if len(w) > 2 and w.std() > 0 else float("nan"), len(w)


def report():
    T = pd.read_parquet(os.path.join(BT, "trades.parquet"))
    T["week"] = T["entry_day"]
    names = [c[:-4] for c in T.columns if c.endswith("_pnl") and c not in ("lc_pnl", "full_pnl")]
    L = ["# Technical Timing book: historical test of the rule policy",
         "",
         f"Generated by `fund/backtest_levels.py` on {pd.Timestamp.now(tz='UTC'):%Y-%m-%d}. No LLM involved.",
         "",
         "**Events.** S&P 500 members (at the time), news days = open gaps ≥ 1.5 ATR on ≥ 2× usual volume, "
         "view = gap direction, entered at the first Thursday close after the news day (the fund's timing), "
         "horizon 15 − news age sessions, residual returns vs SPY (Welch beta), 5 bp per side on every trade. "
         "P&L is per planned position, in bp of its notional. Survivorship: yfinance lacks most delisted "
         "members; the comparisons are paired, event by event, so this affects all books alike.",
         ""]
    for lab, (lo, hi) in (("Fit 2012–2021", FIT), ("Holdout 2022–2025", HOLD)):
        S = T[(T.entry_day >= lo) & (T.entry_day <= hi)]
        L += [f"## {lab}: {len(S):,} events over {S.week.nunique()} Thursdays", "",
              "| book | mean bp / event | t (weekly) | hit rate | mean exposure (frac × days) | bp per exposure-day | vs lifecycle: mean bp, t |",
              "|---|---:|---:|---:|---:|---:|---:|"]
        rows = [("hold full to horizon (no barriers)", S["full_pnl"], None), ("Position Lifecycle barriers", S["lc_pnl"], S["lc_days"].astype(float))]
        rows += [("Technical Timing (plan defaults)", S["tech_pnl"], S["tech_expo"]), ("Placebo levels", S["placebo_pnl"], S["placebo_expo"])]
        for nm, x, ex in rows:
            m, tt, _ = weekly_t(x, S.week)
            d = x - S["lc_pnl"]
            md, td, _ = weekly_t(d, S.week)
            L.append(f"| {nm} | {m * 1e4:+.1f} | {tt:+.2f} | {(x > 0).mean():.1%} | "
                     f"{'' if ex is None else f'{ex.mean():.2f}'} | {'' if ex is None else f'{x.sum() / max(ex.sum(), 1e-9) * 1e4:+.2f}'} | "
                     f"{'' if nm == 'Position Lifecycle barriers' else f'{md * 1e4:+.1f}, {td:+.2f}'} |")
        m, tt, _ = weekly_t(S["tech_pnl"] - S["placebo_pnl"], S.week)
        L += ["", f"**Levels vs placebo (paired):** {m * 1e4:+.1f} bp per event, t {tt:+.2f}.", ""]
        L += ["Entry decisions (Technical Timing, defaults), with what the full hold would have earned on those events:", "",
              "| decision | share | full-hold bp | lifecycle bp | technical bp |", "|---|---:|---:|---:|---:|"]
        for a, G in S.groupby("tech_plan"):
            L.append(f"| {a} | {len(G) / len(S):.1%} | {G.full_pnl.mean() * 1e4:+.1f} | {G.lc_pnl.mean() * 1e4:+.1f} | {G.tech_pnl.mean() * 1e4:+.1f} |")
        L += ["", "Exit reasons (Technical Timing):", "",
              ", ".join(f"{k} {v:.1%}" for k, v in S["tech_exit"].value_counts(normalize=True).items()), ""]
        L += ["By side:", "", "| side | n | lifecycle bp | technical bp | placebo bp |", "|---|---:|---:|---:|---:|"]
        for sd, G in S.groupby("side"):
            L.append(f"| {'long' if sd > 0 else 'short'} | {len(G)} | {G.lc_pnl.mean() * 1e4:+.1f} | {G.tech_pnl.mean() * 1e4:+.1f} | {G.placebo_pnl.mean() * 1e4:+.1f} |")
        L.append("")
    # grid: chosen on the fit period only, read once on the holdout
    F = T[(T.entry_day >= FIT[0]) & (T.entry_day <= FIT[1])]
    Hd = T[(T.entry_day >= HOLD[0]) & (T.entry_day <= HOLD[1])]
    cand = ["tech"] + [n for n in names if n.startswith("g_")]
    score = {n: weekly_t(F[f"{n}_pnl"] - F["lc_pnl"], F.week)[1] for n in cand}
    best = max(score, key=lambda n: score[n])
    def lab(n):
        return "plan defaults (RR_SKIP 1.0, TRAIL 3.0, STOP_MAX 2.5)" if n == "tech" else \
            "RR_SKIP {}, TRAIL {}, STOP_MAX {}".format(*n.split("_")[1:])
    L += ["## Parameter grid (27 settings, chosen on 2012–2021 by the paired t vs the lifecycle barriers)", "",
          "| setting | fit: vs lifecycle bp, t | holdout: vs lifecycle bp, t |", "|---|---:|---:|"]
    for n in sorted(cand, key=lambda n: -score[n])[:8]:
        mf, tf, _ = weekly_t(F[f"{n}_pnl"] - F["lc_pnl"], F.week)
        mh, th, _ = weekly_t(Hd[f"{n}_pnl"] - Hd["lc_pnl"], Hd.week)
        L.append(f"| {lab(n)}{' **(chosen)**' if n == best else ''} | {mf * 1e4:+.1f}, {tf:+.2f} | {mh * 1e4:+.1f}, {th:+.2f} |")
    L += ["", f"Chosen on the fit period: **{lab(best)}**. Its holdout row is the one out-of-sample read; "
          "27 settings were tried, so a fit-period t below ~2.9 (Bonferroni over 27) is not evidence by itself.", ""]
    Fq = F.assign(q=pd.qcut(F.priced_z, 5, labels=False))
    L += ["## Exploratory, fit period only: does the market's follow-through after the news matter?", "",
          "Priced-in z = the residual move from the close before the news day to the entry close, in the view's "
          "direction, divided by sigma x sqrt(days). Full hold to the horizon, no barriers. This was looked at "
          "after the policy test, so it is a hypothesis for the holdout and for pre-registration, not a result.", "",
          "| quintile | priced-in z range | events | mean bp / event | t (weekly) |", "|---:|---|---:|---:|---:|"]
    for q, G in Fq.groupby("q"):
        m, tt, _ = weekly_t(G.full_pnl, G.week)
        L.append(f"| {q + 1} | {G.priced_z.min():+.2f} to {G.priced_z.max():+.2f} | {len(G)} | {m * 1e4:+.1f} | {tt:+.2f} |")
    L.append("")
    out = os.path.join(ROOT, "reports", "research", "technicals_backtest.md")
    open(out, "w").write("\n".join(L) + "\n")
    json.dump({"chosen": best, "fit_t": score[best]}, open(os.path.join(BT, "chosen.json"), "w"))
    print("\n".join(L))


# ----------------------------------------------------------------------------- do levels interrupt moves? (Osler's test)
def touch_ticker(t):
    """Every 5th session 2012-2025: the nearest strong zone above and below the close (0.25-4 ATR away), and a
    placebo level at a random distance of the same scale with no strong zone within 0.5 ATR. Follow the next
    20 sessions to the first touch, then measure the close 1, 3 and 5 sessions after the touch relative to the
    level, in ATR, signed so that positive = the level held (price turned back from resistance, bounced off
    support). Also the nearest major round number. If the levels carry information, real > placebo."""
    b = load(t)
    if b is None or t == "SPY":
        return []
    ch = LV.Chart(b, 1)
    H_, L_, C_ = b["high"].to_numpy(), b["low"].to_numpy(), b["close"].to_numpy()
    out = []
    rng = np.random.default_rng(zlib.crc32(t.encode()))
    ix = [i for i in range(300, len(b) - 30, 5) if FIT[0] <= str(b.index[i].date()) <= HOLD[1]]
    for i in ix:
        try:
            lm = ch.levels(b.index[i])
        except (ValueError, KeyError):
            continue
        c, a = lm["close"], lm["atr"]
        strong = [z for z in lm["zones"] if z["strength"] >= LV.P["STRONG"]]
        for d in (1, -1):                                   # +1 resistance above, -1 support below
            cand = [z for z in strong if 0.25 <= d * ((z["lo"] if d > 0 else z["hi"]) - c) / a <= 4]
            if not cand:
                continue
            z = min(cand, key=lambda z: d * ((z["lo"] if d > 0 else z["hi"]) - c))
            lvl = z["lo"] if d > 0 else z["hi"]
            dist = d * (lvl - c) / a
            pl = None
            for _ in range(20):
                pd_ = dist * rng.uniform(0.6, 1.4)
                if not 0.25 <= pd_ <= 4:
                    continue
                cand_px = c + d * pd_ * a
                if all(abs(cand_px - q["mid"]) > 0.5 * a and not (q["lo"] - 0.5 * a <= cand_px <= q["hi"] + 0.5 * a) for q in strong):
                    pl = cand_px; break
            rn = [r["price"] for r in lm["rounds"] if r["major"] and 0.25 <= d * (r["price"] - c) / a <= 4]
            rn = min(rn, key=lambda x: abs(x - c)) if rn else None
            for kind, level in (("zone", lvl), ("placebo", pl), ("round", rn)):
                if level is None:
                    continue
                hit = None
                for s in range(i + 1, i + 21):
                    if (d > 0 and H_[s] >= level) or (d < 0 and L_[s] <= level):
                        hit = s; break
                if hit is None or hit + 5 >= len(C_):
                    continue
                rec = {"ticker": t, "date": b.index[i], "dir": d, "kind": kind, "dist_atr": d * (level - c) / a,
                       "strength": z["strength"] if kind == "zone" else None, "zkinds": z["kinds"] if kind == "zone" else None,
                       "days_to_touch": hit - i}
                for h in (1, 3, 5):
                    rec[f"hold{h}"] = -d * (C_[hit + h] - level) / a      # + = level held
                rec["close_beyond"] = bool(d * (C_[hit] - level) > 0)   # closed through it on the touch day
                out.append(rec)
    return out


def touch():
    tick = sorted(f[:-8] for f in os.listdir(os.path.join(BT, "bars")) if f.endswith(".parquet") and f != "SPY.parquet")
    rows = []
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as ex:
        for res in ex.map(touch_ticker, tick, chunksize=4):
            rows += res
    T = pd.DataFrame(rows)
    T.to_parquet(os.path.join(BT, "touches.parquet"))
    touch_report()


def touch_report():
    """Zone vs placebo vs round number, compared within cells of the same distance and the same time to the
    touch. (A naive pairing of zone and placebo on the same day is biased: when the placebo lies beyond the
    zone, reaching it selects paths that already ran through the zone.)"""
    T = pd.read_parquet(os.path.join(BT, "touches.parquet"))
    T["week"] = pd.to_datetime(T["date"]).dt.to_period("W").astype(str)
    T["dbin"] = pd.cut(T.dist_atr, [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4])
    T["tbin"] = pd.cut(T.days_to_touch, [0, 1, 2, 4, 8, 20])
    L = ["", "## Do levels interrupt moves? (Osler's test on S&P 500 members, 2012–2025)", "",
         "Every 5th session per stock: the nearest strong zone 0.25–4 ATR above (resistance) and below (support); "
         "a placebo level at a random distance of the same scale with no strong zone within 0.5 ATR; the nearest major "
         "round number. After the first touch within 20 sessions: the close 1, 3 and 5 sessions later relative to the "
         "level, in ATR, signed so that + means the level held.", "",
         "| level | side | touches | closed through on touch day | held +1 | held +3 | held +5 |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for k in ("zone", "placebo", "round"):
        for d, nm in ((1, "resistance"), (-1, "support")):
            G = T[(T.kind == k) & (T.dir == d)]
            L.append(f"| {k} | {nm} | {len(G):,} | {G.close_beyond.mean():.1%} | "
                     + " | ".join(f"{G[f'hold{h}'].mean():+.3f}" for h in (1, 3, 5)) + " |")
    L += ["", "**Zone minus comparison level, within cells of equal distance (7 bins) and time to touch (5 bins), "
          "weighted by zone touches** (ATR; + = strong zones hold better). Each cell: mean over touches / mean of "
          "weekly means (t of the weekly means). The two differ in sign where volatile weeks with many touches "
          "behave unlike quiet ones; either way the magnitudes are hundredths of an ATR.", "",
          "| comparison | side | +1 | +3 | +5 |", "|---|---|---:|---:|---:|"]
    for k in ("placebo", "round"):
        for d, nm in ((1, "resistance"), (-1, "support")):
            cells = []
            for h in (1, 3, 5):
                S = T[(T.dir == d) & T.kind.isin(["zone", k])]
                cm = S.groupby(["dbin", "tbin", "kind"], observed=True)[f"hold{h}"].mean().unstack("kind")
                Z = S[S.kind == "zone"].join(cm[k].rename("cmp"), on=["dbin", "tbin"])
                Z["diff"] = Z[f"hold{h}"] - Z["cmp"]
                Z = Z.dropna(subset=["diff"])
                w = Z["diff"].groupby(Z["week"]).mean()
                _, tt, _ = weekly_t(Z["diff"], Z["week"])
                cells.append(f"{Z['diff'].mean():+.4f} / {w.mean():+.4f} (t {tt:+.1f})")
            L.append(f"| zone − {k} | {nm} | " + " | ".join(cells) + " |")
    Z = T[T.kind == "zone"].copy()
    Z["type"] = np.where(Z.zkinds.str.contains("A"), "with 52w/ATH anchor",
                         np.where(Z.zkinds.str.contains("V") & ~Z.zkinds.str.contains("[HL]"), "volume node only",
                                  np.where(Z.zkinds.str.contains("V"), "pivots + volume node", "pivots only")))
    P_ = T[T.kind == "placebo"].groupby(["dir", "dbin", "tbin"], observed=True)["hold3"].mean().rename("cmp")
    Z = Z.join(P_, on=["dir", "dbin", "tbin"])
    Z["diff3"] = Z["hold3"] - Z["cmp"]
    Z["sbin"] = pd.qcut(Z.strength, 3, labels=["weaker", "middle", "stronger"])
    L += ["", "By zone type and strength, held +3 minus the matched placebo (ATR):", "",
          "| zone | touches | zone − placebo, +3 |", "|---|---:|---:|"]
    for col in ("type", "sbin"):
        for k, G in Z.groupby(col, observed=True):
            x = G["diff3"].dropna()
            wk = G.loc[G["diff3"].notna(), "week"]
            _, tt, _ = weekly_t(x, wk)
            L.append(f"| {k} | {len(G):,} | {x.mean():+.4f} / {x.groupby(wk).mean().mean():+.4f} (t {tt:+.1f}) |")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(ROOT, "reports", "research", "technicals_backtest.md"), "a").write(txt)

def gate():
    """The pre-registered follow-through gate (report section 'Pre-registration'), read once on 2022-2025."""
    T = pd.read_parquet(os.path.join(BT, "trades.parquet"))
    Hd = T[(T.entry_day >= HOLD[0]) & (T.entry_day <= HOLD[1])].copy()
    Hd["passed"] = Hd.priced_z >= 1.5
    L = ["", "## Holdout read of the follow-through gate (2022–2025, once)", "",
         "| group | events | Lifecycle-barrier bp / event | t (weekly) |", "|---|---:|---:|---:|"]
    for k, G in ((True, Hd[Hd.passed]), (False, Hd[~Hd.passed]), ("all", Hd)):
        m, tt, _ = weekly_t(G.lc_pnl, G.entry_day)
        L.append(f"| {'passed (z ≥ 1.5)' if k is True else 'failed (z < 1.5)' if k is False else 'all (Lifecycle book)'} "
                 f"| {len(G):,} | {m * 1e4:+.1f} | {tt:+.2f} |")
    res = {}
    for nm, G in (("all", Hd), ("long", Hd[Hd.side > 0]), ("short", Hd[Hd.side < 0])):
        w = G.groupby(["entry_day", "passed"]).lc_pnl.mean().unstack().dropna()
        sp = w[True] - w[False]
        res[nm] = (sp.mean(), sp.mean() / sp.std(ddof=1) * math.sqrt(len(sp)), len(sp))
    L += ["", "| weekly spread, passed − failed | bp | t | weeks |", "|---|---:|---:|---:|"]
    for nm, (m, tt, n) in res.items():
        L.append(f"| {nm} | {m * 1e4:+.1f} | {tt:+.2f} | {n} |")
    prim = res["all"][1] >= 2.0
    sec = res["long"][0] > 0 and res["short"][0] > 0 and Hd[Hd.passed].lc_pnl.mean() > Hd.lc_pnl.mean()
    L += ["", f"**Primary (t ≥ 2.0): {'PASS' if prim else 'FAIL'}.** Secondary (both sides positive, passed above all): "
          f"{'yes' if sec else 'no'}.", ""]
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(ROOT, "reports", "research", "technicals_backtest.md"), "a").write(txt)


# ----------------------------------------------------------------------------- pre-registration 3: breakout entry
def breakout_level(lm, placebo_rng=None):
    """The far edge of the nearest strong opposing zone within 6 ATR (long frame), or None (clear air)."""
    m = placebo_map(lm, placebo_rng) if placebo_rng is not None else lm
    c, a = m["close"], m["atr"]
    zs = [z for z in m["zones"] if z["strength"] >= LV.P["STRONG"] and z["hi"] >= c and z["lo"] - c <= 6 * a]
    return min(zs, key=lambda z: z["lo"])["hi"] if zs else None


def breakout_ticker(t):
    T = pd.read_parquet(os.path.join(BT, "trades.parquet"), columns=["ticker", "news_day", "entry_day", "side", "H", "W", "beta"])
    T = T[T.ticker == t]
    b = load(t)
    if b is None or T.empty:
        return []
    ctx = context()
    b = b[b.index.isin(ctx.index)]
    r = b["adj close"].pct_change()
    rm = ctx["spy_ret"].reindex(b.index)
    charts = {1: LV.Chart(b, 1), -1: LV.Chart(b, -1)}
    idx = {d: i for i, d in enumerate(b.index)}
    out = []
    for nd, ed, side, H, W, beta in zip(T.news_day, T.entry_day, T.side, T.H, T.W, T.beta):
        k = idx.get(ed)
        if k is None or k + 5 + H + 1 >= len(b):
            continue
        ch = charts[side]
        es = (side * (r - beta * rm)).to_numpy()
        try:
            lm0 = ch.levels(b.index[k], event_day=nd)
        except (ValueError, KeyError):
            continue
        rng = np.random.default_rng(zlib.crc32(f"bo{t}{ed.date()}".encode()))
        rec = {"ticker": t, "entry_day": ed, "side": side}
        for name, lvl in (("bo", breakout_level(lm0)), ("bo_placebo", breakout_level(lm0, rng))):
            if lvl is None:
                fill = k                                     # clear air: enter at the Thursday close
            else:
                fill = None
                for s_ in range(1, 6):
                    c_ = ch.b["close"].iloc[k + s_]
                    rv = ch.relvol.iloc[k + s_]
                    if c_ > lvl and np.isfinite(rv) and rv >= 1.5:
                        fill = k + s_; break
            if fill is None:
                rec[f"{name}_pnl"], rec[f"{name}_how"] = 0.0, "skip"
                continue
            R = 0.0
            for j in range(fill + 1, fill + H + 1):
                R += es[j]
                if R <= -STOP_K * W or R >= TARGET_K * W:
                    break
            rec[f"{name}_pnl"] = R - 2 * COST
            rec[f"{name}_how"] = "clear_air" if lvl is None else f"breakout_d{fill - k}"
        out.append(rec)
    return out


def breakout():
    tick = sorted(pd.read_parquet(os.path.join(BT, "trades.parquet"), columns=["ticker"]).ticker.unique())
    rows = []
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as ex:
        for res in ex.map(breakout_ticker, tick, chunksize=4):
            rows += res
    Bk = pd.DataFrame(rows).merge(pd.read_parquet(os.path.join(BT, "trades.parquet"),
                                                  columns=["ticker", "entry_day", "lc_pnl"]), on=["ticker", "entry_day"])
    Bk.to_parquet(os.path.join(BT, "breakout.parquet"))
    L = ["", "## Results of pre-registration 3: breakout entry (computed 2026-10-08)", "",
         "| period | events | immediate bp | breakout bp | placebo-breakout bp | breakout − immediate (bp, t) | breakout − placebo (bp, t) | breakout entries / skips / clear air |",
         "|---|---:|---:|---:|---:|---:|---:|---|"]
    res = {}
    for lab, lo, hi in (("2012–2021", FIT[0], FIT[1]), ("**2022–2025**", HOLD[0], HOLD[1])):
        S = Bk[(Bk.entry_day >= lo) & (Bk.entry_day <= hi)]
        d1, d2 = S.bo_pnl - S.lc_pnl, S.bo_pnl - S.bo_placebo_pnl
        m1, t1, _ = weekly_t(d1, S.entry_day)
        m2, t2, _ = weekly_t(d2, S.entry_day)
        how = S.bo_how.str.startswith("breakout").mean(), (S.bo_how == "skip").mean(), (S.bo_how == "clear_air").mean()
        L.append(f"| {lab} | {len(S):,} | {S.lc_pnl.mean() * 1e4:+.1f} | {S.bo_pnl.mean() * 1e4:+.1f} | "
                 f"{S.bo_placebo_pnl.mean() * 1e4:+.1f} | {m1 * 1e4:+.1f}, {t1:+.2f} | {m2 * 1e4:+.1f}, {t2:+.2f} | "
                 f"{how[0]:.0%} / {how[1]:.0%} / {how[2]:.0%} |")
        res[lab] = (t1, t2)
    ok = res["**2022–2025**"][0] >= 2 and res["**2022–2025**"][1] >= 2
    L += ["", f"**Breakout entry: {'PASS' if ok else 'FAIL'}** (both holdout t ≥ 2.0 required).", ""]
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(ROOT, "reports", "research", "technicals_backtest.md"), "a").write(txt)


# ----------------------------------------------------------------------------- drift profiles (horizon classes)
DRIFT_DAYS = (1, 2, 3, 5, 10, 15, 20, 30, 40, 60)


def drift_ticker(t):
    """Side-signed cumulative residual return from the news-day close, and from the Thursday entry close, to
    each of DRIFT_DAYS sessions later."""
    T = pd.read_parquet(os.path.join(BT, "trades.parquet"), columns=["ticker", "news_day", "entry_day", "side", "beta", "gap_atr", "W", "H"])
    T = T[T.ticker == t]
    b = load(t)
    if b is None or T.empty:
        return []
    ctx = context()
    b = b[b.index.isin(ctx.index)]
    r = b["adj close"].pct_change()
    rm = ctx["spy_ret"].reindex(b.index)
    idx = {d: i for i, d in enumerate(b.index)}
    out = []
    for nd, ed, side, beta, gap, W, H in zip(T.news_day, T.entry_day, T.side, T.beta, T.gap_atr, T.W, T.H):
        j, k = idx.get(nd), idx.get(ed)
        if j is None or k is None or k + 60 >= len(b):
            continue
        e = (side * (r - beta * rm)).to_numpy()
        rec = {"ticker": t, "news_day": nd, "entry_day": ed, "side": side, "gap_atr": abs(gap),
               "sigma": W / math.sqrt(H)}
        for h in DRIFT_DAYS:
            rec[f"n{h}"] = float(np.nansum(e[j + 1:j + h + 1]))
            rec[f"e{h}"] = float(np.nansum(e[k + 1:k + h + 1]))
        out.append(rec)
    return out


def drift():
    tick = sorted(pd.read_parquet(os.path.join(BT, "trades.parquet"), columns=["ticker"]).ticker.unique())
    rows = []
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 1)) as ex:
        for res in ex.map(drift_ticker, tick, chunksize=4):
            rows += res
    D = pd.DataFrame(rows)
    p = os.path.join(BT, "iv.parquet")
    if os.path.exists(p):
        V = pd.read_parquet(p)[["ticker", "news_day", "iv"]]
        V["news_day"] = pd.to_datetime(V["news_day"])
        D = D.merge(V, on=["ticker", "news_day"], how="left")
    D.to_parquet(os.path.join(BT, "drift.parquet"))
    hdr = "| group | events | " + " | ".join(f"+{h}" for h in DRIFT_DAYS) + " |"
    sep = "|---|---:|" + "---:|" * len(DRIFT_DAYS)

    def row(lab, S, pre):
        cells = []
        for h in DRIFT_DAYS:
            m, tt, _ = weekly_t(S[f"{pre}{h}"], S.entry_day)
            cells.append(f"{m * 1e4:+.0f} ({tt:+.1f})")
        return f"| {lab} | {len(S):,} | " + " | ".join(cells) + " |"

    L = ["", "## Drift profiles: when does the edge arrive? (2012–2025, for the horizon classes)", "",
         "Mean side-signed cumulative residual return in bp (t on weekly means), the view's side = gap direction. "
         "From the news-day close (the market's reaction already in) and from the fund's Thursday entry close.", "",
         "**From the news-day close:**", "", hdr, sep]
    L.append(row("all", D, "n"))
    for sd, nm in ((1, "long (gap up)"), (-1, "short (gap down)")):
        L.append(row(nm, D[D.side == sd], "n"))
    D["gq"] = pd.qcut(D.gap_atr, 3, labels=["smaller gaps", "middle gaps", "largest gaps"])
    for g, S in D.groupby("gq", observed=True):
        L.append(row(str(g), S, "n"))
    if "iv" in D:
        S = D[D.iv.notna()].copy()
        S["iq"] = pd.qcut(S.iv, 3, labels=["low IV before", "middle IV", "high IV before"])
        for g, G in S.groupby("iq", observed=True):
            L.append(row(str(g), G, "n"))
    L += ["", "**From the Thursday entry close (what the fund can capture):**", "", hdr, sep]
    L.append(row("all", D, "e"))
    for sd, nm in ((1, "long"), (-1, "short")):
        L.append(row(nm, D[D.side == sd], "e"))
    for lab, lo, hi in (("2012–2021", FIT[0], FIT[1]), ("2022–2025", HOLD[0], HOLD[1])):
        L.append(row(lab, D[(D.entry_day >= lo) & (D.entry_day <= hi)], "e"))
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(ROOT, "reports", "research", "technicals_backtest.md"), "a").write(txt)


if __name__ == "__main__":
    {"download": download, "run": run, "report": report, "touch": touch, "touch_report": touch_report, "gate": gate,
     "breakout": breakout, "drift": drift}[sys.argv[1]]()
