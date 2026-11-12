"""Forward beta records (research/riskfield/PREREG.md Amendment 5; never traded): each Thursday, the fund's beta (B0)
and the intraday-calibrated beta (B1, coefficients frozen in FROZEN_B1.json) for every S&P 500 member; 21 sessions
later, the realised beta from 30-minute returns, frozen at first computation.

    python research/riskfield/forward.py freeze                       # once: B1 coefficients from 2016-2025 -> FROZEN_B1.json
    cd research/quant_trials && PYTHONPATH=. python ../riskfield/forward.py weekly [--asof YYYY-MM-DD] [--dry]
    cd research/quant_trials && PYTHONPATH=. python ../riskfield/forward.py ledger [--dry]

Runs after the forward S&P books in the Friday job and reuses their price panel (spx_live.build) and calendar.
Bars: Alpaca market data, SIP feed, split-adjusted, regular session (the research data's source; see Amendment 5a).
Needs ALPACA_API_KEY / ALPACA_SECRET_KEY in the environment (the runner provides them; never printed).
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN = os.path.join(HERE, "FROZEN_B1.json")
REC = os.environ.get("BETA_REC", os.path.expanduser("~/.fund-runner/research/beta"))
CACHE = os.environ.get("SPX_CACHE", os.path.expanduser("~/.fund-runner/cache/spx"))
BARS = os.path.join(CACHE, "bars30_regular.parquet")
DRY = os.path.join(CACHE, "beta_forward_dry")
MIN_COVERAGE = 0.90                       # share of members with a 63-session intraday beta, else a problem


# ------------------------------------------------------------------------------------------------- definitions
def day_returns(bars, sessions, names):
    """bars: DataFrame(date, ticker, k (0..12 = 09:30..15:30 ET bar), open, close), regular session only.
    -> R (sessions x 14 x names): overnight, then the 13 intraday log returns; a name-day needs all 13 bars, and any
    |return| > 0.4 makes it missing (PREREG.md §2)."""
    S = pd.DatetimeIndex(sessions)
    full = bars.groupby(["date", "ticker"]).k.transform("size") == 13
    b = bars[full]
    di, ni = S.get_indexer(b.date), pd.Index(names).get_indexer(b.ticker)
    ok = (di >= 0) & (ni >= 0)
    b, di, ni = b[ok], di[ok], ni[ok]
    C = np.full((len(S), 13, len(names)), np.nan)
    C[di, b.k.to_numpy(), ni] = np.log(b.close.to_numpy())
    O = np.full((len(S), len(names)), np.nan)
    o = b.k.to_numpy() == 0
    O[di[o], ni[o]] = np.log(b.open.to_numpy()[o])
    R = np.empty((len(S), 14, len(names)))
    R[:, 0] = O - np.vstack([np.full((1, len(names)), np.nan), C[:-1, 12]])
    R[:, 1] = C[:, 0] - O
    R[:, 2:] = np.diff(C, axis=1)
    bad = np.any(np.abs(R) > 0.4, axis=1)
    R[np.broadcast_to(bad[:, None, :], R.shape)] = np.nan
    return R


def hf_beta(R, mi, need):
    """Realised beta over all sessions of R (14 returns a day) against column mi; NaN with < need complete days."""
    rm = R[:, :, mi]
    ok = np.isfinite(R).all(1) & np.isfinite(rm).all(1)[:, None]
    x = np.where(ok[:, None, :], R, 0.0)
    m = np.where(ok[:, None, :], rm[:, :, None], 0.0)
    num, den = (x * m).sum((0, 1)), (m * m).sum((0, 1))
    return np.where(ok.sum(0) >= need, num / np.where(den > 0, den, np.nan), np.nan)


def ols_beta(r, rm, t):
    """The fund's raw ingredient: OLS beta over sessions t-251..t of returns winsorised to
    [min, max](-2 r_m, 4 r_m), >= 200 finite (sp500_test.build). B0 = 2/3 of it + 1/3."""
    a = t - 251
    x, m = r[a:t + 1], rm[a:t + 1]
    lo, hi = np.minimum(-2 * m, 4 * m)[:, None], np.maximum(-2 * m, 4 * m)[:, None]
    x = np.clip(x, lo, hi)
    ok = np.isfinite(x) & np.isfinite(m)[:, None]
    n = ok.sum(0)
    mm = np.where(ok, m[:, None], 0.0)
    xx = np.where(ok, x, 0.0)
    mx, mmn = xx.sum(0) / np.maximum(n, 1), mm.sum(0) / np.maximum(n, 1)
    cov = ((xx - mx) * (mm - mmn) * ok).sum(0) / np.maximum(n - 1, 1)
    var = (((mm - mmn) ** 2) * ok).sum(0) / np.maximum(n - 1, 1)
    return np.where(n >= 200, cov / np.where(var > 0, var, np.nan), np.nan)


def b1(coef, hf21, hf63, ols):
    return coef["intercept"] + coef["hf21"] * hf21 + coef["hf63"] * hf63 + coef["ols"] * ols


# ------------------------------------------------------------------------------------------------------- freeze
def freeze():
    """B1's pooled calibration on every weekly decision 2016-2025 whose 21-session target ended by 2025-12-31
    (the research panel; PREREG §5). Written once; refuses to overwrite."""
    if os.path.exists(FROZEN):
        raise SystemExit(f"{FROZEN} exists")
    import beta as BT
    import risk as K
    D = K.Data()
    B = BT.build(D)
    regs = [B["b21"], B["b63"], B["ols"]]
    m = np.broadcast_to(D.stock, (D.T, D.N)) & B["thu"][:, None] & np.all([np.isfinite(r) for r in regs], 0)
    m &= np.isfinite(B["tgt"]) & (np.arange(D.T) + 21 < D.T)[:, None]
    X = np.column_stack([np.ones(m.sum())] + [r[m] for r in regs])
    c = np.linalg.lstsq(X, B["tgt"][m], rcond=None)[0]
    out = {"intercept": float(c[0]), "hf21": float(c[1]), "hf63": float(c[2]), "ols": float(c[3]), "rows": int(m.sum()),
           "decisions": f"{D.S[np.where(m.any(1))[0][0]].date()}..{D.S[np.where(m.any(1))[0][-1]].date()}",
           "frozen_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}
    json.dump(out, open(FROZEN, "w"), indent=1)
    print(json.dumps(out, indent=1))


# --------------------------------------------------------------------------------------------------------- bars
_LAST = [0.0]
_LOCK = threading.Lock()
GAP = 0.33                                 # seconds between requests: about 180 a minute (the plan allows 200)


def _get(url):
    req = urllib.request.Request(url, headers={"APCA-API-KEY-ID": os.environ["ALPACA_API_KEY"],
                                               "APCA-API-SECRET-KEY": os.environ["ALPACA_SECRET_KEY"]})
    for attempt in range(6):
        with _LOCK:
            wait = _LAST[0] + GAP - time.time()
            if wait > 0:
                time.sleep(wait)
            _LAST[0] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:                                       # noqa: BLE001 (transport: retried, then raised)
            if attempt == 5:
                raise RuntimeError(f"Alpaca bars request failed 6 times: {type(e).__name__} {getattr(e, 'code', '')}") from None
            time.sleep(5 * 2 ** min(attempt, 3))


SIP_DELAY = pd.Timedelta(minutes=16)       # Alpaca's free plan refuses SIP data newer than 15 minutes (HTTP 403)


def _now():
    return pd.Timestamp.now(tz="UTC")


def window_end(end):
    """The request's end: 04:00 UTC the day after `end`, but never later than now - 16 minutes. On 2026-11-11 the
    weekly screen (22:15 UTC) asked for bars to 04:00 UTC the next morning and every request was refused: "subscription
    does not permit querying recent SIP data"."""
    want = pd.Timestamp(f"{(pd.Timestamp(end) + pd.Timedelta(days=1)).date()}T04:00:00Z")
    return min(want, _now() - SIP_DELAY).strftime("%Y-%m-%dT%H:%M:%SZ")


