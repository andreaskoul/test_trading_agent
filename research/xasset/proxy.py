"""Proxy return constructions for 12-month time-series momentum on US Treasuries and currencies, and their
validation against executable ETFs on the spent 2003-2026 period (research/xasset/SCOPE.md section 7).

    python research/xasset/proxy.py fetch      # download once, freeze sha256 in research/xasset/MANIFEST.json
    python research/xasset/proxy.py coverage   # contracts + coverage counts (all dates; no return computed)
    python research/xasset/proxy.py validate   # constructions and validation statistics, 2003-01-01 onwards only
                                               # -> research/xasset/VALIDATE.json

THE 1962-01 .. 2002-12 RETURNS STAY UNREAD.
    Every return, signal and statistic goes through `validation_window()`, which keeps dates on or after
    2003-01-01. It is applied to the level inputs of every construction *before* any difference is taken, and again
    to every output, so no pre-2003 return exists even in memory. Coverage checks (first/last date, missing-value
    counts, field contracts) are the only computations allowed on all dates; they use presence masks only.
    `COMPUTED` registers every computed series; test_proxy.py fails if any has a date before 2003-01-01.

Treasury excess return (synthetic constant-maturity par bond, maturity N years, from FRED H.15 CMT yields)
    For a period from observation t to t+1 with Delta t = (calendar days) / 365:

        r_{t+1} = y_t Delta t  -  D_t Delta y_{t+1}  +  1/2 C_t (Delta y_{t+1})^2  -  r_f,t Delta t

    * y_t: the N-year CMT yield at t (FRED DGS<N>, daily, "Quoted on an Investment Basis", i.e. bond-equivalent,
      semi-annual), in decimals; Delta y_{t+1} = y_{t+1} - y_t.
    * D_t, C_t: modified duration and convexity of a par bond (coupon c = y_t, semi-annual) at yield y_t.
      With v = 1 / (1 + y/2), cash flows CF_k = c/2 at t_k = k/2 (k = 1..2N) plus 1 at t_{2N}, and P = 1 at par:

          D = sum_k t_k CF_k v^(2 t_k + 1)                 (= (1/y)(1 - v^(2N)) for a par bond)
          C = sum_k t_k (t_k + 1/2) CF_k v^(2 t_k + 2)

    * r_f,t: the 3-month T-bill at t (FRED DTB3, daily, "Discount Basis"), converted to a bond-equivalent yield
      r = 365 d / (360 - 91 d) (the conversion is selected by the series title, a typed field).
    * A diagnostic "exact" variant reprices the par bond issued at t after Delta t at y_{t+1} with remaining maturity
      N - Delta t (dirty price, no coupon paid within the period): r = P(y_{t+1}; N - Delta t) - 1 - r_f,t Delta t.
    * Maturities available from 1962 (FRED daily): 1, 3, 5, 10, 20 years (20-year missing 1987-1993);
      7 years from 1969, 2 years from 1976, 30 years from 1977 (missing 2002-02 .. 2006-02). The maturity N of each
      series is read from the FRED title ("at <N>-Year Constant Maturity"), not from the series id.
    * FRED monthly GS1/GS3/GS5/GS10/TB3MS are monthly averages and fail the point-in-time contract; they are
      downloaded for coverage only. Month-end values are the last daily observation of each calendar month, which
      must fall within the last 7 calendar days of the month.

Currency excess return (USD investor long one unit of foreign currency, i.e. a currency forward under CIP)

        r_{t+1} = Delta log S_{t+1}  +  (i_foreign,t - i_US,t) Delta t

    * S: USD per unit of foreign currency from the Fed H.10 noon buying rates (FRED DEX*, daily). The quote
      direction is read from the FRED "Units" field ("X to One U.S. Dollar" is inverted; "U.S. Dollars to One X" is
      used as is); anything else is a typed defect.
    * i: OECD Main Economic Indicators 3-month interbank rates (FRED IR3TIB01<cc>M156N, monthly, percent), for the
      foreign country and for the US alike. The value of month m (known at the end of month m) accrues over the
      period that starts at the end of month m (monthly), or over the days of month m+1 (daily). No look-ahead.
    * A MISSING DIFFERENTIAL NEVER BECOMES ZERO: the observation is dropped and counted as a typed defect
      `missing_interest_differential` per currency and year.
    * The UUP comparator is minus the ICE US Dollar Index basket of currency excess returns (EUR 0.576, JPY 0.136,
      GBP 0.119, CAD 0.091, SEK 0.042, CHF 0.036); a month missing any member is dropped (defect).

Validation (2003-01-01 onwards, spent; validation statistics of instruments, not strategy performance)
    Monthly excess returns of proxy and ETF on the same months (ETF total return from the Yahoo adjusted close, less
    the same cash leg the proxy uses), per declared pair: correlation, tracking error (%/yr), mean difference
    (proxy - ETF, %/yr, Newey-West SE, lags floor(4 (T/100)^(2/9))), 12-month TSMOM sign agreement
    (sign of the compounded 12-month excess return), and the difference in sign switches per year.
    No Sharpe ratio or mean return of any trend strategy is computed.
"""
import hashlib
import html as htmllib
import json
import math
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(ROOT, ".cache", "xasset-proxy")
MANIFEST = os.path.join(HERE, "MANIFEST.json")
OUT = os.path.join(HERE, "VALIDATE.json")

VALID_START = pd.Timestamp("2003-01-01")
FETCH_DATE = pd.Timestamp("2026-11-25")      # data later than the last complete month before this are not used

# ------------------------------------------------------------------ declared universe (fixed before any statistic)
TREASURY_IDS = ["DGS1", "DGS2", "DGS3", "DGS5", "DGS7", "DGS10", "DGS20", "DGS30"]
RF_ID = "DTB3"
MONTHLY_AVG_IDS = ["GS1", "GS3", "GS5", "GS10", "TB3MS"]          # coverage only (monthly averages)

