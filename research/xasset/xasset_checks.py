"""§3 gate of PREREG_XASSET.md: checks before the read, on spent 2003+ data and pre-2003 levels only.

    python -I research/xasset/xasset_checks.py fetch   # freeze the files the checks add (XASSET_MANIFEST.json)
    python -I research/xasset/xasset_checks.py run     # -> research/xasset/CHECKS_XASSET.json; exit 0 pass,
                                                       #    1 fail (evaluated, not passed), 2 cannot be evaluated

What is computed, and on which dates (every non-equity series goes through xasset_lib.PRE2003_GUARD):
* §3.1 validation statistics (correlation, tracking error, bias, 12-month sign agreement, switch difference; the
  VALIDATE.md thresholds in proxy.THRESHOLDS) on 2003-01 or later only:
  - JPY (BoJ call rate) vs FXY, CHF (SNB call money) vs FXF, DEM (BIS spot, OECD German 3m) vs the euro proxy;
  - UK, DE, JP, CA, CH 10-year par-bond proxies vs the same-country pysystemtrade bond futures;
  - pysystemtrade commodity excess returns vs yfinance continuous futures (front contract, roll days excluded);
  - the already-validated US 5y/10y and GBP/AUD/CAD constructions, re-run through proxy.py and compared with
    VALIDATE.json.
* §3.2 pre-2003 LEVEL checks: per market and decade, the count of sessions where the pysystemtrade settlement of the
  contract the CHRIS-style mirror holds agrees with the mirror within 0.5 %. Counts only (`pre2003_level_counts`, the
  one caller the guard admits to pre-2003 levels).
* §3.3 splice / variant exclusions; §3.4 content contracts and coverage (presence counts on all dates).
A market that fails is dropped and the drop recorded; nothing is re-scoped.
"""
import json
import math
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xasset_lib as L                                              # noqa: E402
from xasset_lib import G, P                                         # noqa: E402

LEVEL_TOL = 0.005               # §3.2: settlement prices agree within 0.5 %
LEVEL_MIN_SHARE = 0.95          # §3.2: fewer than 95 % agreeing -> dropped
ROLL_WINDOW_DAYS = 5            # implementation choice: sessions within +-5 calendar days of an inferred expiry excluded
COVERAGE_MIN_SHARE = 0.95       # implementation choice: month-end coverage contract over the expected calendar


# ===================================================================================== fetch (files added for the checks)
def _record(name, src, p, extra=None):
    m = L.xmanifest()
    m["files"][name] = {"source": src, "bytes": os.path.getsize(p), "sha256": L.sha256(p),
                        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "path": os.path.relpath(p, L.MAIN_ROOT), **(extra or {})}
    m["note"] = ("Frozen at first fetch (CLAUDE.md rule 4); raw files under .cache, not committed. yfinance files start "
                 "2003-01-01, so they hold no pre-2003 value.")
    json.dump(m, open(L.XMANIFEST, "w"), indent=1, sort_keys=True)


