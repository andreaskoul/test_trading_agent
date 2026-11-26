"""Shared loaders, constructions and the pre-2003 guard for the cross-asset trend read (PREREG_XASSET.md).

THE 1962-2002 SLEEVE STAYS UNREAD UNTIL THE ONE READ.
    `PRE2003_GUARD` is the single gate every function that touches non-equity data goes through:
    * `PRE2003_GUARD.raw(x, what)` is applied by every loader of real non-equity data. Outside an authorised mode it
      keeps only dates on or after 2003-01-01, so no pre-2003 level reaches a construction. In synthetic mode it
      refuses real data altogether.
    * `PRE2003_GUARD.derived(x, what)` is applied to every return, signal, position and statistic series. It raises
      `Pre2003Error` if the series has a date before 2003-01-01, unless the read itself (or a synthetic dry run) is in
      progress, and registers the series so that tests can check the whole registry.
    * Two modes may hold pre-2003 levels: `level_check()` (callable only from `pre2003_level_counts`, the §3.2 level
      comparison, which returns counts only; `derived` still raises there) and `read()` (callable only from
      `run_read`; it creates READ_XASSET.lock with O_EXCL first and refuses if the lock exists).
    proxy.py's own mask (`validation_window`) stays in force except inside `read()`, which lifts it for the read.

Frozen inputs: MANIFEST.json (proxy cache), FREE_MANIFEST.json (free cache), XASSET_MANIFEST.json (files added for
the checks: the pysystemtrade Bund files at the same pinned commit, yfinance continuous futures from 2003-01-01, and
the French daily factors file used by research/sharpe/capital.py). Every file is checked against its sha256 before use.
"""
import contextlib
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import proxy as P                                                   # noqa: E402

VALID_START = pd.Timestamp("2003-01-01")
READ_END = pd.Timestamp("2002-12-31")
LOCK = os.path.join(HERE, "READ_XASSET.lock")
CHECKS_OUT = os.path.join(HERE, "CHECKS_XASSET.json")
XMANIFEST = os.path.join(HERE, "XASSET_MANIFEST.json")


def _main_root():
    try:
        g = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE, capture_output=True, text=True,
                           check=True).stdout.strip()
        return os.path.dirname(os.path.abspath(os.path.join(HERE, g)))
    except Exception:                                                # noqa: BLE001
        return ROOT


MAIN_ROOT = _main_root()


def _first_dir(env, cands):
    if os.environ.get(env):
        return os.environ[env]
    for c in cands:
        if os.path.isdir(c) and os.listdir(c):
            return c
    return cands[0]


FREE_CACHE = _first_dir("XASSET_FREE_CACHE", [os.path.join(ROOT, ".cache", "xasset-free"),
                                              os.path.join(MAIN_ROOT, ".claude", "worktrees", "xasset-free", ".cache",
                                                           "xasset-free")])
PROXY_CACHE = _first_dir("XASSET_PROXY_CACHE", [os.path.join(ROOT, ".cache", "xasset-proxy"),
                                                os.path.join(MAIN_ROOT, ".claude", "worktrees", "xasset-proxy",
                                                             ".cache", "xasset-proxy")])
CHECK_CACHE = os.environ.get("XASSET_CHECK_CACHE", os.path.join(ROOT, ".cache", "xasset-checks"))
P.CACHE = PROXY_CACHE


class Pre2003Error(RuntimeError):
    """A non-equity value dated before 2003-01-01 reached a computation outside the level check or the read."""


class InputDefect(Exception):
    """A source failed its content contract (CLAUDE.md rules 1-4): it is not used (counted as missing)."""