# currency: (H.10 spot id, expected foreign-currency name in the FRED Units field, OECD 3m id, ETF, plausible S range
# in the series' own quote units)
CCY = {
    "EUR": ("DEXUSEU", "Euro", "IR3TIB01EZM156N", "FXE", (0.6, 1.8)),
    "JPY": ("DEXJPUS", "Japanese Yen", "IR3TIB01JPM156N", "FXY", (50.0, 400.0)),
    "GBP": ("DEXUSUK", "U.K. Pound", "IR3TIB01GBM156N", "FXB", (0.9, 3.0)),
    "CHF": ("DEXSZUS", "Swiss Franc", "IR3TIB01CHM156N", "FXF", (0.5, 5.0)),
    "AUD": ("DEXUSAL", "Australian Dollar", "IR3TIB01AUM156N", "FXA", (0.4, 1.6)),
    "CAD": ("DEXCAUS", "Canadian Dollar", "IR3TIB01CAM156N", "FXC", (0.8, 1.9)),
    "SEK": ("DEXSDUS", "Swedish Kron", "IR3TIB01SEM156N", None, (3.0, 13.0)),
    "NOK": ("DEXNOUS", "Norwegian Kron", "IR3TIB01NOM156N", None, (4.0, 13.0)),
    "DKK": ("DEXDNUS", "Danish Kron", "IR3TIB01DKM156N", None, (4.0, 13.0)),
}
US_RATE_ID = "IR3TIB01USM156N"
DEM_MONTHLY_ID = "EXGEUS"                                         # coverage only (monthly average, to 2001)
DEM_RATE_ID = "IR3TIB01DEM156N"                                   # coverage only
# fallback candidates for the pre-1999/2002 CHF and JPY carry gap: coverage + a 2003+ diagnostic only
CALL_MONEY = {"JPY": "IRSTCI01JPM156N", "CHF": "IRSTCI01CHM156N"}
DXY_WEIGHTS = {"EUR": 0.576, "JPY": 0.136, "GBP": 0.119, "CAD": 0.091, "SEK": 0.042, "CHF": 0.036}

ETFS = {"SHY": "2002-07-30", "IEI": "2007-01-11", "IEF": "2002-07-30", "TLT": "2002-07-30", "FXE": "2005-12-12",
        "FXY": "2007-02-13", "FXB": "2006-06-26", "FXF": "2006-06-26", "FXA": "2006-06-26", "FXC": "2006-06-26",
        "UUP": "2007-03-01"}                                      # first trade dates, SCOPE.json (Yahoo metadata)

# (ETF, proxy, role). Primary pairs decide; alternates show which other maturities track the same instrument.
TREASURY_PAIRS = [("SHY", "DGS2", "primary"), ("SHY", "DGS1", "alternate"), ("SHY", "DGS3", "alternate"),
                  ("IEI", "DGS5", "primary"), ("IEI", "DGS7", "alternate"),
                  ("IEF", "DGS10", "primary"), ("IEF", "DGS7", "alternate"),
                  ("TLT", "DGS20", "primary"), ("TLT", "DGS30", "alternate")]
FX_PAIRS = [("FXE", "EUR"), ("FXY", "JPY"), ("FXB", "GBP"), ("FXF", "CHF"), ("FXA", "AUD"), ("FXC", "CAD"),
            ("UUP", "-DXY")]

# Proposed validation thresholds, fixed in this file before any validation statistic was computed.
THRESHOLDS = {
    "corr_min": 0.95,                    # monthly excess returns
    "te_max_share_of_etf_vol": 0.35,     # tracking error <= 0.35 x ETF volatility (corr 0.95 at equal vol = 0.32)
    "abs_bias_max_pct_per_year": 1.0,    # |mean(proxy - ETF)|; ETF expense ratios (0.15-0.80 %/yr) count against it
    "signal_agreement_min": 0.90,        # share of months with the same 12-month TSMOM sign
    "abs_switch_diff_max_per_year": 0.5,  # |sign switches per year, proxy - ETF|
}

COMPUTED = {}          # name -> computed series (returns, signals); checked by test_proxy.py for the date mask


class InputDefect(Exception):
    """A source failed its content contract (CLAUDE.md rules 1-4): it is not used."""


# ------------------------------------------------------------------ the mask
def validation_window(x):
    """Keep only dates on or after 2003-01-01 (the spent modern period). Every computation goes through this."""
    if not isinstance(x.index, pd.DatetimeIndex):
        raise TypeError("validation_window needs a DatetimeIndex")
    return x.loc[x.index >= VALID_START]


def _register(name, s):
    s = validation_window(s)
    COMPUTED[name] = s
    return s


def assert_masked(registry=None):
    """Raise if any computed series has a date before 2003-01-01 (the test's check)."""
    bad = {k: str(v.index.min().date()) for k, v in (registry if registry is not None else COMPUTED).items()
           if len(v) and v.index.min() < VALID_START}
    if bad:
        raise AssertionError(f"computed series with dates before {VALID_START.date()}: {sorted(bad)}")


# ------------------------------------------------------------------ download once, freeze
def _manifest():
    return json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {"note": "sha256 at first fetch", "files": {}}


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def frozen(name):
    """Path of a frozen file after checking it against its sha256 (a mismatch or a missing file is a defect)."""
    m = _manifest()["files"].get(name)
    p = os.path.join(CACHE, name)
    if m is None:
        raise InputDefect(f"{name}: not in MANIFEST.json (run fetch)")
    if not os.path.exists(p):
        raise InputDefect(f"{name}: frozen file missing from {CACHE}; refusing to re-download a new vintage")
    if _sha(p) != m["sha256"]:
        raise InputDefect(f"{name}: sha256 differs from the manifest")
    return p


def _record(name, url, p):
    m = _manifest()
    m["files"][name] = {"source": url, "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "bytes": os.path.getsize(p), "sha256": _sha(p)}
    json.dump(m, open(MANIFEST, "w"), indent=1, sort_keys=True)


def _get(url, tries=4):
    # generic client: Python's default urllib User-Agent; no personal details
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:                                      # noqa: BLE001
            last = e
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"{url}: {last}")


