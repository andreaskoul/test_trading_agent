"""Volatility-forecasting study: data foundation (free sources only). Builds daily realised measures for three asset
classes. Nothing here fits a model or evaluates a forecast; `coverage` writes counts only.

    PY=~/.fund-runner/venv-vol/bin/python
    $PY -I research/volforecast/data.py crypto        # Binance Vision bulk 5-minute klines, sha256-checked
    $PY -I research/volforecast/data.py indices       # Yahoo daily OHLC (indices and VIX)
    python3 ~/.claude/hooks/with_secrets.py '$PY research/volforecast/data.py alpaca'   # SIP 5-min + daily bars
    $PY -I research/volforecast/data.py coverage      # -> COVERAGE.json (counts only)

Sources (all free, no account beyond the fund's existing Alpaca paper key):
  * crypto: data.binance.vision spot klines, 5m, monthly zips (+ daily zips for the current month). Every zip is
    checked against the sha256 Binance publishes beside it (.CHECKSUM); a mismatch is a typed defect.
  * indices: Yahoo chart API through yfinance, auto_adjust=False.
  * US ETFs and S&P 500 point-in-time members: Alpaca SIP bars, adjustment=all, 5Min (regular session kept) and 1Day.
Raw files live under .cache/volforecast (not committed); DATA_MANIFEST.json (committed) freezes every file's sha256.
"""
import concurrent.futures as cf
import hashlib
import io
import json
import math
import os
import sys
import time
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.environ.get("VOL_CACHE", os.path.join(ROOT, ".cache", "volforecast"))
DAILY = os.path.join(CACHE, "daily")
MANIFEST = os.path.join(HERE, "DATA_MANIFEST.json")
END = "2026-11-27"                                   # last full session / UTC day before the plan (2026-11-28)
UA = {"User-Agent": "Mozilla/5.0 (research client)"}

CRYPTO = {"BTCUSDT": "2017-08", "ETHUSDT": "2017-08", "BNBUSDT": "2017-11", "LTCUSDT": "2017-12",
          "ADAUSDT": "2018-04", "XRPUSDT": "2018-05", "DOGEUSDT": "2019-07", "SOLUSDT": "2020-08"}
INDICES = ["^GSPC", "^NDX", "^RUT", "^DJI", "^FTSE", "^GDAXI", "^N225", "^STOXX50E", "^HSI", "^VIX"]
ETFS = ["SPY", "QQQ", "IWM", "DIA"]
STOCK_START = "2016-01-04"
BV_MU = math.sqrt(2 / math.pi)
for d in (CACHE, DAILY):
    os.makedirs(d, exist_ok=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_manifest():
    return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"files": {}, "daily": {}}