# ===================================================================================== the guard
class _Pre2003Guard:
    LEVEL_CALLERS = {"pre2003_level_counts"}
    READ_CALLERS = {"run_read"}
    COVERAGE_CALLERS = {"coverage_counts"}

    def __init__(self):
        self.mode = None
        self.registry = {}

    @staticmethod
    def _caller_names():
        f, names = sys._getframe(1), []
        while f is not None:
            names.append(f.f_code.co_name)
            f = f.f_back
        return set(names)

    @contextlib.contextmanager
    def level_check(self):
        if not (self._caller_names() & self.LEVEL_CALLERS):
            raise Pre2003Error("level-check mode may only be entered by pre2003_level_counts")
        if self.mode is not None:
            raise Pre2003Error(f"level check inside mode {self.mode!r}")
        self.mode = "level_check"
        try:
            yield
        finally:
            self.mode = None

    @contextlib.contextmanager
    def read(self, lock_path, payload):
        if not (self._caller_names() & self.READ_CALLERS):
            raise Pre2003Error("read mode may only be entered by run_read")
        if self.mode is not None:
            raise Pre2003Error(f"read inside mode {self.mode!r}")
        if os.path.exists(lock_path):
            raise Pre2003Error(f"already read: {lock_path} exists")
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)   # created first, before any data
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=1)
        keep = P.VALID_START
        self.mode = "read"
        P.VALID_START = pd.Timestamp("1900-01-01")                   # proxy.py's mask lifted for the read only
        try:
            yield
        finally:
            P.VALID_START = keep
            self.mode = None

    @contextlib.contextmanager
    def synthetic(self):
        if self.mode is not None:
            raise Pre2003Error(f"synthetic inside mode {self.mode!r}")
        keep = P.VALID_START
        self.mode = "synthetic"
        P.VALID_START = pd.Timestamp("1900-01-01")                   # synthetic dates only; real loaders refuse
        try:
            yield
        finally:
            P.VALID_START = keep
            self.mode = None

    @contextlib.contextmanager
    def coverage(self):
        """Presence-only mode: loaders return 1.0 where a value exists and NaN elsewhere, on all dates."""
        if not (self._caller_names() & self.COVERAGE_CALLERS):
            raise Pre2003Error("coverage mode may only be entered by coverage_counts")
        if self.mode is not None:
            raise Pre2003Error(f"coverage inside mode {self.mode!r}")
        self.mode = "coverage"
        try:
            yield
        finally:
            self.mode = None

    def raw(self, x, what):
        """Every loader of real non-equity data returns through here."""
        if self.mode == "synthetic":
            raise Pre2003Error(f"{what}: real data requested in a synthetic run")
        if not isinstance(x.index, pd.DatetimeIndex):
            raise TypeError(f"{what}: needs a DatetimeIndex")
        if self.mode in ("read", "level_check"):
            return x
        if self.mode == "coverage":
            return x.notna().astype(float).where(x.notna())          # presence only; no value leaves the loader
        return x.loc[x.index >= VALID_START]

    def derived(self, x, what):
        """Every return, signal, position or statistic series returns through here."""
        if not isinstance(x.index, pd.DatetimeIndex):
            raise TypeError(f"{what}: needs a DatetimeIndex")
        if self.mode in ("read", "synthetic"):
            return x
        if len(x) and x.index.min() < VALID_START:
            raise Pre2003Error(f"{what}: computed value dated {x.index.min().date()} (< {VALID_START.date()}) "
                               f"in mode {self.mode!r}")
        self.registry[what] = x
        return x

    def assert_clean(self, registry=None):
        reg = self.registry if registry is None else registry
        bad = {k: str(v.index.min().date()) for k, v in reg.items() if len(v) and v.index.min() < VALID_START}
        if bad:
            raise AssertionError(f"series dated before {VALID_START.date()}: {sorted(bad)}")
        if self.mode is None:
            P.assert_masked()


PRE2003_GUARD = _Pre2003Guard()
G = PRE2003_GUARD


# ===================================================================================== frozen files
_SHA_OK = {}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _verified(p, want, name):
    if not os.path.exists(p):
        raise InputDefect(f"{name}: frozen file missing ({p}); refusing to re-download a new vintage")
    st = os.stat(p)
    key = (p, st.st_size, st.st_mtime)
    if _SHA_OK.get(key) != want:
        if sha256(p) != want:
            raise InputDefect(f"{name}: sha256 differs from its manifest")
        _SHA_OK[key] = want
    return p


def free_path(name):
    m = json.load(open(os.path.join(HERE, "FREE_MANIFEST.json")))["files"].get(name)
    if m is None:
        raise InputDefect(f"{name}: not in FREE_MANIFEST.json")
    return _verified(os.path.join(FREE_CACHE, name), m["sha256"], name)


def xmanifest():
    return json.load(open(XMANIFEST)) if os.path.exists(XMANIFEST) else {"files": {}, "failed": {}}