def fetch_url(name, url):
    if name in _manifest()["files"]:
        return frozen(name)
    os.makedirs(CACHE, exist_ok=True)
    b = _get(url)
    p = os.path.join(CACHE, name)
    open(p, "wb").write(b)
    _record(name, url, p)
    return p


def fetch_fred(sid):
    fetch_url(f"fred_{sid}.csv", f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
    fetch_url(f"fred_{sid}.html", f"https://fred.stlouisfed.org/series/{sid}")


def fetch_etf(t):
    name = f"yahoo_{t}.csv"
    if name in _manifest()["files"]:
        return frozen(name)
    import yfinance as yf
    end = FETCH_DATE.strftime("%Y-%m-%d")
    h = yf.Ticker(t).history(start="2002-01-01", end=end, auto_adjust=False, actions=True)
    if h is None or h.empty:
        raise InputDefect(f"{t}: no rows from Yahoo")
    h.index = pd.DatetimeIndex(h.index).tz_localize(None).normalize()
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    h[["Close", "Adj Close", "Dividends", "Stock Splits"]].to_csv(p, index_label="Date")
    _record(name, f"yfinance {yf.__version__} Ticker('{t}').history(start='2002-01-01', end='{end}', "
                  "auto_adjust=False, actions=True)", p)
    return p


def all_fred_ids():
    ids = TREASURY_IDS + [RF_ID] + MONTHLY_AVG_IDS + [US_RATE_ID, DEM_MONTHLY_ID, DEM_RATE_ID]
    for spot, _, rate, _, _ in CCY.values():
        ids += [spot, rate]
    return ids + list(CALL_MONEY.values())


def fetch_all():
    failed = {}
    for sid in all_fred_ids():
        try:
            fetch_fred(sid)
        except Exception as e:                                      # noqa: BLE001
            failed[sid] = str(e)[:200]
    for t in ETFS:
        try:
            fetch_etf(t)
        except Exception as e:                                      # noqa: BLE001
            failed[t] = str(e)[:200]
    return failed


# ------------------------------------------------------------------ content contracts
def fred_meta(sid):
    """Typed fields of the FRED series page: title, units, frequency, release, notes."""
    b = open(frozen(f"fred_{sid}.html"), encoding="utf8", errors="replace").read()
    title = re.search(r'<meta property="og:title" content="([^"]*)"', b)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S)
    t = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", t)))
    units = re.search(r"Units:\s*(.+?)\s*,\s*(?:Not )?Seasonally Adjusted", t)
    freq = re.search(r"Frequency:\s*([A-Za-z]+(?:, [A-Za-z ]+)?)\s", t)
    notes = re.search(r"Notes:\s*(.{0,600})", t)
    if not (title and units and freq):
        raise InputDefect(f"{sid}: FRED page lacks a typed title/units/frequency field")
    return {"title": htmllib.unescape(title.group(1)).strip(), "units": units.group(1).strip(),
            "frequency": freq.group(1).strip(), "notes": notes.group(1) if notes else ""}


def fred_csv(sid):
    """The raw FRED series (levels in the source's units) after the CSV contract; blanks stay NaN."""
    p = frozen(f"fred_{sid}.csv")
    first = open(p, encoding="utf8").readline().strip()
    if first not in (f"observation_date,{sid}", f"DATE,{sid}"):
        raise InputDefect(f"{sid}: CSV header {first[:60]!r} does not name the series")
    raw = pd.read_csv(p, dtype=str)
    d = pd.to_datetime(raw.iloc[:, 0], format="%Y-%m-%d", errors="coerce")
    if d.isna().any():
        raise InputDefect(f"{sid}: {int(d.isna().sum())} unparseable dates")
    v = pd.to_numeric(raw.iloc[:, 1].replace({".": None, "": None}), errors="coerce")
    nonnum = int((raw.iloc[:, 1].notna() & ~raw.iloc[:, 1].isin([".", ""]) & v.isna()).sum())
    if nonnum:
        raise InputDefect(f"{sid}: {nonnum} non-numeric values")
    s = pd.Series(v.values, index=pd.DatetimeIndex(d), name=sid)
    if not s.index.is_monotonic_increasing or s.index.has_duplicates:
        raise InputDefect(f"{sid}: dates not strictly increasing")
    return s


def check_series(sid, s, meta, freq, units_re, lo, hi, title_re=None, max_last_age_days=None):
    """Contract on dates, units, frequency and plausible range (all dates; values are never printed)."""
    if meta["frequency"] != freq:
        raise InputDefect(f"{sid}: declared frequency {meta['frequency']!r}, expected {freq!r}")
    if not re.fullmatch(units_re, meta["units"]):
        raise InputDefect(f"{sid}: declared units {meta['units']!r} do not match {units_re!r}")
    if title_re and not re.search(title_re, meta["title"]):
        raise InputDefect(f"{sid}: title {meta['title']!r} lacks {title_re!r}")
    x = s.dropna()
    if len(x) < 24:
        raise InputDefect(f"{sid}: {len(x)} values")
    gaps = np.diff(x.index.values).astype("timedelta64[D]").astype(int)
    med = float(np.median(gaps))
    if (freq == "Daily" and med > 3) or (freq == "Monthly" and not 28 <= med <= 31):
        raise InputDefect(f"{sid}: median spacing {med} days is not {freq}")
    if freq == "Monthly" and not (x.index.day == 1).all():
        raise InputDefect(f"{sid}: monthly dates not first-of-month")
    out = int(((x < lo) | (x > hi)).sum())
    if out:
        raise InputDefect(f"{sid}: {out} values outside the plausible range [{lo}, {hi}]")
    age = (FETCH_DATE - x.index.max()).days
    if max_last_age_days is not None and age > max_last_age_days:
        raise InputDefect(f"{sid}: last value {age} days before the fetch date")
    return {"first": str(x.index.min().date()), "last": str(x.index.max().date()), "values": int(len(x)),
            "blank_rows": int(s.isna().sum()), "max_gap_days": int(gaps.max()), "units": meta["units"],
            "frequency": meta["frequency"], "title": meta["title"]}