def save_manifest(m):
    m["written_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(m, open(MANIFEST, "w"), indent=1, sort_keys=True)


# ===================================================================================== realised measures
def measures(r):
    """Daily realised measures from one day's intraday log returns r (1-D, NaN-free). RV, bipower BV (scaled to
    the integrated variance), positive and negative semivariances, realised quarticity, number of returns."""
    n = len(r)
    if n < 2:
        return dict(rv=np.nan, bv=np.nan, rs_pos=np.nan, rs_neg=np.nan, rq=np.nan, n=n)
    a = np.abs(r)
    return dict(rv=float((r ** 2).sum()), bv=float((a[1:] * a[:-1]).sum() / BV_MU ** 2 * n / (n - 1)),
                rs_pos=float((r[r > 0] ** 2).sum()), rs_neg=float((r[r < 0] ** 2).sum()),
                rq=float(n / 3 * (r ** 4).sum()), n=n)


# ===================================================================================== crypto (Binance Vision)
def _months(start, end):
    return [str(p) for p in pd.period_range(start, end, freq="M")]


def _get(url, tries=4):
    import requests
    for k in range(tries):
        try:
            x = requests.get(url, headers=UA, timeout=60)
            if x.status_code == 200:
                return x.content
            if x.status_code == 404:
                return None
        except Exception:                                            # noqa: BLE001
            pass
        time.sleep(2 ** k)
    raise RuntimeError(f"fetch failed: {url}")


def _crypto_file(sym, kind, stamp):
    base = f"https://data.binance.vision/data/spot/{kind}/klines/{sym}/5m/{sym}-5m-{stamp}.zip"
    p = os.path.join(CACHE, "binance", sym, f"{sym}-5m-{stamp}.zip")
    if os.path.exists(p):
        return p, "cached"
    z = _get(base)
    if z is None:
        return None, "absent"
    chk = _get(base + ".CHECKSUM")
    want = chk.decode().split()[0] if chk else None
    got = hashlib.sha256(z).hexdigest()
    if want is None or want != got:
        return None, f"checksum_mismatch want={want} got={got}"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".part"
    open(tmp, "wb").write(z)
    os.replace(tmp, p)
    return p, "fetched"


def crypto():
    m = load_manifest()
    last_full_month = str(pd.Period(END, freq="M") - 1)
    for sym, start in CRYPTO.items():
        jobs = [("monthly", s) for s in _months(start, last_full_month)]
        jobs += [("daily", str(d.date())) for d in pd.date_range(str(pd.Period(END, freq="M").start_time.date()), END)]
        with cf.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda j: (j, _crypto_file(sym, *j)), jobs))
        bad = [(j, s) for j, (p, s) in res if p is None and s != "absent"]
        absent = [j for j, (p, s) in res if s == "absent"]
        if bad:
            raise SystemExit(f"{sym}: {len(bad)} files failed their checksum or fetch, e.g. {bad[:3]}; nothing reduced")
        for j, (p, s) in res:
            if p:
                m["files"][os.path.relpath(p, CACHE)] = sha(p)
        m.setdefault("absent", {})[sym] = absent
        print(f"{sym}: {sum(1 for _, (p, _) in res if p)} files ({len(absent)} absent)", flush=True)
        reduce_crypto(sym, m)
        save_manifest(m)


def _read_kline_zip(p):
    with zipfile.ZipFile(p) as z:
        name = z.namelist()[0]
        raw = z.read(name)
    df = pd.read_csv(io.BytesIO(raw), header=None, usecols=range(6),
                     names=["t", "o", "h", "l", "c", "v"])
    if not np.issubdtype(df["t"].dtype, np.number):                  # a header row in some files
        df = df[pd.to_numeric(df["t"], errors="coerce").notna()].astype({"t": "int64", "o": float, "h": float,
                                                                           "l": float, "c": float, "v": float})
    unit = np.where(df["t"] > 10 ** 14, "us", "ms")                  # Binance spot moved to microseconds in 2025
    df["ts"] = [pd.Timestamp(int(t), unit=u) for t, u in zip(df["t"], unit)] if (unit == "us").any() and (unit == "ms").any() \
        else pd.to_datetime(df["t"], unit=unit[0])
    return df[["ts", "o", "h", "l", "c", "v"]]


def reduce_crypto(sym, m):
    files = sorted(os.listdir(os.path.join(CACHE, "binance", sym)))
    B = pd.concat([_read_kline_zip(os.path.join(CACHE, "binance", sym, f)) for f in files if f.endswith(".zip")])
    B = B.drop_duplicates("ts").sort_values("ts").set_index("ts")
    B = B[B.index < pd.Timestamp(END) + pd.Timedelta(days=1)]
    lc = np.log(B["c"])
    r = lc.diff()                                                    # consecutive 5-minute closes across midnight
    day = B.index.floor("D")
    rows = []
    for d, idx in pd.Series(np.arange(len(B)), index=day).groupby(level=0):
        g = B.iloc[idx.values]
        rr = r.iloc[idx.values].dropna().values
        rows.append(dict(date=d, open=g["o"].iloc[0], high=g["h"].max(), low=g["l"].min(), close=g["c"].iloc[-1],
                         volume=g["v"].sum(), n_bars=len(g), **measures(rr)))
    D = pd.DataFrame(rows).set_index("date")
    D["ret"] = np.log(D["close"]).diff()
    D["rv_ok"] = D["n_bars"] >= 0.9 * 288
    out = os.path.join(DAILY, f"crypto_{sym}.parquet")
    D.to_parquet(out)
    m["daily"][os.path.relpath(out, CACHE)] = sha(out)
    print(f"  {sym}: {len(D)} days {D.index.min().date()}..{D.index.max().date()}, rv_ok {D['rv_ok'].mean():.3f}")