def check_path(name):
    m = xmanifest()["files"].get(name)
    if m is None:
        raise InputDefect(f"{name}: not in XASSET_MANIFEST.json")
    p = m.get("path") or os.path.join(CHECK_CACHE, name)
    if not os.path.isabs(p):
        p = os.path.join(MAIN_ROOT, p)
    return _verified(p, m["sha256"], name)


def verify_all():
    """sha256 of every frozen file this programme uses (MANIFEST.json, FREE_MANIFEST.json, XASSET_MANIFEST.json)."""
    out = {"proxy": 0, "free": 0, "checks": 0, "defects": []}
    for name in P._manifest()["files"]:
        try:
            P.frozen(name)
            out["proxy"] += 1
        except Exception as e:                                       # noqa: BLE001
            out["defects"].append(str(e))
    for name in json.load(open(os.path.join(HERE, "FREE_MANIFEST.json")))["files"]:
        try:
            free_path(name)
            out["free"] += 1
        except Exception as e:                                       # noqa: BLE001
            out["defects"].append(str(e))
    for name in xmanifest()["files"]:
        try:
            check_path(name)
            out["checks"] += 1
        except Exception as e:                                       # noqa: BLE001
            out["defects"].append(str(e))
    return out


# ===================================================================================== registered universe
# §2 and §3.3. Commodities: the pysystemtrade full-size file only (minis and micros never used); excluded before any
# check: the splice (GASOILINE = RBOB with unleaded inside) and single-month (deferred) hold cycles from the shipped
# rollconfig.csv (CORN Z, WHEAT Z, CRUDE_W Z: December-only; SOYBEAN X: November-only, same defect class).
PST_COMMODITIES = ["OJ", "SOYOIL", "SUGAR11", "COTTON2", "COCOA", "OATIES", "SOYMEAL", "SILVER", "PLAT", "WHEAT",
                   "CORN", "LIVECOW", "LEANHOG", "GOLD", "FEEDCOW", "PALLAD", "CANOLA", "HEATOIL", "SOYBEAN",
                   "GASOILINE", "GASOIL", "RICE", "CRUDE_W", "SUGAR_WHITE", "COCOA_LDN", "BRENT_W", "GAS_US",
                   "WHEAT_ICE", "COPPER", "REDWHEAT", "MILK", "MILKWET", "MILLWHEAT"]
SPLICES = {"GASOILINE": "splice: RBOB file holds unleaded gasoline from 1985 (FREE_DATA.md §2 defect 2)",
           "SOFR": "splice: Eurodollar inside SOFR (not a commodity; listed for the record)"}
# second source on 2003+ (§3.1): yfinance continuous futures where Yahoo lists the same contract
YF = {"OJ": "OJ=F", "SOYOIL": "ZL=F", "SUGAR11": "SB=F", "COTTON2": "CT=F", "COCOA": "CC=F", "OATIES": "ZO=F",
      "SOYMEAL": "ZM=F", "SILVER": "SI=F", "PLAT": "PL=F", "LIVECOW": "LE=F", "LEANHOG": "HE=F", "GOLD": "GC=F",
      "FEEDCOW": "GF=F", "PALLAD": "PA=F", "HEATOIL": "HO=F", "RICE": "ZR=F", "BRENT_W": "BZ=F", "GAS_US": "NG=F",
      "COPPER": "HG=F", "REDWHEAT": "KE=F", "MILK": "DC=F"}
# CHRIS-style mirror (front month, unadjusted), same contract (FREE_DATA.md; free_coverage.CHRIS_TO_PST)
CHRIS = {"SOYOIL": "ZL", "SUGAR11": "SB", "COTTON2": "CT", "COCOA": "CC", "OATIES": "ZO", "SOYMEAL": "ZM",
         "SILVER": "SI", "PLAT": "PL", "LIVECOW": "LE", "LEANHOG": "HE", "GOLD": "GC", "FEEDCOW": "FC",
         "PALLAD": "PA", "HEATOIL": "HO", "RICE": "ZR", "GAS_US": "NG", "COPPER": "HG", "OJ": "OJ"}