def treasury_series(sid):
    meta = fred_meta(sid)
    s = fred_csv(sid)
    c = check_series(sid, s, meta, "Daily", r"Percent", -1.0, 20.0,
                     title_re=r"Treasury Securities at \d+-Year Constant Maturity, Quoted on an Investment Basis",
                     max_last_age_days=10)
    c["maturity_years"] = int(re.search(r"at (\d+)-Year Constant Maturity", meta["title"]).group(1))
    # values inside a discontinuation declared in the series notes are not the series: typed defect, removed
    m = re.search(r"discontinued on (\w+ \d+, \d{4}),? and reintroduced on (\w+ \d+, \d{4})", meta["notes"])
    if m:
        a, b = (pd.Timestamp(datetime.strptime(g, "%B %d, %Y")) for g in m.groups())
        inside = (s.index >= a) & (s.index < b) & s.notna().values
        c["declared_discontinuation"] = [str(a.date()), str(b.date())]
        c["values_inside_discontinuation_removed"] = int(inside.sum())
        s = s.where(~inside)
    return s / 100.0, c


def tbill_series():
    meta = fred_meta(RF_ID)
    s = fred_csv(RF_ID)
    c = check_series(RF_ID, s, meta, "Daily", r"Percent", -1.0, 20.0, title_re=r"3-Month Treasury Bill",
                     max_last_age_days=10)
    d = s / 100.0
    if "Discount Basis" in meta["title"]:
        d = 365 * d / (360 - 91 * d)
        c["conversion"] = "discount basis -> bond-equivalent 365 d / (360 - 91 d) (from the title)"
    else:
        raise InputDefect(f"{RF_ID}: title does not declare a discount basis; quote convention unknown")
    return d, c


def spot_series(ccy):
    """USD per unit of foreign currency; the direction comes from the declared Units field."""
    sid, name, _, _, (lo, hi) = CCY[ccy]
    meta = fred_meta(sid)
    s = fred_csv(sid)
    c = check_series(sid, s, meta, "Daily", r".+ to One .+", lo, hi, title_re=r"Spot Exchange Rate",
                     max_last_age_days=14)
    if "H.10" not in meta["notes"] + open(frozen(f"fred_{sid}.html"), encoding="utf8", errors="replace").read():
        raise InputDefect(f"{sid}: release H.10 not declared")
    num, den = re.fullmatch(r"(.+) to One (.+)", meta["units"]).groups()
    if den == "U.S. Dollar" and num.startswith(name):
        c["direction"] = "foreign per USD -> inverted"
        return 1.0 / s, c
    if num == "U.S. Dollars" and den.startswith(name):
        c["direction"] = "USD per foreign"
        return s, c
    raise InputDefect(f"{sid}: units {meta['units']!r} are not {name} against the U.S. dollar")


def rate_series(sid, max_last_age_days=None):
    """OECD MEI monthly short rate, decimals, indexed by the first day of the month."""
    meta = fred_meta(sid)
    s = fred_csv(sid)
    c = check_series(sid, s, meta, "Monthly", r"Percent", -2.0, 60.0, max_last_age_days=max_last_age_days)
    c["averaging_declared"] = bool(re.search(r"averag", meta["notes"], re.I))
    return s / 100.0, c


def etf_series(t):
    """Adjusted close (total return incl. distributions) after the ETF contract."""
    p = frozen(f"yahoo_{t}.csv")
    d = pd.read_csv(p, parse_dates=["Date"]).set_index("Date")
    for col in ("Close", "Adj Close", "Dividends"):
        if col not in d.columns:
            raise InputDefect(f"{t}: column {col} missing")
    if not d.index.is_monotonic_increasing or d.index.has_duplicates:
        raise InputDefect(f"{t}: dates not strictly increasing")
    bad = d[["Close", "Adj Close"]].isna().any(axis=1) | (d[["Close", "Adj Close"]] <= 0).any(axis=1)
    dropped_last = False
    if bad.iloc[-1] and bad.sum() == 1:                 # the in-progress session at fetch time: drop, record
        d, dropped_last = d.iloc[:-1], True
    elif bad.any():
        raise InputDefect(f"{t}: {int(bad.sum())} rows with non-positive or missing prices")
    lag = (d.index.min() - pd.Timestamp(ETFS[t])).days
    if not 0 <= lag <= 7:
        raise InputDefect(f"{t}: first row {d.index.min().date()} is {lag} days from the declared inception")
    if (FETCH_DATE - d.index.max()).days > 7:
        raise InputDefect(f"{t}: stale last row")
    # coverage against the NYSE sessions implied by SPY-free calendar: business days minus a holiday allowance
    bdays = pd.bdate_range(d.index.min(), d.index.max())
    share = len(d) / len(bdays)
    if share < 0.955:                                   # ~9-10 NYSE holidays a year = ~0.962 of business days
        raise InputDefect(f"{t}: {len(d)} rows for {len(bdays)} business days ({share:.3f})")
    jump = int((d["Adj Close"].pct_change().abs() > 0.25).sum())
    if jump:
        raise InputDefect(f"{t}: {jump} daily moves above 25 % (unadjusted split?)")
    return d["Adj Close"], {"first": str(d.index.min().date()), "last": str(d.index.max().date()),
                            "rows": int(len(d)), "rows_per_business_day": round(share, 4),
                            "incomplete_last_row_dropped": dropped_last,
                            "dividend_rows": int((d["Dividends"] > 0).sum())}