def _chain(symbols, start, end):
    """One symbol group, all pages (Alpaca returns about 370 bars a page whatever the limit)."""
    q = {"symbols": ",".join(symbols), "timeframe": "30Min", "feed": "sip", "adjustment": "split",
         "start": f"{start}T08:00:00Z", "end": window_end(end), "limit": 10000}
    rows, tok = [], None
    while True:
        d = _get("https://data.alpaca.markets/v2/stocks/bars?" + urllib.parse.urlencode({**q, **({"page_token": tok} if tok else {})}))
        for s_, bs in (d.get("bars") or {}).items():
            rows += [(s_, b["t"], b["o"], b["c"]) for b in bs]
        tok = d.get("next_page_token")
        if not tok:
            return rows


def fetch(symbols, start, end):
    """30-minute SIP bars, split-adjusted, sessions start..end (dates) -> regular-session rows; 10-symbol groups
    in 4 threads under one rate limit."""
    from concurrent.futures import ThreadPoolExecutor
    groups = [symbols[i:i + 10] for i in range(0, len(symbols), 10)]
    with ThreadPoolExecutor(4) as ex:
        rows = [r for part in ex.map(lambda g: _chain(g, start, end), groups) for r in part]
    b = pd.DataFrame(rows, columns=["ticker", "t", "open", "close"])
    if b.empty:
        return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "ticker": pd.Series(dtype=str),
                             "k": pd.Series(dtype=int), "open": pd.Series(dtype=float), "close": pd.Series(dtype=float)})
    et = pd.to_datetime(b.pop("t"), utc=True).dt.tz_convert("America/New_York")
    mins = et.dt.hour * 60 + et.dt.minute - 570
    keep = ((mins >= 0) & (mins <= 360) & (mins % 30 == 0)).to_numpy()
    b = b[keep].copy()
    b["k"] = (mins[keep] // 30).astype(int).to_numpy()
    b["date"] = et[keep].dt.tz_localize(None).dt.normalize().to_numpy()
    return b[["date", "ticker", "k", "open", "close"]].reset_index(drop=True)


def _typed(b):
    """Column types of the bar table (an empty cache would otherwise turn prices into objects on concat)."""
    return b.astype({"ticker": str, "k": int, "open": float, "close": float}).assign(date=pd.to_datetime(b.date))


def bars_for(symbols, sessions, all_sessions):
    """Regular-session bars for symbols x sessions from the cache (BARS), fetching what is missing.

    * New sessions are fetched with one overlap session already in the cache.
    * A symbol whose overlap closes differ (a split re-adjusted its history) loses its cached bars and is fetched
      afresh over the whole window, so no window mixes two adjustments.
    * The cache keeps 300 calendar days."""
    sessions = pd.DatetimeIndex(sessions)
    cols = ["date", "ticker", "k", "open", "close"]
    have = _typed(pd.read_parquet(BARS) if os.path.exists(BARS) else pd.DataFrame(columns=cols))
    cached = have.groupby("ticker").date.agg(lambda x: set(x)).to_dict() if len(have) else {}
    plan = {}
    for s_ in symbols:
        c = cached.get(s_, set())
        miss = [d for d in sessions if d not in c]
        if not miss:
            continue
        prior = [d for d in all_sessions if d < miss[0] and d in c]
        start = prior[-1] if prior and all(d in c for d in sessions if d < miss[0]) else sessions[0]
        plan.setdefault(start, []).append(s_)
    new = [fetch(g, st.date(), sessions[-1].date()) for st, g in sorted(plan.items())]
    if new:
        new = pd.concat(new)
        new["date"] = pd.to_datetime(new.date)
        m = new.merge(have, on=["date", "ticker", "k"], suffixes=("", "_old"))
        moved = sorted(set(m.loc[(m.close / m.close_old - 1).abs() > 1e-6, "ticker"]))
        if moved:                                   # re-adjusted history: refetch these names over the whole window
            print(f"re-adjusted since cached (split): {', '.join(moved)}: refetched")
            have = have[~have.ticker.isin(moved)]
            new = pd.concat([new[~new.ticker.isin(moved)], fetch(moved, sessions[0].date(), sessions[-1].date())])
            new["date"] = pd.to_datetime(new.date)
        have = _typed(pd.concat([have, new])).drop_duplicates(["date", "ticker", "k"], keep="last")
        have = have[have.date >= sessions[-1] - pd.Timedelta(days=300)]
        os.makedirs(CACHE, exist_ok=True)
        have[cols].reset_index(drop=True).to_parquet(BARS)
    return have[have.ticker.isin(symbols) & have.date.isin(sessions)]


# ------------------------------------------------------------------------------------------------------- weekly
def weekly(asof=None, dry=False):
    import spx_forward as FW
    import spx_live as L
    out = DRY if dry else REC
    if asof is None:
        exp = FW.expected_thursday()
        if exp is None or os.path.exists(os.path.join(out, f"beta_{exp.date()}.json")):
            print("nothing to record (already recorded, or a holiday week)")
            return None
        asof = str(exp.date())
    d = L.build()
    S, names = d["S"], list(d["names"])
    if pd.Timestamp(asof) not in S:
        sys.exit(f"prices for {asof} are missing (data to {S[-1].date()}): no record written")
    t = int(np.searchsorted(S, pd.Timestamp(asof)))
    if S[t].weekday() != 3:
        sys.exit(f"{asof}: not a Thursday session")
    path = os.path.join(out, f"beta_{asof}.json")
    if os.path.exists(path):
        sys.exit(f"{path} exists: records are append-only")
    coef = json.load(open(FROZEN))
    mem = [n for n, e in zip(names, d["elig"][t]) if e]
    syms = mem + ["SPY"]
    ses = S[t - 62:t + 1]
    R = day_returns(bars_for(syms, ses, S), ses, syms)
    mi = len(syms) - 1
    h21, h63 = hf_beta(R[-21:], mi, 17)[:-1], hf_beta(R, mi, 50)[:-1]
    ix = [names.index(n) for n in mem]
    ols = ols_beta(d["r"][:, ix], d["rm"], t)
    B0 = d["beta"][t, ix]
    B1 = b1(coef, h21, h63, ols)
    problems = []
    cov = float(np.isfinite(h63).mean())
    if cov < MIN_COVERAGE:
        problems.append(f"intraday beta for {cov:.0%} of {len(mem)} members (< {MIN_COVERAGE:.0%}): bars incomplete")
    nb = lambda x: None if not np.isfinite(x) else round(float(x), 5)
    rec = {"asof": asof, "data_end": str(S[-1].date()), "dry": dry,
           "code": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip(), "coef": coef,
           "members": len(mem), "coverage_hf63": cov,
           "betas": {n: {"B0": nb(B0[i]), "B1": nb(B1[i]), "hf21": nb(h21[i]), "hf63": nb(h63[i]), "ols": nb(ols[i])}
                     for i, n in enumerate(mem)}, "problems": problems}
    spx = os.path.join(FW.DRY if dry else FW.REC, f"spx_{asof}.json")
    if os.path.exists(spx):                        # the AI ensemble book's hedge under each beta (residual exposure)
        e = json.load(open(spx))["books"]["fw_ensemble"]
        w = e["weights"]
        bb = {k: sum(x * (rec["betas"].get(n, {}).get(k) or 0.0) for n, x in w.items()) for k in ("B0", "B1")}
        rec["ens"] = {"w_spy": e["w_spy"], "book_beta_B0": bb["B0"], "book_beta_B1": bb["B1"],
                      "missing_B1": [n for n in w if rec["betas"].get(n, {}).get("B1") is None]}
    else:
        problems.append(f"no forward S&P record for {asof}: ensemble hedge not compared")
    os.makedirs(out, exist_ok=True)
    json.dump(rec, open(path, "w"), indent=1)
    print(f"written {path}: {len(mem)} members, intraday coverage {cov:.1%}; "
          f"B1-B0 mean {np.nanmean(B1 - B0):+.3f}, sd {np.nanstd(B1 - B0):.3f}" + (f"; ens {rec['ens']}" if "ens" in rec else ""))
    if problems:                                                        # fail loudly, after saving (CLAUDE.md 9)
        sys.exit("; ".join(problems))
    return path


# ------------------------------------------------------------------------------------------------------- ledger
def ledger(dry=False):
    """Score each record whose 21 following sessions are in the price data: realised beta from 30-minute returns over
    t+1..t+21, squared errors of B0 and B1, and the ensemble book's realised residual beta under each hedge.
    Rows are frozen at first computation."""
    import spx_live as L
    path = DRY if dry else REC
    recs = sorted(f for f in os.listdir(path) if f.startswith("beta_20")) if os.path.isdir(path) else []
    lp = os.path.join(path, "ledger.json")
    led = json.load(open(lp)) if os.path.exists(lp) else {"rows": []}
    have = {r["asof"] for r in led["rows"]}
    d = L.build()
    S = d["S"]
    for f in recs:
        rec = json.load(open(os.path.join(path, f)))
        if rec["asof"] in have:
            continue
        t = int(np.searchsorted(S, pd.Timestamp(rec["asof"])))
        if t + 21 >= len(S):
            continue
        mem = list(rec["betas"])
        syms = mem + ["SPY"]
        ses = S[t + 1:t + 22]
        R = day_returns(bars_for(syms, ses, S), ses, syms)
        real = hf_beta(R, len(syms) - 1, 17)[:-1]
        b0 = np.array([rec["betas"][n]["B0"] if rec["betas"][n]["B0"] is not None else np.nan for n in mem], float)
        b1v = np.array([rec["betas"][n]["B1"] if rec["betas"][n]["B1"] is not None else np.nan for n in mem], float)
        ok = np.isfinite(real) & np.isfinite(b0) & np.isfinite(b1v)
        row = {"asof": rec["asof"], "from": str(ses[0].date()), "to": str(ses[-1].date()), "names": int(ok.sum()),
               "mse_B0": float(np.mean((real[ok] - b0[ok]) ** 2)), "mse_B1": float(np.mean((real[ok] - b1v[ok]) ** 2)),
               "computed_with_data_to": str(S[-1].date())}
        if "ens" in rec:
            spx = json.load(open(os.path.join(os.path.dirname(path), "spx", f"spx_{rec['asof']}.json"))) if not dry else None
            if spx:
                w = spx["books"]["fw_ensemble"]["weights"]
                rb = dict(zip(mem, real))
                br = sum(x * rb.get(n, np.nan) for n, x in w.items())
                row["ens_realised_beta"] = None if not np.isfinite(br) else float(br)
                row["ens_residual_B0"] = None if not np.isfinite(br) else float(br - rec["ens"]["book_beta_B0"])
                row["ens_residual_B1"] = None if not np.isfinite(br) else float(br - rec["ens"]["book_beta_B1"])
        led["rows"].append(row)
    led["rows"].sort(key=lambda r: r["asof"])
    os.makedirs(path, exist_ok=True)
    json.dump(led, open(lp, "w"), indent=1)
    rows = led["rows"]
    page = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "records": len(recs),
            "scored": len(rows), "first": recs[0][5:15] if recs else None,
            "mse_B0": float(np.mean([r["mse_B0"] for r in rows])) if rows else None,
            "mse_B1": float(np.mean([r["mse_B1"] for r in rows])) if rows else None, "rows": rows,
            "evidence": {"oos_mse_B0": 0.1454, "oos_mse_B1": 0.0971, "oos_t": 7.56, "years": "2020-2025"}}
    if recs:
        last = json.load(open(os.path.join(path, recs[-1])))
        page["latest"] = {"asof": last["asof"], "members": last["members"], "coverage_hf63": last["coverage_hf63"],
                          "ens": last.get("ens")}
    json.dump(page, open(os.path.join(path, "page.json"), "w"), indent=1, allow_nan=False)
    print(json.dumps({k: page[k] for k in ("records", "scored", "mse_B0", "mse_B1")}))
    return page


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["freeze", "weekly", "ledger"])
    ap.add_argument("--asof")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.cmd == "freeze":
        sys.path.insert(0, HERE)
        freeze()
    else:                              # quant_trials' modules first: this folder's panel.py would shadow theirs
        sys.path = [p for p in sys.path if os.path.abspath(p or ".") != HERE]
        weekly(a.asof, a.dry) if a.cmd == "weekly" else ledger(a.dry)