def fetch():
    os.makedirs(L.CHECK_CACHE, exist_ok=True)
    man = L.xmanifest()
    failed = {}
    pst = "https://raw.githubusercontent.com/robcarver17/pysystemtrade/bbf5cf823e16be1cca27493a94099eb8cf33f6e7/data/futures/"
    jobs = [("pst_multiple_BUND.csv", pst + "multiple_prices_csv/BUND.csv"),
            ("pst_adjusted_BUND.csv", pst + "adjusted_prices_csv/BUND.csv")]
    for name, url in jobs:
        if name in man["files"]:
            L.check_path(name)
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-client/1.0"})
            with urllib.request.urlopen(req, timeout=120) as f:
                b = f.read()
            p = os.path.join(L.CHECK_CACHE, name)
            open(p, "wb").write(b)
            _record(name, url, p)
        except Exception as e:                                       # noqa: BLE001
            failed[name] = repr(e)[:200]
    import yfinance as yf
    for m, t in L.YF.items():
        name = f"yf_{t}.csv"
        if name in L.xmanifest()["files"]:
            L.check_path(name)
            continue
        try:
            h = yf.Ticker(t).history(start="2003-01-01", end="2026-11-25", auto_adjust=False)
            if h is None or h.empty:
                raise RuntimeError("no rows")
            h.index = pd.DatetimeIndex(h.index).tz_localize(None).normalize()
            h = h[h.index >= L.VALID_START]
            p = os.path.join(L.CHECK_CACHE, name)
            h[["Close", "Volume"]].to_csv(p, index_label="Date")
            _record(name, f"yfinance {yf.__version__} Ticker('{t}').history(start='2003-01-01', end='2026-11-25', "
                          "auto_adjust=False)", p, {"rows": int(len(h)), "first": str(h.index.min().date()),
                                                    "last": str(h.index.max().date())})
        except Exception as e:                                       # noqa: BLE001
            failed[name] = repr(e)[:200]
    name = "F-F_Research_Data_Factors_daily.csv"
    if name not in L.xmanifest()["files"]:
        src = os.path.join(L.MAIN_ROOT, ".claude", "worktrees", "sharpe-cap", ".cache", "exposure", name)
        p = os.path.join(L.CHECK_CACHE, name)
        shutil.copyfile(src, p)
        _record(name, f"copy of {os.path.relpath(src, L.MAIN_ROOT)} (the file research/sharpe/capital.py read)", p)
    m = L.xmanifest()
    m["failed"] = failed
    json.dump(m, open(L.XMANIFEST, "w"), indent=1, sort_keys=True)
    print(json.dumps({"frozen": len(m["files"]), "failed": failed}, indent=1))
    return 0


# ===================================================================================== §3.3 exclusions (before any check)
def exclusions():
    roll, _ = L.pst_cfg()
    out, keep = {}, []
    for m in L.PST_COMMODITIES:
        if m in L.SPLICES:
            out[m] = L.SPLICES[m]
        elif len(str(roll.loc[m, "HoldRollCycle"])) == 1:
            out[m] = (f"single-month hold cycle {roll.loc[m, 'HoldRollCycle']!r} in the shipped rollconfig.csv "
                      "(December-only rule; deferred contract, not MOP's front)")
        else:
            keep.append(m)
    out["minis_and_micros"] = ("never used: each market's history is its full-size file only "
                               "(variants listed in free_coverage.PST_MARKETS)")
    out["US rate futures, STIRs, pysystemtrade FX futures"] = ("not in the registered universe: the US curve and the "
                                                               "currencies are the proxy legs (one leg, never two)")
    return out, keep


# ===================================================================================== §3.1 helpers
def _pair(proxy_m, inst_m, label):
    j = pd.concat([proxy_m.rename("p"), inst_m.rename("e")], axis=1).dropna()
    if len(j) < 37:
        return {"evaluated": False, "reason": f"only {len(j)} common months on 2003+", "months": int(len(j)),
                "validates": False}
    try:
        r = P.pair_stats(proxy_m, inst_m, label)
    except (TypeError, ValueError, ZeroDivisionError) as e:      # e.g. no 12-month run of consecutive common months
        return {"evaluated": False, "months": int(len(j)), "validates": False,
                "reason": f"statistics not computable on 2003+ ({type(e).__name__}: too few consecutive months)"}
    r["evaluated"] = True
    if not np.isfinite(r["signal_agreement"]) or r["signal_months"] < 12:
        r["evaluated"], r["validates"] = False, False
        r["reason"] = f"only {r['signal_months']} months with a 12-month signal on both"
    return r


def _reasons(r):
    if not r.get("evaluated", True):
        return r["reason"]
    return "failed: " + ", ".join(k for k, v in r["checks"].items() if not v)


def contract_of_level(f, s, tol=LEVEL_TOL):
    """2003+ only: which pysystemtrade contract (PRICE / CARRY / FORWARD, typed labels) a second-source level is, by
    the nearest settlement within `tol`; None where none is within `tol`."""
    G.derived(f, "contract_id_input")
    cols = [("PRICE", "PRICE_CONTRACT"), ("CARRY", "CARRY_CONTRACT"), ("FORWARD", "FORWARD_CONTRACT")]
    gaps = np.column_stack([np.abs(s.values / f[c].values - 1) for c, _ in cols])
    gaps = np.where(np.isfinite(gaps), gaps, np.inf)
    k = gaps.argmin(1)
    lab = np.column_stack([f[lc].values for _, lc in cols])[np.arange(len(f)), k]
    ok = gaps.min(1) <= tol
    return pd.Series(np.where(ok, lab, np.nan), index=f.index)