def etf_adjustment_check(t):
    """Contract: monthly total return from the adjusted close agrees with close + dividends (2003+ only)."""
    p = frozen(f"yahoo_{t}.csv")
    d = validation_window(pd.read_csv(p, parse_dates=["Date"]).set_index("Date")).dropna(subset=["Close", "Adj Close"])
    tr_close = (d["Close"] + d["Dividends"]) / d["Close"].shift(1)
    tr_adj = d["Adj Close"] / d["Adj Close"].shift(1)
    lm = np.log(tr_close).groupby(d.index.to_period("M")).sum()
    la = np.log(tr_adj).groupby(d.index.to_period("M")).sum()
    dev = (lm - la).abs().iloc[1:]
    return {"months": int(len(dev)), "months_dev_over_5bp": int((dev > 5e-4).sum()),
            "max_abs_dev_bp": round(float(dev.max() * 1e4), 2)}


# ------------------------------------------------------------------ sampling
def month_end(s, max_stale_days=7):
    """Last valid observation of each calendar month, labelled by the month's end; months whose last observation is
    more than `max_stale_days` before the month end are dropped, and months not complete by FETCH_DATE too."""
    x = s.dropna()
    g = x.groupby(x.index.to_period("M"))
    last_date = g.apply(lambda v: v.index.max())
    val = g.last()
    me = val.index.to_timestamp(how="end").normalize()
    ok = ((me - pd.DatetimeIndex(last_date.values)).days <= max_stale_days) & (me < FETCH_DATE)
    return pd.Series(val.values[ok], index=me[ok], name=s.name)


def _consecutive_months(idx):
    p = idx.to_period("M")
    return np.r_[False, (p[1:] - p[:-1]).map(lambda o: o.n) == 1]


# ------------------------------------------------------------------ constructions
def par_duration_convexity(y, n_years):
    """Modified duration and convexity of a semi-annual par bond at yield y (decimals, array)."""
    y = np.asarray(y, float)[..., None]
    t = np.arange(1, 2 * n_years + 1) / 2.0
    c = y
    cf = np.broadcast_to(c / 2, y.shape[:-1] + t.shape).copy()
    cf[..., -1] += 1.0
    v = 1.0 / (1.0 + y / 2.0)
    D = (t * cf * v ** (2 * t + 1)).sum(-1)
    C = (t * (t + 0.5) * cf * v ** (2 * t + 2)).sum(-1)
    return D, C


def _par_price_after(y0, y1, n_years, dt):
    """Dirty price after dt years of a par bond (coupon y0, maturity n) at yield y1; dt < 0.5."""
    y0, y1, dt = (np.asarray(a, float)[..., None] for a in (y0, y1, dt))
    t = np.arange(1, 2 * n_years + 1) / 2.0
    cf = np.broadcast_to(y0 / 2, np.broadcast(y0, t).shape).copy()
    cf[..., -1] += 1.0
    return (cf * (1.0 + y1 / 2.0) ** (-2.0 * (t - dt))).sum(-1)


def treasury_excess(y, rf, n_years, monthly, method="taylor", name=None):
    """Excess return of a synthetic N-year par bond. y, rf: yields in decimals (rf bond-equivalent) by date; for
    monthly, y must be month-end sampled. Periods spanning a missing month (monthly) or > 7 days (daily) are dropped."""
    y = validation_window(y.dropna())
    rf = validation_window(rf.dropna())
    rf_t = rf.reindex(y.index, method="ffill")
    dt = pd.Series(np.r_[np.nan, np.diff(y.index.values).astype("timedelta64[D]").astype(int)], index=y.index) / 365.0
    ok = _consecutive_months(y.index) if monthly else np.r_[False, dt.values[1:] * 365 <= 7]
    y0, y1, r0 = y.shift(1), y, rf_t.shift(1)
    if method == "taylor":
        D, C = par_duration_convexity(y0.fillna(0.05).values, n_years)
        dy = y1 - y0
        r = y0 * dt - D * dy + 0.5 * C * dy ** 2 - r0 * dt
    elif method == "exact":
        P = _par_price_after(y0.fillna(0.05).values, y1.values, n_years, dt.fillna(0).values)
        r = pd.Series(P - 1.0, index=y.index) - r0 * dt
    else:
        raise ValueError(method)
    r = r[ok & y0.notna().values & r0.notna().values]
    return _register(name or f"tsy_{n_years}y_{'m' if monthly else 'd'}_{method}", r)


def currency_excess(spot_usd, i_f, i_us, ccy, monthly, name=None):
    """(excess returns, defects) of a long-foreign-currency position. spot_usd: USD per foreign unit by date
    (month-end sampled if monthly). i_f, i_us: monthly decimals indexed by first-of-month. A missing differential
    drops the observation and is recorded as a typed defect (never zero)."""
    S = validation_window(spot_usd.dropna())
    i_f, i_us = validation_window(i_f), validation_window(i_us)
    per = S.index.to_period("M")
    src = per if monthly else per - 1                       # month whose rate accrues over the period starting at t
    diff_t = pd.Series((i_f.reindex(src.to_timestamp()).values - i_us.reindex(src.to_timestamp()).values),
                       index=S.index)
    dt = pd.Series(np.r_[np.nan, np.diff(S.index.values).astype("timedelta64[D]").astype(int)], index=S.index) / 365.0
    ok = _consecutive_months(S.index) if monthly else np.r_[False, dt.values[1:] * 365 <= 7]
    d0 = diff_t.shift(1)
    r = np.log(S / S.shift(1)) + d0 * dt
    valid_period = pd.Series(ok, index=S.index) & S.shift(1).notna()
    missing = valid_period & d0.isna()
    defects = [{"kind": "missing_interest_differential", "currency": ccy, "year": int(y), "count": int(n)}
               for y, n in missing[missing].groupby(missing[missing].index.year).size().items()]
    r = r[valid_period & d0.notna()]
    return _register(name or f"fx_{ccy}_{'m' if monthly else 'd'}", r), defects