BOND_FUTURES = {"UK": "GILT", "DE": "BUND", "JP": "JGB", "CA": "CAD10", "CH": "CH10"}
US_TSY = {"US5": "DGS5", "US10": "DGS10"}
FX_H10 = ["GBP", "AUD", "CAD", "JPY", "CHF", "NOK", "SEK", "DKK"]          # + DEM from BIS
CLASSES = ("bonds", "currencies", "commodities")


def pst_cfg():
    r = pd.read_csv(free_path("pst_rollconfig.csv")).set_index("Instrument")
    i = pd.read_csv(free_path("pst_instrumentconfig.csv")).set_index("Instrument")
    return r, i


def bund_path(kind):
    return check_path(f"pst_{kind}_BUND.csv")


# ===================================================================================== loaders (real data; guarded)
def _contract_dates(dt, what):
    if dt.isna().any():
        raise InputDefect(f"{what}: unparseable dates")
    if dt.duplicated().any():
        raise InputDefect(f"{what}: duplicate dates")
    if not dt.is_monotonic_increasing:
        raise InputDefect(f"{what}: dates not increasing")


LOADER_NOTES = {}


def _last_stamp_per_date(d, what):
    """pysystemtrade DATETIME stamps must strictly increase; where a calendar date carries several stamps (intraday
    rows), the date's last stamp is its observation (implementation choice). Returns (frame by date, rows collapsed)."""
    ts = pd.to_datetime(d.DATETIME, errors="coerce")
    if ts.isna().any():
        raise InputDefect(f"{what}: unparseable timestamps")
    if not ts.is_monotonic_increasing or ts.duplicated().any():
        raise InputDefect(f"{what}: timestamps not strictly increasing")
    day = ts.dt.normalize()
    keep = ~day.duplicated(keep="last")
    out = d[keep.values].copy()
    out.index = pd.DatetimeIndex(day[keep].values)
    return out.drop(columns=["DATETIME"]), int((~keep).sum())


def pst_frame(market):
    """Multiple prices (held PRICE, CARRY, FORWARD with their contract labels) and the back-adjusted price, by date."""
    mp = bund_path("multiple") if market == "BUND" else free_path(f"pst_multiple_{market}.csv")
    ap = bund_path("adjusted") if market == "BUND" else free_path(f"pst_adjusted_{market}.csv")
    m = pd.read_csv(mp)
    need = ["DATETIME", "PRICE", "PRICE_CONTRACT", "CARRY", "CARRY_CONTRACT", "FORWARD", "FORWARD_CONTRACT"]
    if list(m.columns) != ["DATETIME", "CARRY", "CARRY_CONTRACT", "PRICE", "PRICE_CONTRACT", "FORWARD",
                           "FORWARD_CONTRACT"]:
        raise InputDefect(f"{market}: multiple-prices columns {list(m.columns)}")
    a = pd.read_csv(ap)
    if list(a.columns) != ["DATETIME", "price"]:
        raise InputDefect(f"{market}: adjusted columns {list(a.columns)}")
    m, nm = _last_stamp_per_date(m, f"{market} multiple")
    a, na = _last_stamp_per_date(a, f"{market} adjusted")
    LOADER_NOTES[f"pst {market}"] = {"intraday_rows_collapsed_multiple": nm, "intraday_rows_collapsed_adjusted": na}
    m = m[need[1:]]
    m["ADJ"] = a.price.reindex(m.index)
    bad = int(((m.PRICE <= 0) & m.PRICE.notna()).sum())
    if bad:
        raise InputDefect(f"{market}: {bad} non-positive held prices")
    return G.raw(m, f"pst {market}")


def chris_settle(sym):
    d = pd.read_csv(free_path(f"chris_{sym}.csv"))
    if "Settle" not in d.columns or "Date" not in d.columns:
        raise InputDefect(f"chris {sym}: no typed Settle/Date column")
    dt = pd.to_datetime(d.Date, format="%Y-%m-%d", errors="coerce")
    s = pd.Series(pd.to_numeric(d.Settle, errors="coerce").values, index=pd.DatetimeIndex(dt)).sort_index()
    _contract_dates(pd.Series(s.index), f"chris {sym}")
    s = s[s > 0]
    return G.raw(s, f"chris {sym}")