# ===================================================================================== indices (Yahoo)
def indices():
    import yfinance as yf
    m = load_manifest()
    os.makedirs(os.path.join(CACHE, "yahoo"), exist_ok=True)
    for t in INDICES:
        p = os.path.join(CACHE, "yahoo", t.replace("^", "") + ".csv")
        if not os.path.exists(p):
            df = yf.Ticker(t).history(start="1985-01-01", end="2026-11-28", auto_adjust=False, actions=False)
            if df is None or df.empty:
                raise SystemExit(f"{t}: no rows served")
            df.index = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index
            df.to_csv(p)
        m["files"][os.path.relpath(p, CACHE)] = sha(p)
        D = pd.read_csv(p, index_col=0, parse_dates=True)[["Open", "High", "Low", "Close", "Volume"]]
        D.columns = ["open", "high", "low", "close", "volume"]
        D = D[D.index <= END]
        D["ret"] = np.log(D["close"]).diff()
        D["range_ok"] = (D["high"] > D["low"]) & (D["open"] > 0)      # Yahoo early history has H = L = C
        out = os.path.join(DAILY, f"index_{t.replace('^', '')}.parquet")
        D.to_parquet(out)
        m["daily"][os.path.relpath(out, CACHE)] = sha(out)
        print(f"{t}: {len(D)} days {D.index.min().date()}..{D.index.max().date()}, range_ok {D['range_ok'].mean():.3f}")
    save_manifest(m)


# ===================================================================================== Alpaca (ETFs, stocks)
def stock_symbols():
    sys.path.insert(0, os.path.join(ROOT, "research", "p8"))
    mem = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    keep = mem[mem["date"] <= END]
    # members on any date 2016-01-04..END: the row in force at the start plus every later row
    first = keep[keep["date"] <= STOCK_START].tail(1)
    rows = pd.concat([first, keep[keep["date"] > STOCK_START]])
    names = set()
    for s in rows["tickers"]:
        names |= set(s.split(","))
    al_p = os.path.join(CACHE, "aliases.json")
    al = json.load(open(al_p)) if os.path.exists(al_p) else {}
    return sorted(names | {al[t] for t in names if t in al}), al


import threading  # noqa: E402

_LOCK = threading.Lock()
_LAST = [0.0]
RATE_PER_MIN = 190                                   # Alpaca basic plan: 200 requests a minute


def _throttle():
    with _LOCK:
        wait = _LAST[0] + 60.0 / RATE_PER_MIN - time.time()
        if wait > 0:
            time.sleep(wait)
        _LAST[0] = time.time()


def _alpaca_pages(broker, sym, tf, start, end):
    out, token = [], None
    while True:
        q = (f"/v2/stocks/bars?symbols={sym}&timeframe={tf}&adjustment=all&feed=sip&limit=10000"
             f"&start={start}&end={end}T23:59:59Z" + (f"&page_token={token}" if token else ""))
        for k in range(6):
            _throttle()
            s, b = broker.api("GET", q, base=broker.DATA)
            if s == 200:
                break
            time.sleep(min(60, 2 ** k * 3))                          # 429 / transient: back off
        if s != 200:
            raise RuntimeError(f"{sym} {tf}: HTTP {s}")
        out += (b.get("bars") or {}).get(sym, [])
        token = b.get("next_page_token")
        if not token:
            return out