def dxy_basket(fx_returns, name="fx_-DXY_m"):
    """Minus the dollar-index-weighted sum of currency excess returns (long USD); incomplete months dropped."""
    df = pd.DataFrame({c: validation_window(fx_returns[c]) for c in DXY_WEIGHTS})
    full = df.notna().all(axis=1)
    r = -(df[full] * pd.Series(DXY_WEIGHTS)).sum(axis=1)
    defects = [{"kind": "basket_incomplete", "currency": "-DXY", "year": int(y), "count": int(n)}
               for y, n in (~full)[~full].groupby(df.index[~full].year).size().items()]
    return _register(name, r), defects


def etf_excess(adj, cash, monthly, cash_monthly_rate=False, name=None):
    """ETF total-return excess over the same cash leg the proxy uses.
    cash: daily bond-equivalent T-bill (as of t) or, if cash_monthly_rate, monthly decimals by first-of-month."""
    P = validation_window(month_end(adj) if monthly else adj.dropna())
    dt = pd.Series(np.r_[np.nan, np.diff(P.index.values).astype("timedelta64[D]").astype(int)], index=P.index) / 365.0
    if cash_monthly_rate:
        per = P.index.to_period("M")
        src = per if monthly else per - 1
        c_t = pd.Series(validation_window(cash).reindex(src.to_timestamp()).values, index=P.index)
    else:
        c_t = validation_window(cash.dropna()).reindex(P.index, method="ffill")
    ok = _consecutive_months(P.index) if monthly else np.r_[False, dt.values[1:] * 365 <= 7]
    r = P / P.shift(1) - 1 - c_t.shift(1) * dt
    r = r[ok & c_t.shift(1).notna().values & P.shift(1).notna().values]
    return _register(name or "etf", r)


# ------------------------------------------------------------------ validation statistics (2003+ only)
def nw_lags(T):
    return int(math.floor(4 * (T / 100.0) ** (2.0 / 9.0)))


def hac_mean(x, lags):
    x = np.asarray(x, float)
    n, e = len(x), x - x.mean()
    v = e @ e / n
    for lag in range(1, lags + 1):
        v += 2 * (1 - lag / (lags + 1)) * (e[lag:] @ e[:-lag]) / n
    return float(x.mean()), float(math.sqrt(v / n))


def tsmom_sign(r, name):
    """Sign of the compounded 12-month excess return ending at t (needs 12 consecutive months)."""
    r = validation_window(r)
    lr = np.log1p(r)
    cons = pd.Series(_consecutive_months(r.index), index=r.index).astype(int)
    run = cons.groupby((cons == 0).cumsum()).cumsum() + 1            # length of the consecutive run ending at t
    s12 = lr.rolling(12).sum()
    sig = np.sign(s12[run >= 12])
    return _register(name, sig)


def switches_per_year(sig):
    cons = _consecutive_months(sig.index)
    ch = (sig != sig.shift(1)) & cons
    years = cons.sum() / 12.0
    return float(ch.sum() / years) if years else float("nan")


def pair_stats(proxy, etf, label):
    j = pd.concat([validation_window(proxy).rename("p"), validation_window(etf).rename("e")], axis=1).dropna()
    T = len(j)
    d = j.p - j.e
    L = nw_lags(T)
    mu, se = hac_mean(d.values, L)
    vol_e = float(j.e.std(ddof=1) * math.sqrt(12))
    vol_p = float(j.p.std(ddof=1) * math.sqrt(12))
    te = float(d.std(ddof=1) * math.sqrt(12))
    # signals on the joint months only (same windows)
    sp = tsmom_sign(j.p, f"sig_proxy_{label}")
    se_ = tsmom_sign(j.e, f"sig_etf_{label}")
    k = pd.concat([sp.rename("p"), se_.rename("e")], axis=1).dropna()
    agree = float((k.p == k.e).mean())
    sw_p, sw_e = switches_per_year(k.p), switches_per_year(k.e)
    beta = float(np.cov(j.e, j.p, ddof=1)[0, 1] / np.var(j.p, ddof=1))
    res = {
        "window": [str(j.index.min().date()), str(j.index.max().date())], "months": T,
        "corr": round(float(j.p.corr(j.e)), 4),
        "tracking_error_pct_per_year": round(100 * te, 3),
        "te_share_of_etf_vol": round(te / vol_e, 3),
        "mean_diff_pct_per_year": round(1200 * mu, 3), "mean_diff_hac_se_pct_per_year": round(1200 * se, 3),
        "hac_lags": L,
        "vol_proxy_pct_per_year": round(100 * vol_p, 2), "vol_etf_pct_per_year": round(100 * vol_e, 2),
        "beta_etf_on_proxy": round(beta, 3),
        "signal_months": int(len(k)), "signal_agreement": round(agree, 4),
        "switches_per_year_proxy": round(sw_p, 3), "switches_per_year_etf": round(sw_e, 3),
        "switch_diff_per_year": round(sw_p - sw_e, 3),
    }
    th = THRESHOLDS
    checks = {"corr": res["corr"] >= th["corr_min"],
              "tracking_error": res["te_share_of_etf_vol"] <= th["te_max_share_of_etf_vol"],
              "bias": abs(res["mean_diff_pct_per_year"]) <= th["abs_bias_max_pct_per_year"],
              "signal_agreement": res["signal_agreement"] >= th["signal_agreement_min"],
              "turnover": abs(res["switch_diff_per_year"]) <= th["abs_switch_diff_max_per_year"]}
    res["checks"] = checks
    res["validates"] = all(checks.values())
    return res


def daily_diag(proxy_d, etf_d):
    j = pd.concat([validation_window(proxy_d).rename("p"), validation_window(etf_d).rename("e")], axis=1).dropna()
    return {"days": int(len(j)), "corr_daily": round(float(j.p.corr(j.e)), 4),
            "vol_ratio_proxy_over_etf": round(float(j.p.std() / j.e.std()), 3)}