def yf_close(t):
    p = check_path(f"yf_{t}.csv")
    d = pd.read_csv(p, parse_dates=["Date"]).set_index("Date")
    if "Close" not in d.columns:
        raise InputDefect(f"{t}: no Close column")
    s = d["Close"].astype(float)
    _contract_dates(pd.Series(s.index), t)
    s = s[s > 0]
    return G.raw(s, f"yf {t}")


# Plausible-range contracts (all dates; pass/fail only): short rates use proxy.rate_series' range [-2 %, 60 %];
# yields [-2 %, 25 %]. A violation is an input defect: the source is not used.
RATE_RANGE = (-0.02, 0.60)
YIELD_RANGE = (-0.02, 0.25)


def _range(s, rng, what):
    x = s.dropna()
    n = int(((x < rng[0]) | (x > rng[1])).sum())
    if n:
        raise InputDefect(f"{what}: {n} values outside the plausible range [{rng[0]:.0%}, {rng[1]:.0%}]")
    return s


def _monthly_first(dates_yyyymm, vals, what):
    idx = pd.to_datetime(pd.Series(dates_yyyymm), format="%Y-%m", errors="coerce")
    _contract_dates(idx, what)
    return pd.Series(np.asarray(vals, float), index=pd.DatetimeIndex(idx))


def boj_call():
    """BoJ collateralised overnight call rate, end of month (typed in the series name), decimals, by first-of-month."""
    rows = list(csv.reader(open(free_path("boj_FM02_STRECLCOON.csv"), encoding="utf-8", errors="replace")))
    h = next(i for i, r in enumerate(rows) if r and r[0] == "SERIES_CODE")
    ix = {k: rows[h].index(k) for k in ("NAME_OF_TIME_SERIES", "UNIT", "FREQUENCY", "SURVEY_DATES", "VALUES")}
    body = [r for r in rows[h + 1:] if len(r) > ix["VALUES"]]
    name, unit, freq = body[0][ix["NAME_OF_TIME_SERIES"]], body[0][ix["UNIT"]], body[0][ix["FREQUENCY"]]
    if "End of Month" not in name or unit != "percent per annum" or freq != "MONTHLY":
        raise InputDefect(f"BoJ call rate: typed fields {name!r} {unit!r} {freq!r}")
    d = [r[ix["SURVEY_DATES"]] for r in body]
    v = [float(r[ix["VALUES"]]) if r[ix["VALUES"]].strip() not in ("", "NA", "null") else np.nan for r in body]
    s = _monthly_first([f"{x[:4]}-{x[4:6]}" for x in d], v, "BoJ call") / 100.0
    _range(s, RATE_RANGE, "BoJ call rate")
    return G.raw(s.dropna(), "boj call")


def snb_series(cube, key, what, rng):
    d = pd.read_csv(free_path(f"snb_{cube}.csv"), sep=";", skiprows=3)
    if list(d.columns) != ["Date", "D0", "Value"]:
        raise InputDefect(f"SNB {cube}: columns {list(d.columns)}")
    g = d[d.D0 == key]
    s = _monthly_first(g.Date.values, pd.to_numeric(g.Value, errors="coerce").values, what) / 100.0
    _range(s, rng, f"SNB {cube} {key}")
    return s.dropna()


def snb_call():
    """SNB call money (tomorrow-next, D0 1TGT), monthly, by first-of-month."""
    return G.raw(snb_series("zimoma", "1TGT", "SNB call money", RATE_RANGE), "snb call")


def _to_month_end(s):
    return pd.Series(s.values, index=(s.index + pd.offsets.MonthEnd(0)).normalize())


def snb_yield10():
    return G.raw(_to_month_end(snb_series("rendoblim", "10J", "SNB 10y", YIELD_RANGE)), "snb 10y")


def bbk_yield10():
    lines = open(free_path("bbk_svensson_M_R10XX.csv"), encoding="utf-8-sig").read().splitlines()
    title = lines[1]
    if "residual maturity of 10.0 years" not in title or "monthly data" not in title:
        raise InputDefect(f"Bundesbank: title {title[:120]!r}")
    if "BBK_UNIT_ENG,percent" not in lines[2]:
        raise InputDefect("Bundesbank: unit is not percent")
    body = [l.split(",") for l in lines if len(l) >= 7 and l[:4].isdigit() and l[4] == "-"]
    s = _monthly_first([b[0] for b in body], [float(b[1]) if b[1] not in ("", ".") else np.nan for b in body],
                       "Bundesbank 10y") / 100.0
    _range(s, YIELD_RANGE, "Bundesbank 10y")
    return G.raw(_to_month_end(s.dropna()), "bbk 10y")