def _reduce_alpaca(sym, bars5, bars1, step=5):
    """Regular-session intraday log returns at `step` minutes (first from the 09:30 open), daily official bars and
    the overnight return. Columns r01..r78 (5-minute) or q01..q26 (15-minute)."""
    nslot = 390 // step
    pre = "r" if step == 5 else "q"
    D1 = pd.DataFrame(bars1)
    if D1.empty:
        return None
    D1["date"] = pd.to_datetime(D1["t"].str[:10])
    D1 = D1.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}).set_index("date")
    D1 = D1[["open", "high", "low", "close", "volume"]]
    X = pd.DataFrame(bars5)
    rows = {}
    if not X.empty:
        ts = pd.to_datetime(X["t"], utc=True).dt.tz_convert("America/New_York")
        X["et"] = ts
        mins = ts.dt.hour * 60 + ts.dt.minute
        X = X[(mins >= 570) & (mins < 960)]                          # 09:30 <= bar start < 16:00
        X["date"] = X["et"].dt.tz_localize(None).dt.normalize()
        for d, g in X.groupby("date"):
            g = g.sort_values("et")
            lc = np.log(g["c"].values)
            r = np.diff(np.r_[np.log(g["o"].values[0]), lc])          # first return: 09:30 open -> first close
            slot = ((g["et"].dt.hour * 60 + g["et"].dt.minute).values - 570) // step
            rr = np.full(nslot, np.nan, np.float32)
            rr[slot[slot < nslot]] = r[slot < nslot]
            rows[d] = rr
    R = pd.DataFrame.from_dict(rows, orient="index", columns=[f"{pre}{i:02d}" for i in range(1, nslot + 1)])
    D = D1.join(R, how="left")
    D["ret"] = np.log(D["close"]).diff()
    D["ret_on"] = np.log(D["open"] / D["close"].shift(1))            # overnight, close(t-1) -> open(t)
    D["n_bars"] = R.notna().sum(axis=1).reindex(D.index).fillna(0).astype(int)
    return D


def _one_symbol(broker, sym):
    """ETFs at 5 minutes (true 5-minute RV for the index instruments); stocks at 15 minutes (data budget: Alpaca pages
    hold ~2,500 bars including extended hours, so 5-minute bars for 758 names would need ~11 hours at the rate limit).
    SPY is fetched at 5 minutes and aggregated to 15-minute slots for the stocks' residuals."""
    out = os.path.join(DAILY, "alpaca", f"{sym}.parquet")
    if os.path.exists(out):
        return sym, "cached", None
    step = 5 if sym in ETFS else 15
    b1 = _alpaca_pages(broker, sym, "1Day", STOCK_START, END)
    if not b1:
        return sym, "no_rows", None
    bi = _alpaca_pages(broker, sym, f"{step}Min", STOCK_START, END)
    D = _reduce_alpaca(sym, bi, b1, step)
    tmp = out + ".part"
    D.to_parquet(tmp)
    os.replace(tmp, out)
    return sym, "fetched", f"{len(D)} days, mean regular bars {D['n_bars'].mean():.1f}"


def alpaca(symbols=None):
    sys.path.insert(0, ROOT)
    from fund import broker
    names, al = stock_symbols()
    todo = ETFS + [s for s in names if s not in ETFS] if symbols is None else symbols
    os.makedirs(os.path.join(DAILY, "alpaca"), exist_ok=True)
    failed, no_rows, done = [], [], 0
    with cf.ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(_one_symbol, broker, s): s for s in todo}
        for f in cf.as_completed(futs):
            s = futs[f]
            try:
                sym, status, msg = f.result()
            except Exception as e:                                   # noqa: BLE001
                failed.append((s, repr(e)[:120]))
                continue
            done += 1
            if status == "no_rows":
                no_rows.append(sym)
            if status == "fetched":
                print(f"{done}/{len(todo)} {sym}: {msg}", flush=True)
    m = load_manifest()
    m["alpaca_failed"], m["alpaca_no_rows"], m["aliases_used"] = failed, sorted(no_rows), len(al)
    save_manifest(m)
    rehash()
    if failed:
        raise SystemExit(f"{len(failed)} symbols failed (rerun resumes): {failed[:5]}")