# ------------------------------------------------------------------ coverage (all dates; presence masks only)
def coverage_months(s, start, end):
    """Number of calendar months in [start, end] with a valid (non-stale) month-end observation."""
    present = month_end(s).notna()                       # values are not used, only their presence
    pm = present.index.to_period("M")
    idx = present.index[(pm >= pd.Period(start, "M")) & (pm <= pd.Period(end, "M"))]
    expected = len(pd.period_range(start, end, freq="M"))
    got = pd.PeriodIndex(idx.to_period("M")).unique()
    missing = sorted(set(pd.period_range(start, end, freq="M")) - set(got))
    spans = _spans(missing)
    return {"expected_months": expected, "months_present": int(len(got)), "missing_spans": spans}


def _spans(periods):
    out, cur = [], None
    for p in periods:
        if cur and (p - cur[1]).n == 1:
            cur[1] = p
        else:
            if cur:
                out.append(f"{cur[0]}..{cur[1]}")
            cur = [p, p]
    if cur:
        out.append(f"{cur[0]}..{cur[1]}")
    return out


def coverage_differential(spot, i_f, i_us, ccy, start, end):
    """Counts per year of month-end periods with spot at both ends but a missing interest differential, on all dates.
    Presence only: no return or differential value is computed."""
    have_s = month_end(spot).notna()
    pm = have_s.index.to_period("M")
    have_s = have_s[(pm >= pd.Period(start, "M")) & (pm <= pd.Period(end, "M"))]
    per = have_s.index.to_period("M")
    cons = _consecutive_months(have_s.index)
    src = (per - 1).to_timestamp()                       # rate of the month in which the period starts
    hf = i_f.notna().reindex(src).fillna(False).astype(bool).values
    hu = i_us.notna().reindex(src).fillna(False).astype(bool).values
    periods = pd.Series(cons, index=have_s.index)
    miss = periods & ~(hf & hu)
    by_year = miss[miss].groupby(miss[miss].index.year).size()
    return {"periods_with_spot": int(periods.sum()), "periods_complete": int((periods & hf & hu).sum()),
            "missing_differential": int(miss.sum()),
            "missing_foreign_rate": int((periods & ~hf).sum()), "missing_us_rate": int((periods & ~hu).sum()),
            "missing_differential_by_year": {int(y): int(n) for y, n in by_year.items()}}


def run_coverage():
    res = {"contracts": {}, "defects": [], "treasury": {}, "fx": {}}
    for sid in TREASURY_IDS:
        try:
            y, c = treasury_series(sid)
            res["contracts"][sid] = c
            res["treasury"][sid] = {"1962-01..2002-12": coverage_months(y, "1962-01", "2002-12"),
                                    "2003-01..2026-10": coverage_months(y, "2003-01", "2026-10")}
        except InputDefect as e:
            res["defects"].append({"kind": "input_defect", "source": sid, "detail": str(e)})
    for sid, fn in [(RF_ID, lambda: tbill_series())]:
        try:
            s, c = fn()
            res["contracts"][sid] = c
            res["treasury"][sid] = {"1962-01..2002-12": coverage_months(s, "1962-01", "2002-12")}
        except InputDefect as e:
            res["defects"].append({"kind": "input_defect", "source": sid, "detail": str(e)})
    for sid in MONTHLY_AVG_IDS + [DEM_MONTHLY_ID]:
        try:
            meta = fred_meta(sid)
            s = fred_csv(sid)
            res["contracts"][sid] = {"first": str(s.dropna().index.min().date()),
                                     "last": str(s.dropna().index.max().date()), "values": int(s.notna().sum()),
                                     "frequency": meta["frequency"], "title": meta["title"],
                                     "averaging_declared": bool(re.search(r"averag", meta["notes"], re.I)),
                                     "verdict": "excluded: monthly frequency (not a point-in-time month-end)"}
        except InputDefect as e:
            res["defects"].append({"kind": "input_defect", "source": sid, "detail": str(e)})
    rates = {}
    for sid in [US_RATE_ID, DEM_RATE_ID] + [v[2] for v in CCY.values()] + list(CALL_MONEY.values()):
        try:
            r, c = rate_series(sid)
            rates[sid] = r
            res["contracts"][sid] = c
        except InputDefect as e:
            res["defects"].append({"kind": "input_defect", "source": sid, "detail": str(e)})
    us = rates.get(US_RATE_ID)
    for ccy, (sid, _, rid, _, _) in CCY.items():
        try:
            s, c = spot_series(ccy)
            res["contracts"][sid] = c
            ent = {"spot_1972-01..2002-12": coverage_months(s, "1972-01", "2002-12")}
            if us is not None and rid in rates:
                ent["differential_1972-01..2002-12"] = coverage_differential(s, rates[rid], us, ccy,
                                                                             "1972-01", "2002-12")
                ent["differential_all_dates"] = coverage_differential(s, rates[rid], us, ccy, "1971-01", "2026-10")
                if ccy in CALL_MONEY and CALL_MONEY[ccy] in rates:
                    ent["differential_1972-01..2002-12_call_money_fallback"] = coverage_differential(
                        s, rates[rid].combine_first(rates[CALL_MONEY[ccy]]), us, ccy, "1972-01", "2002-12")
            res["fx"][ccy] = ent
        except InputDefect as e:
            res["defects"].append({"kind": "input_defect", "source": sid, "detail": str(e)})
    for t in ETFS:
        try:
            _, c = etf_series(t)
            c["adjustment_check_2003+"] = etf_adjustment_check(t)
            res["contracts"][t] = c
        except InputDefect as e:
            res["defects"].append({"kind": "input_defect", "source": t, "detail": str(e)})
    return res