def boe_yield10():
    import openpyxl                                                    # noqa: F401  (typed failure if absent)
    z = zipfile.ZipFile(free_path("boe_glcnominalmonthedata.zip"))
    parts = []
    for n in sorted(z.namelist()):
        x = pd.ExcelFile(io.BytesIO(z.read(n)))
        if "4. spot curve" not in x.sheet_names:
            raise InputDefect(f"BoE {n}: no spot-curve sheet")
        d = x.parse("4. spot curve", header=None)
        if "spot curve" not in str(d.iloc[0, 1]).lower():
            raise InputDefect(f"BoE {n}: sheet title {d.iloc[0, 1]!r}")
        hr = next(i for i in range(10) if str(d.iloc[i, 0]).strip().lower().startswith("years"))
        mats = list(d.iloc[hr, :])
        j = [k for k, v in enumerate(mats) if isinstance(v, (int, float)) and v == 10.0]
        if len(j) != 1:
            raise InputDefect(f"BoE {n}: no unique 10-year column")
        dates = pd.to_datetime(d.iloc[:, 0], errors="coerce", format="mixed")
        b = d[dates.notna()]
        parts.append(pd.Series(pd.to_numeric(b.iloc[:, j[0]], errors="coerce").values,
                               index=pd.DatetimeIndex(dates[dates.notna()]).normalize()))
    s = pd.concat(parts).sort_index()
    _contract_dates(pd.Series(s.index), "BoE 10y")
    if not ((s.index + pd.offsets.MonthEnd(0)) - s.index).days.max() <= 3:
        raise InputDefect("BoE: dates are not month ends")
    s = _to_month_end(s.dropna() / 100.0)
    _range(s, YIELD_RANGE, "BoE 10y")
    return G.raw(s, "boe 10y")


def mof_yield10_daily():
    p = free_path("mof_jgbcme_all.csv")
    if not open(p, encoding="utf-8", errors="replace").readline().startswith("Interest Rate"):
        raise InputDefect("MoF: first line is not the 'Interest Rate' title")
    d = pd.read_csv(p, skiprows=1, na_values="-")
    if "10Y" not in d.columns or d.columns[0] != "Date":
        raise InputDefect("MoF: no Date / 10Y column")
    dt = pd.to_datetime(d.Date, format="%Y/%m/%d", errors="coerce")
    _contract_dates(dt, "MoF")
    s = pd.Series(pd.to_numeric(d["10Y"], errors="coerce").values, index=pd.DatetimeIndex(dt)).dropna() / 100.0
    _range(s, YIELD_RANGE, "MoF 10y")
    return G.raw(s, "mof 10y")


def statcan(vector, what, rng):
    z = zipfile.ZipFile(free_path("statcan_10100122-eng.zip"))
    d = pd.read_csv(z.open("10100122.csv"), usecols=["REF_DATE", "Rates", "UOM", "SCALAR_FACTOR", "VECTOR",
                                                     "VALUE"], low_memory=False)
    g = d[(d.VECTOR == vector) & d.VALUE.notna()]
    if not (g.UOM == "Percent").all() or not (g.SCALAR_FACTOR == "units").all():
        raise InputDefect(f"StatCan {vector}: units")
    s = _monthly_first(g.REF_DATE.values, g.VALUE.values, what) / 100.0
    _range(s, rng, f"StatCan {vector}")
    return s


def statcan_10y():
    return G.raw(_to_month_end(statcan("v122543", "StatCan 10y", YIELD_RANGE)), "statcan 10y")


def statcan_tbill():
    return G.raw(statcan("v122531", "StatCan 3m", RATE_RANGE), "statcan 3m")