# ===================================================================================== report sessions after P8
def p11_sessions():
    """Report sessions after the P8 SEC events end (2026-09-30), from the live Protocol 11 screens on fund-data
    (typed field rows[ticker].report_sessions). Union over the screens; frozen to .cache with its sha256."""
    import subprocess
    m = load_manifest()
    paths = [p for p in subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "origin/fund-data"], text=True,
                                                cwd=ROOT).split() if p.endswith("/p11_screen.json")]
    out = {}
    for p in sorted(paths):
        s = json.loads(subprocess.check_output(["git", "show", f"origin/fund-data:{p}"], text=True, cwd=ROOT))
        for t, row in (s.get("rows") or {}).items():
            out.setdefault(t, set()).update(row.get("report_sessions") or [])
    out = {t: sorted(v) for t, v in out.items()}
    f = os.path.join(CACHE, "p11_report_sessions.json")
    json.dump(out, open(f, "w"), indent=0, sort_keys=True)
    m["daily"][os.path.relpath(f, CACHE)] = sha(f)
    m["p11_screens"] = sorted(paths)
    save_manifest(m)
    print(f"{len(paths)} screens, {len(out)} tickers, {sum(len(v) for v in out.values())} report sessions")


def rehash():
    """Rebuild the manifest's file and daily entries from what is on disk (the fetches ran concurrently and each
    saved its own view). Frozen files are never refetched; this only records their sha256."""
    m = load_manifest()
    m["files"], m["daily"] = {}, {}
    for sub in ("binance", "yahoo"):
        for dp, _, fs in os.walk(os.path.join(CACHE, sub)):
            for f in fs:
                if not f.endswith(".part"):
                    p = os.path.join(dp, f)
                    m["files"][os.path.relpath(p, CACHE)] = sha(p)
    for dp, _, fs in os.walk(DAILY):
        for f in fs:
            if f.endswith(".parquet"):
                p = os.path.join(dp, f)
                m["daily"][os.path.relpath(p, CACHE)] = sha(p)
    f = os.path.join(CACHE, "p11_report_sessions.json")
    if os.path.exists(f):
        m["daily"][os.path.relpath(f, CACHE)] = sha(f)
    save_manifest(m)
    print(f"{len(m['files'])} raw files, {len(m['daily'])} daily files hashed")


# ===================================================================================== coverage (counts only)
def coverage():
    m = load_manifest()
    out = {"written_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "end": END,
           "note": "counts only: no return statistic, forecast or loss is computed here", "series": {}}
    for rel, h in sorted(m["daily"].items()):
        p = os.path.join(CACHE, rel)
        if sha(p) != h:
            raise SystemExit(f"{rel}: sha256 differs from the manifest")
        D = pd.read_parquet(p, columns=None)
        row = {"first": str(D.index.min().date()), "last": str(D.index.max().date()), "days": int(len(D))}
        for k in ("rv_ok", "range_ok"):
            if k in D:
                row[k] = int(D[k].sum())
        if "n_bars" in D:
            row["days_with_intraday"] = int((D["n_bars"] > 0).sum())
        out["series"][rel] = row
    json.dump(out, open(os.path.join(HERE, "COVERAGE.json"), "w"), indent=1)
    print(f"{len(out['series'])} series written to COVERAGE.json")


if __name__ == "__main__":
    if sys.argv[1] == "alpaca" and len(sys.argv) > 2:
        alpaca(sys.argv[2].split(","))
    else:
        {"crypto": crypto, "indices": indices, "alpaca": alpaca, "coverage": coverage, "p11": p11_sessions,
         "rehash": rehash}[sys.argv[1]]()