# ------------------------------------------------------------------ validation run
def run_validation():
    COMPUTED.clear()
    out = {"window_rule": f"every series masked to dates >= {VALID_START.date()} by validation_window()",
           "thresholds": THRESHOLDS, "treasury": [], "fx": [], "diagnostics": {}, "defects": []}
    rf, _ = tbill_series()
    rf = validation_window(rf)
    tsy_m, tsy_d, mats = {}, {}, {}
    for sid in TREASURY_IDS:
        y, c = treasury_series(sid)
        y = validation_window(y)
        mats[sid] = c["maturity_years"]
        tsy_m[sid] = treasury_excess(month_end(y), rf, mats[sid], monthly=True, name=f"tsy_{sid}_m")
        ex = treasury_excess(month_end(y), rf, mats[sid], monthly=True, method="exact", name=f"tsy_{sid}_m_exact")
        j = pd.concat([tsy_m[sid], ex], axis=1).dropna()
        out["diagnostics"][f"{sid}_taylor_vs_exact_monthly"] = {
            "months": int(len(j)), "corr": round(float(j.iloc[:, 0].corr(j.iloc[:, 1])), 6),
            "abs_diff_pct_per_year_mean": round(float(1200 * (j.iloc[:, 0] - j.iloc[:, 1]).abs().mean()), 4)}
    etf_m, etf_px = {}, {}
    for t in ["SHY", "IEI", "IEF", "TLT"]:
        etf_px[t], _ = etf_series(t)
        etf_m[t] = etf_excess(etf_px[t], rf, monthly=True, name=f"etf_{t}_m")
    for t, sid, role in TREASURY_PAIRS:
        r = pair_stats(tsy_m[sid], etf_m[t], f"{t}_{sid}")
        r.update({"etf": t, "proxy": f"{mats[sid]}y par bond ({sid})", "role": role})
        if role == "primary":
            y, _ = treasury_series(sid)
            px = validation_window(etf_px[t])
            y = validation_window(y).dropna()
            common = y.index.intersection(px.index)
            pd_ = treasury_excess(y.reindex(common), rf, mats[sid], monthly=False, name=f"tsy_{sid}_d")
            ed = etf_excess(px.reindex(common), rf, monthly=False, name=f"etf_{t}_d")
            r["daily_diagnostic"] = daily_diag(pd_, ed)
        out["treasury"].append(r)

    i_us, _ = rate_series(US_RATE_ID)
    fx_m, spots, rates = {}, {}, {}
    for ccy, (sid, _, rid, etf, _) in CCY.items():
        s, _ = spot_series(ccy)
        spots[ccy] = validation_window(s)
        rates[ccy], _ = rate_series(rid)
        fx_m[ccy], dfx = currency_excess(month_end(spots[ccy]), rates[ccy], i_us, ccy, monthly=True)
        out["defects"] += dfx
    basket, dfx = dxy_basket(fx_m)
    out["defects"] += dfx
    fx_m["-DXY"] = basket
    for t, ccy in FX_PAIRS:
        px, _ = etf_series(t)
        em = etf_excess(px, i_us, monthly=True, cash_monthly_rate=True, name=f"etf_{t}_m")
        r = pair_stats(fx_m[ccy], em, f"{t}_{ccy}")
        r.update({"etf": t, "proxy": ccy, "role": "primary"})
        if ccy != "-DXY":
            px = validation_window(px)
            common = spots[ccy].dropna().index.intersection(px.index)
            pdx, _ = currency_excess(spots[ccy].reindex(common), rates[ccy], i_us, ccy, monthly=False,
                                     name=f"fx_{ccy}_d")
            edx = etf_excess(px.reindex(common), i_us, monthly=False, cash_monthly_rate=True, name=f"etf_{t}_d")
            r["daily_diagnostic"] = daily_diag(pdx, edx)
        out["fx"].append(r)
    # call-money fallback for the JPY / CHF carry gap, measured on 2003+ against the same ETFs (diagnostic)
    for ccy, sid in CALL_MONEY.items():
        try:
            cm, _ = rate_series(sid)
        except InputDefect as e:
            out["diagnostics"][f"{ccy}_call_money_fallback"] = {"input_defect": str(e)}
            continue
        alt, _ = currency_excess(month_end(spots[ccy]), cm, i_us, ccy, monthly=True, name=f"fx_{ccy}_m_callmoney")
        t = CCY[ccy][3]
        px, _ = etf_series(t)
        em = COMPUTED[f"etf_{t}_m"]
        r = pair_stats(alt, em, f"{t}_{ccy}_callmoney")
        out["diagnostics"][f"{ccy}_call_money_fallback_vs_{t}"] = r
        j = pd.concat([fx_m[ccy], alt], axis=1).dropna()
        out["diagnostics"][f"{ccy}_call_money_vs_3m_proxy"] = {
            "months": int(len(j)), "corr": round(float(j.iloc[:, 0].corr(j.iloc[:, 1])), 5),
            "mean_diff_pct_per_year": round(float(1200 * (j.iloc[:, 1] - j.iloc[:, 0]).mean()), 3)}
    # aggregate defects per currency and kind
    agg = {}
    for d in out["defects"]:
        k = (d["kind"], d["currency"])
        agg.setdefault(k, {}).setdefault(d["year"], 0)
        agg[k][d["year"]] += d["count"]
    out["defects"] = [{"kind": k[0], "currency": k[1], "by_year": v, "total": sum(v.values())} for k, v in agg.items()]
    assert_masked()
    out["mask_check"] = {"computed_series": len(COMPUTED),
                         "earliest_date": str(min(v.index.min() for v in COMPUTED.values() if len(v)).date())}
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "validate"
    if cmd == "fetch":
        failed = fetch_all()
        print(json.dumps({"failed": failed}, indent=1))
        return 0 if not failed else 1
    if cmd == "coverage":
        cov = run_coverage()
        json.dump(cov, open(os.path.join(CACHE, "coverage.json"), "w"), indent=1, default=str)
        print(json.dumps({"defects": cov["defects"]}, indent=1))
        return 0
    if cmd == "validate":
        cov = run_coverage()
        val = run_validation()
        res = {"written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "kind": "validation statistics of proxy constructions vs executable ETFs on the spent 2003+ period; "
                       "no trend-strategy return or Sharpe computed; 1962-2002 returns unread",
               "manifest": "research/xasset/MANIFEST.json", "coverage": cov, "validation": val}
        json.dump(res, open(OUT, "w"), indent=1, default=str)
        print(f"wrote {OUT}")
        return 0
    raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