def commodity_pair(market, ticker):
    f = L.pst_frame(market)
    s = L.yf_close(ticker)
    common = f.index.intersection(s.index)
    f, s = f.loc[common], s.loc[common]
    f = f[f.PRICE.notna() & f.ADJ.notna()]
    s = s.loc[f.index]
    cid = contract_of_level(f, s)
    same = cid.notna() & (cid == cid.shift(1))                       # no roll between the two common sessions
    r_src = (s / s.shift(1) - 1)[same]
    r_pst = (f.ADJ.diff() / f.PRICE.shift(1))[same]
    G.derived(r_src, f"yf_d_{market}")
    G.derived(r_pst, f"pst_dcommon_{market}")
    pm = L.compound_monthly(r_pst, f"pst_m_{market}")
    sm = L.compound_monthly(r_src, f"yf_m_{market}")
    r = _pair(pm, sm, f"com_{market}")
    r["second_source"] = f"yfinance {ticker} (front contract, roll days excluded)"
    r["common_sessions"] = int(len(common))
    r["sessions_contract_identified"] = int(cid.notna().sum())
    r["sessions_used_no_roll"] = int(same.sum())
    return r


# ===================================================================================== §3.2 level counts (pre-2003)
def _front_calendar(market, dates):
    """Contract the CHRIS-style mirror holds at each date (Quandl CHRIS #1 convention: the nearest contract of the
    priced roll cycle not yet expired), from typed rollconfig fields; and whether the date is a roll day (within
    ROLL_WINDOW_DAYS calendar days of an inferred expiry)."""
    roll, _ = L.pst_cfg()
    cyc, off = str(roll.loc[market, "PricedRollCycle"]), int(roll.loc[market, "ExpiryOffset"])
    code = {c: i + 1 for i, c in enumerate("FGHJKMNQUVXZ")}
    months = sorted(code[c] for c in cyc)
    exp = []
    for y in range(dates.min().year - 1, dates.max().year + 3):
        for mo in months:
            exp.append((pd.Timestamp(y, mo, 1) + pd.Timedelta(days=off), y * 10000 + mo * 100))
    exp.sort()
    ex_d = pd.DatetimeIndex([e[0] for e in exp])
    ex_l = np.array([e[1] for e in exp])
    pos = ex_d.searchsorted(dates, side="left")                        # first expiry on or after the date
    label = ex_l[pos]
    dist = np.minimum(np.abs((dates - ex_d[np.clip(pos, 0, len(ex_d) - 1)]).days),
                      np.abs((dates - ex_d[np.clip(pos - 1, 0, len(ex_d) - 1)]).days))
    return label, dist <= ROLL_WINDOW_DAYS