def bis_dem_daily():
    """USD per Deutsche mark in euro units (BIS WS_XRU, Germany, daily): 1 / (EUR per USD)."""
    z = zipfile.ZipFile(free_path("bis_WS_XRU_csv_flat.zip"))
    d = pd.read_csv(z.open(z.namelist()[0]), low_memory=False)
    g = d[d["REF_AREA:Reference area"].str.startswith("DE:") & d["FREQ:Frequency"].str.startswith("D:")]
    if not (g["STRUCTURE_ID"].str.contains("US dollar exchange rates")).all() or \
            not (g["CURRENCY:Currency"] == "EUR: Euro").all() or not (g["UNIT_MULT:Unit Multiplier"] == "0: Units").all():
        raise InputDefect("BIS DE: typed fields (US dollar exchange rates, EUR units, unit multiplier 0)")
    g = g[g["OBS_VALUE:Observation Value"].notna()]
    dt = pd.to_datetime(g["TIME_PERIOD:Time period or range"], format="%Y-%m-%d", errors="coerce")
    s = pd.Series(g["OBS_VALUE:Observation Value"].astype(float).values, index=pd.DatetimeIndex(dt)).sort_index()
    _contract_dates(pd.Series(s.index), "BIS DE")
    if ((s < 0.3) | (s > 3.0)).any():
        raise InputDefect("BIS DE: EUR per USD outside [0.3, 3]")
    return G.raw(1.0 / s, "bis dem")


def fred_rate(sid):
    s, _ = P.rate_series(sid)
    return G.raw(s, f"fred {sid}")


def h10_spot(ccy):
    s, _ = P.spot_series(ccy)
    return G.raw(s, f"h10 {ccy}")


def tsy_yield(sid):
    y, c = P.treasury_series(sid)
    return G.raw(y, f"fred {sid}"), c["maturity_years"]


def tbill():
    s, _ = P.tbill_series()
    return G.raw(s, "fred DTB3")


# ===================================================================================== constructions (guarded)
def pst_excess_daily(market, frame=None):
    """Excess return of the held contract: change in the back-adjusted price over the held contract's price."""
    f = pst_frame(market) if frame is None else frame
    f = f[f.ADJ.notna() & f.PRICE.notna()]
    r = f.ADJ.diff() / f.PRICE.shift(1)
    return G.derived(r.iloc[1:].dropna(), f"pst_d_{market}")


def compound_monthly(r, what):
    """Compound daily returns within calendar months, labelled by the month end."""
    lr = np.log1p(r)
    m = lr.groupby(r.index.to_period("M")).sum()
    out = pd.Series(np.expm1(m.values), index=m.index.to_timestamp(how="end").normalize())
    return G.derived(out, what)


SHORT_RATE = {"UK": ("fred", "IR3TIB01GBM156N"), "DE": ("fred", "IR3TIB01DEM156N"), "JP": ("boj", None),
              "CA": ("statcan", None), "CH": ("snb", None)}


def short_rate(country):
    k, sid = SHORT_RATE[country]
    if k == "fred":
        return fred_rate(sid)
    return {"boj": boj_call, "statcan": statcan_tbill, "snb": snb_call}[k]()


def yield10(country):
    if country == "UK":
        return boe_yield10()
    if country == "DE":
        return bbk_yield10()
    if country == "JP":
        return P.month_end(mof_yield10_daily())
    if country == "CA":
        return statcan_10y()
    if country == "CH":
        return snb_yield10()
    raise KeyError(country)


def intl_bond_monthly(country):
    """Par-bond excess return on month-end 10-year yields, local short rate as financing (local excess return)."""
    y = yield10(country)
    rf = short_rate(country)
    r = P.treasury_excess(y, rf, 10, monthly=True, name=f"bond_{country}_m")
    return G.derived(r, f"bond_{country}_m")


def us_tsy(key, monthly):
    y, n = tsy_yield(US_TSY[key])
    rf = tbill()
    yy = P.month_end(y) if monthly else y
    r = P.treasury_excess(yy, rf, n, monthly=monthly, name=f"tsy_{key}_{'m' if monthly else 'd'}")
    return G.derived(r, f"tsy_{key}_{'m' if monthly else 'd'}")


def fx_rate_for(ccy):
    """Foreign short rate of the registered construction: OECD 3m (validated six), BoJ call (JPY), SNB call (CHF),
    OECD 3m Germany (DEM)."""
    if ccy == "JPY":
        return boj_call()
    if ccy == "CHF":
        return snb_call()
    if ccy == "DEM":
        return fred_rate("IR3TIB01DEM156N")
    return fred_rate(P.CCY[ccy][2])


def fx_spot(ccy):
    return bis_dem_daily() if ccy == "DEM" else h10_spot(ccy)


def fx_excess(ccy, monthly):
    s = fx_spot(ccy)
    i_f, i_us = fx_rate_for(ccy), fred_rate(P.US_RATE_ID)
    r, defects = P.currency_excess(P.month_end(s) if monthly else s, i_f, i_us, ccy, monthly=monthly,
                                   name=f"fx_{ccy}_{'m' if monthly else 'd'}")
    return G.derived(r, f"fx_{ccy}_{'m' if monthly else 'd'}"), defects


def bond_future_monthly(country):
    return compound_monthly(pst_excess_daily(BOND_FUTURES[country]), f"fut_{country}_m")


# ===================================================================================== the core (equity; spent)
def french_path():
    m = xmanifest()["files"].get("F-F_Research_Data_Factors_daily.csv")
    if m is None:
        raise InputDefect("French daily factors file not in XASSET_MANIFEST.json")
    return check_path("F-F_Research_Data_Factors_daily.csv")


def core_reproduce():
    """research/sharpe/capital.py sample (a), arm M under R: daily returns, rf, exposure; checked against
    RESULT_CAPITAL.json to 1e-6 (the core is a spent equity sample; reading it is allowed)."""
    sys.path.insert(0, os.path.join(ROOT, "research", "sharpe"))
    import capital as CAP                                             # noqa: E402
    CAP.FF = french_path()
    res, (r, rf, e, out) = CAP.item1_long()
    ref = json.load(open(os.path.join(ROOT, "research", "sharpe", "RESULT_CAPITAL.json")))["item1_a_1927_2026"]
    diffs = {}
    for arm in ("M_R", "E1_R", "E2_R", "M_S"):
        for k, v in ref[arm].items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and k != "tracking_vs_M":
                diffs[f"{arm}.{k}"] = abs(float(res[arm][k]) - float(v))
    diffs["period"] = 0.0 if res["period"] == ref["period"] else 1.0
    diffs["share_days_at_1.3"] = abs(res["share_days_at_1.3"] - ref["share_days_at_1.3"])
    worst = max(diffs.values())
    check = {"compared_fields": len(diffs), "max_abs_diff": worst, "match_1e-6": bool(worst <= 1e-6),
             "period": res["period"], "M_R_excess_sharpe": res["M_R"]["excess_sharpe"]}
    return check, r, rf, e, out[("M", "R")]


def core_monthly(r_mkt, rf, e, m_daily, start="1962-01-01", end="2002-12-31"):
    """Monthly excess return of arm M under R (compounded arm return minus compounded T-bill, per calendar month);
    exposure at the first session of each month; ex-ante market volatility (EWMA com 60 of daily returns, x261) at
    each month end."""
    sel = (m_daily.index >= start) & (m_daily.index <= end)
    md, rfd, ed, rm = m_daily[sel], rf[sel], e[sel], r_mkt[sel]
    per = md.index.to_period("M")
    gm = np.expm1(np.log1p(md).groupby(per).sum())
    gf = np.expm1(np.log1p(rfd).groupby(per).sum())
    me = gm.index.to_timestamp(how="end").normalize()
    ex = pd.Series((gm - gf).values, index=me)
    e_first = pd.Series(ed.groupby(per).first().values, index=me)
    sig_all = np.sqrt(r_mkt.ewm(com=60).var() * 261)
    sig = sig_all.groupby(r_mkt.index.to_period("M")).last()
    sig = pd.Series(sig.values, index=sig.index.to_timestamp(how="end").normalize())
    return ex, e_first, sig


# ===================================================================================== git helpers
def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def committed_clean(paths):
    """(all tracked and unchanged against HEAD, last commit hash touching them)."""
    rel = [os.path.relpath(p, ROOT) for p in paths]
    for r in rel:
        if git("ls-files", "--error-unmatch", r).returncode != 0:
            return False, None
    if git("diff", "--quiet", "HEAD", "--", *rel).returncode != 0:
        return False, None
    h = git("log", "-1", "--format=%H", "--", *rel).stdout.strip()
    return True, h or None