def pre2003_level_counts(markets):
    """§3.2: per market and decade, sessions where the mirror and pysystemtrade hold the same contract (by the
    calendar above, roll days excluded) and the count of those whose settlements agree within 0.5 %. Counts only:
    nothing dated is returned, saved or printed. 2003-2019 counts are given alongside as a spent diagnostic."""
    out = {}
    with G.level_check():
        for m in markets:
            sym = L.CHRIS.get(m)
            if sym is None:
                out[m] = {"applicable": False, "reason": "no CHRIS-style mirror file for this market"}
                continue
            try:
                f = L.pst_frame(m)
                c = L.chris_settle(sym)
            except L.InputDefect as e:
                out[m] = {"applicable": False, "input_defect": str(e)}
                continue
            j = f.join(c.rename("CH"), how="inner")
            label, rollday = _front_calendar(m, j.index)
            cols = [("PRICE", "PRICE_CONTRACT"), ("CARRY", "CARRY_CONTRACT"), ("FORWARD", "FORWARD_CONTRACT")]
            px = np.full(len(j), np.nan)
            for c_, lc in cols:
                hit = (j[lc].values == label) & np.isnan(px)
                px = np.where(hit, j[c_].values, px)
            same = ~np.isnan(px) & ~rollday & np.isfinite(j.CH.values)
            agree = same & (np.abs(j.CH.values / np.where(same, px, 1.0) - 1) <= LEVEL_TOL)
            dec = (j.index.year // 10) * 10
            pre = j.index < L.VALID_START
            res = {"applicable": True, "mirror": sym, "by_decade_pre2003": {}, "spent_2003_2019": {}}
            for d in sorted(set(dec[pre])):
                k = pre & (dec == d)
                res["by_decade_pre2003"][f"{d}s"] = {"common_sessions": int(k.sum()),
                                                     "same_contract_sessions": int((k & same).sum()),
                                                     "agree_within_0.5pct": int((k & agree).sum())}
            n_same, n_agree = int((pre & same).sum()), int((pre & agree).sum())
            post = ~pre
            res["spent_2003_2019"] = {"same_contract_sessions": int((post & same).sum()),
                                      "agree_within_0.5pct": int((post & agree).sum())}
            res["pre2003_same_contract_sessions"] = n_same
            res["pre2003_agree"] = n_agree
            res["pre2003_share_agree"] = round(n_agree / n_same, 4) if n_same else None
            if n_same == 0:
                res["applicable"] = False
                res["reason"] = "no pre-2003 session on which both hold the same contract"
            else:
                res["passes"] = bool(n_agree / n_same >= LEVEL_MIN_SHARE)
            del f, c, j, px, same, agree
            out[m] = res
    return out


# ===================================================================================== §3.4 coverage (presence only)
def _me_presence(x):
    """Month-end presence (1/NaN series or frame) -> PeriodIndex of months with a valid month-end observation."""
    s = x if isinstance(x, pd.Series) else x.notna().all(axis=1).astype(float).where(x.notna().all(axis=1))
    me = P.month_end(s)
    return pd.PeriodIndex(me.index.to_period("M"))


def _rate_months(r):
    x = r.dropna()
    return pd.PeriodIndex(x.index.to_period("M"))


def coverage_counts(markets):
    """Presence counts on all dates (no value is loaded: the guard returns 1/NaN). For each market: the months with
    every level input present, from the first such month to 2002-12, against the expected calendar."""
    out = {}
    with G.coverage():
        for name, (cls, kind) in markets.items():
            try:
                if cls == "commodities":
                    f = L.pst_frame(name)
                    have = _me_presence(f[["PRICE", "ADJ"]])
                elif name in L.US_TSY:
                    y, _ = L.tsy_yield(L.US_TSY[name])
                    have = _me_presence(y).intersection(_me_presence(L.tbill()))
                elif cls == "bonds":
                    c = name.split("_")[1]
                    have = _me_presence(L.yield10(c)).intersection(_rate_months(L.short_rate(c)))
                else:
                    sp = _me_presence(L.fx_spot(name))
                    # the rate of month m accrues over month m+1: a month counts if both rates exist for m-1
                    rates = _rate_months(L.fx_rate_for(name)).intersection(_rate_months(L.fred_rate(P.US_RATE_ID)))
                    have = sp.intersection(rates + 1)
            except L.InputDefect as e:
                out[name] = {"input_defect": str(e)}
                continue
            have = pd.PeriodIndex(sorted(set(have)), freq="M")
            pre = have[have <= pd.Period("2002-12", "M")]
            res = {"first_month_all_inputs": str(have.min()) if len(have) else None}
            if len(pre):
                exp = pd.period_range(pre.min(), "2002-12", freq="M")
                miss = sorted(set(exp) - set(pre))
                res.update({"expected_months_to_2002_12": int(len(exp)), "months_present": int(len(pre)),
                            "share": round(len(pre) / len(exp), 4), "missing_spans": P._spans(miss)[:20],
                            "passes": bool(len(pre) / len(exp) >= COVERAGE_MIN_SHARE)})
            else:
                res.update({"expected_months_to_2002_12": 0, "passes": None,
                            "note": "no pre-2003 month: cannot enter the 1962-2002 read"})
            post = have[have > pd.Period("2002-12", "M")]
            res["months_present_2003_on"] = int(len(post))
            out[name] = res
    return out


# ===================================================================================== the gate
def run():
    G.registry.clear()
    P.COMPUTED.clear()
    res = {"written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "prereg": "research/xasset/PREREG_XASSET.md (dd2a819)", "notes": "research/xasset/IMPLEMENTATION_NOTES.md",
           "kind": ("§3 gate: validation statistics of constructions on spent 2003+ data; pre-2003 level-agreement "
                    "counts and coverage counts only; no sleeve return, signal or statistic on any date"),
           "thresholds": P.THRESHOLDS, "level_tolerance": LEVEL_TOL, "level_min_share": LEVEL_MIN_SHARE,
           "roll_window_days": ROLL_WINDOW_DAYS, "coverage_min_share": COVERAGE_MIN_SHARE}
    errors = []
    # frozen inputs
    v = L.verify_all()
    res["frozen_files"] = v
    if v["defects"]:
        errors.append("frozen-file defects")
    # the core (spent equity sample)
    core, *_ = L.core_reproduce()
    res["core_reproduction"] = core
    if not core["match_1e-6"]:
        errors.append("core does not reproduce RESULT_CAPITAL.json")
    # §3.3
    excl, com_keep = exclusions()
    res["exclusions"] = excl
    markets = {}
    # ---- already-validated constructions: re-run proxy.py and compare with VALIDATE.json
    ref = json.load(open(os.path.join(HERE, "VALIDATE.json")))["validation"]
    val = P.run_validation()
    rerun = {}
    for key, etf, prox, kind in (("US5", "IEI", "5y par bond (DGS5)", "treasury"),
                                 ("US10", "IEF", "10y par bond (DGS10)", "treasury"),
                                 ("GBP", "FXB", "GBP", "fx"), ("AUD", "FXA", "AUD", "fx"), ("CAD", "FXC", "CAD", "fx")):
        a = next(r for r in val[kind] if r["etf"] == etf and r["proxy"] == prox)
        b = next(r for r in ref[kind] if r["etf"] == etf and r["proxy"] == prox)
        same = all(a[k] == b[k] for k in ("corr", "te_share_of_etf_vol", "mean_diff_pct_per_year", "signal_agreement",
                                          "switch_diff_per_year", "validates", "months"))
        rerun[key] = {"comparator": etf, "values": {k: a[k] for k in ("months", "corr", "te_share_of_etf_vol",
                                                                       "mean_diff_pct_per_year", "signal_agreement",
                                                                       "switch_diff_per_year")},
                      "checks": a["checks"], "validates": a["validates"], "reproduces_VALIDATE_json": same}
        if not same:
            errors.append(f"{key}: VALIDATE.json not reproduced")
        cls = "bonds" if kind == "treasury" else "currencies"
        markets[key] = {"class": cls, "check": "§3.1 (VALIDATE.md, re-run)", **rerun[key],
                        "pass": bool(a["validates"] and same),
                        "drop_reason": None if a["validates"] else _reasons(a)}
    # ---- new currency constructions
    i_us = L.fred_rate(P.US_RATE_ID)
    for ccy, etf in (("JPY", "FXY"), ("CHF", "FXF")):
        try:
            pm, defects = L.fx_excess(ccy, monthly=True)
            px, _ = P.etf_series(etf)
            em = P.etf_excess(px, i_us, monthly=True, cash_monthly_rate=True, name=f"etf_{etf}_m_x")
            r = _pair(pm, em, f"{ccy}_{etf}_x")
            r["comparator"] = etf
            r["rate"] = {"JPY": "BoJ collateralised overnight call rate, end of month",
                         "CHF": "SNB call money (tomorrow-next), monthly"}[ccy]
            r["missing_differential_2003_on"] = sum(d["count"] for d in defects)
            markets[ccy] = {"class": "currencies", "check": "§3.1", **r, "pass": bool(r["validates"]),
                            "drop_reason": None if r["validates"] else _reasons(r)}
        except L.InputDefect as e:
            markets[ccy] = {"class": "currencies", "check": "§3.1", "evaluated": False, "pass": False,
                            "input_defect": str(e), "drop_reason": f"input_defect: {e}"}
    try:
        dem, _ = L.fx_excess("DEM", monthly=True)
        eur, _ = P.currency_excess(P.month_end(L.h10_spot("EUR")), L.fred_rate("IR3TIB01EZM156N"), i_us, "EUR",
                                   monthly=True, name="fx_EUR_m_x")
        r = _pair(dem, G.derived(eur, "fx_EUR_m_x"), "DEM_EURproxy")
        r["comparator"] = "euro proxy (H.10 DEXUSEU + OECD euro-area 3m, proxy.py; validated against FXE)"
        markets["DEM"] = {"class": "currencies", "check": "§3.1", **r, "pass": bool(r["validates"]),
                          "drop_reason": None if r["validates"] else _reasons(r)}
    except L.InputDefect as e:
        markets["DEM"] = {"class": "currencies", "check": "§3.1", "evaluated": False, "pass": False,
                          "drop_reason": f"input_defect: {e}"}
    for ccy in ("NOK", "SEK", "DKK"):
        markets[ccy] = {"class": "currencies", "check": "none registered (no executable comparator)",
                        "pass": True, "drop_reason": None,
                        "note": ("same H.10 + OECD 3m construction as the six validated currencies; enters where the "
                                 "differential is covered (§2 'where covered')")}
    # ---- non-US bonds vs same-country bond futures
    for c, fut in L.BOND_FUTURES.items():
        key = f"BOND_{c}"
        try:
            pm = L.intl_bond_monthly(c)
            fm = L.bond_future_monthly(c)
            r = _pair(pm, fm, f"bond_{c}")
            r["comparator"] = f"pysystemtrade {fut} (back-adjusted, held contract)"
            markets[key] = {"class": "bonds", "check": "§3.1", **r, "pass": bool(r["validates"]),
                            "drop_reason": None if r["validates"] else _reasons(r)}
        except L.InputDefect as e:
            markets[key] = {"class": "bonds", "check": "§3.1", "evaluated": False, "pass": False,
                            "drop_reason": f"input_defect: {e}"}
    # ---- commodities vs second source
    for m in com_keep:
        t = L.YF.get(m)
        if t is None:
            markets[m] = {"class": "commodities", "check": "§3.1", "evaluated": False, "pass": False,
                          "drop_reason": "no second source on 2003+ (not listed on yfinance; no CHRIS-style mirror)"}
            continue
        try:
            r = commodity_pair(m, t)
            markets[m] = {"class": "commodities", "check": "§3.1", **r, "pass": bool(r["validates"]),
                          "drop_reason": None if r["validates"] else _reasons(r)}
        except L.InputDefect as e:
            markets[m] = {"class": "commodities", "check": "§3.1", "evaluated": False, "pass": False,
                          "drop_reason": f"input_defect: {e}"}
    G.assert_clean()
    res["mask_check"] = {"registered_series": len(G.registry),
                         "earliest_date": str(min(v.index.min() for v in G.registry.values() if len(v)).date()),
                         "proxy_computed_series": len(P.COMPUTED)}
    # ---- §3.2 pre-2003 level counts (commodities kept after §3.3)
    lv = pre2003_level_counts(com_keep)
    res["level_checks_pre2003"] = lv
    for m, r in lv.items():
        if r.get("passes") is False and markets[m]["pass"]:
            markets[m]["pass"] = False
            markets[m]["drop_reason"] = (f"§3.2 level check: {r['pre2003_agree']}/{r['pre2003_same_contract_sessions']}"
                                         f" = {r['pre2003_share_agree']:.1%} < 95 % agreeing")
        elif r.get("passes") is False:
            markets[m]["drop_reason"] += f"; also §3.2 level check {r['pre2003_share_agree']:.1%} < 95 %"
        markets[m]["level_check"] = {k: r.get(k) for k in ("applicable", "pre2003_share_agree", "passes", "reason")}
    # ---- §3.4 coverage
    cov = coverage_counts({k: (v["class"], None) for k, v in markets.items()})
    res["coverage"] = cov
    for k, c in cov.items():
        markets[k]["coverage"] = c
        if "input_defect" in c:
            if markets[k]["pass"]:
                markets[k]["pass"] = False
                markets[k]["drop_reason"] = f"input_defect (coverage): {c['input_defect']}"
        elif c.get("passes") is False and markets[k]["pass"]:
            markets[k]["pass"] = False
            markets[k]["drop_reason"] = (f"§3.4 coverage {c['share']:.1%} of the expected month-ends "
                                         f"({c['first_month_all_inputs']}..2002-12) < 95 %")
        elif c.get("passes") is None and markets[k]["pass"]:
            markets[k]["enters_read"] = False
            markets[k]["note_read"] = "passes, but has no pre-2003 month: cannot enter the 1962-2002 read"
    for k, v in markets.items():
        v.setdefault("enters_read", bool(v["pass"]))
        if not v["pass"]:
            v["enters_read"] = False
    res["markets"] = markets
    ent = {c: sorted(k for k, v in markets.items() if v["class"] == c and v["enters_read"]) for c in L.CLASSES}
    res["entering_read"] = {c: {"n": len(v), "markets": v} for c, v in ent.items()}
    res["dropped"] = {k: v["drop_reason"] for k, v in markets.items() if not v["pass"]}
    res["loader_notes"] = L.LOADER_NOTES
    res["diagnostic_mirror_convention_spent_2003_2019"] = mirror_convention_spent(com_keep)
    res["errors"] = errors
    empty = [c for c, v in res["entering_read"].items() if v["n"] == 0]
    res["gate_evaluable"] = not errors
    res["gate"] = "cannot be evaluated" if errors else ("fail" if empty else "pass")
    res["gate_fail_reasons"] = [f"no {c} market survives the checks (IMPLEMENTATION_NOTES A11: each asset class "
                                "must keep at least one market)" for c in empty]
    return res


def mirror_convention_spent(markets):
    """Diagnostic on spent 2003-2019 levels, added after the first gate run; it decides nothing. Share of common
    sessions on which the CHRIS-style mirror's settlement is within 0.5 % (and within 0.01 %) of pysystemtrade's
    PRICE (held), CARRY and FORWARD contracts: which contract the mirror actually carries."""
    out = {}
    for m in markets:
        sym = L.CHRIS.get(m)
        if sym is None:
            continue
        f = L.pst_frame(m)
        c = L.chris_settle(sym)
        j = f.join(c.rename("CH"), how="inner")
        if not len(j):
            out[m] = {"common_sessions": 0}
            continue
        out[m] = {"common_sessions": int(len(j)), "first": str(j.index.min().date()),
                  "within_0.5pct": {k: round(float((np.abs(j.CH / j[k] - 1) <= LEVEL_TOL).mean()), 3)
                                    for k in ("PRICE", "CARRY", "FORWARD")},
                  "within_0.01pct": {k: round(float((np.abs(j.CH / j[k] - 1) <= 1e-4).mean()), 3)
                                     for k in ("PRICE", "CARRY", "FORWARD")}}
    return out


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "fetch":
        return fetch()
    if cmd != "run":
        raise SystemExit(f"unknown command {cmd}")
    try:
        res = run()
    except Exception as e:                                           # noqa: BLE001
        import traceback
        res = {"gate": "cannot be evaluated", "gate_evaluable": False, "exception": repr(e)[:500],
               "traceback": traceback.format_exc()[-3000:]}
        json.dump(res, open(L.CHECKS_OUT, "w"), indent=1, default=str)
        print(json.dumps(res, indent=1))
        return 2
    json.dump(res, open(L.CHECKS_OUT, "w"), indent=1, default=str)
    print(json.dumps({"gate": res["gate"], "gate_fail_reasons": res["gate_fail_reasons"], "errors": res["errors"],
                      "entering_read": res["entering_read"], "dropped": res["dropped"]}, indent=1))
    return {"pass": 0, "fail": 1}.get(res["gate"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
