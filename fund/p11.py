"""Protocol 11 (shadow only; PROTOCOL_fund.md, research/eventrisk/PLAN.md "The assembly"). Nothing here trades.

An earnings report inside a position's holding period: the event-inclusive width
    W11 = sqrt((H - n_E) sigma_d^2 + n_E c* sigma_d^2)   and the size scalar   s = sqrt(H sigma_d^2 / W11^2),
recorded next to the live sigma_e and W, frozen at first write. sigma_d is the entry volatility (EWMA span 60, floored at
0.75 x the 252-session std, as fund/lifecycle.py entry_vol) of the residual returns with the firm's own report reaction
sessions masked out; c* the firm's shrunk report-day variance multiple (research/eventrisk/study.py `multiples`).

    FUND_ASOF=2026-11-18 python fund/p11.py screen   # weekly, shadow stage: next reports, c*, pooled multiple
    python fund/p11.py nightly                        # reconcile, after the rebuild: shadow entry widths, audit rows
    python fund/p11.py status screen|nightly          # prints "ok" or the problem (the runner opens an issue)

Separate process and separate files: the live path never imports this module and never reads its files.
* <week>/p11_screen.json                weekly screen output (frozen at first write)
* p11/ratios.csv                       report-day ratios q, frozen at first computation (append-only)
* lifecycle/p11/entries.json           shadow values per entry, keyed like lifecycle/entries.json (frozen)
* lifecycle/p11/audit.csv              one row per report window passed (append-only)
* lifecycle/p11/status.json            the nightly status the runner reads
Typed defects (shadow = live, counted): no_calendar_date, no_report_history, no_pooled_multiple, no_p11_screen,
input_mismatch. Errors: shadow_error:<Type>, counted, not recorded, retried the next night.
"""
import csv
import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lifecycle_rules import P11_SHADOW  # noqa: E402

SPAN, FLOOR = 60, 0.75                  # fund/lifecycle.py entry_vol and research/eventrisk/study.py
MIN_POOLED, FIRM_LAST = 200, 12         # study.py multiples: >= 200 past ratios; firm mean of the last <= 12
HIST_DAYS, CAL_DAYS, AHEAD_DAYS = 1650, 100, 150   # price/EDGAR history (~4.5 years), calendar window, sessions ahead
KEEP_DAYS = 600                         # past report sessions kept per firm in the screen (entry window is 420 days)
COVER = {"priced": 0.90, "calendar": 0.70, "history": 0.80}   # screen coverage expected of the members
SIGMA_TOL = 0.01                        # the recomputed sigma_e must match the recorded one within 1%
ALERT = ("no_pooled_multiple", "no_p11_screen", "input_mismatch")   # defects that also raise the runner's alert


# ======================================================================= pure functions
def sigma(e):
    """research/eventrisk/study.py sigma: max(EW std span 60, 0.75 x 252-session std) on a (T, N) frame."""
    ew = e.ewm(span=SPAN, min_periods=SPAN, ignore_na=True).std()
    sd = e.rolling(252, min_periods=120).std()
    return np.maximum(ew, FLOOR * sd)


def residuals(r, rm):
    """study.py load: e = r - b x r_SPY, b = 2/3 x (252-session slope-winsorised OLS beta, lagged) + 1/3."""
    lo, hi = np.minimum(-2 * rm, 4 * rm), np.maximum(-2 * rm, 4 * rm)
    w = r.clip(lower=lo, upper=hi, axis=0)
    ols = w.rolling(252, min_periods=200).cov(rm).div(rm.rolling(252, min_periods=200).var(), axis=0)
    b = (2 / 3 * ols + 1 / 3).shift(1)
    return r.sub(b.mul(rm, axis=0))


def sd_daily(e, E):
    """study.py build: sigma_d on returns with the report sessions masked; a report session keeps the last value."""
    return sigma(e.mask(E)).ffill(limit=1)


def ratios(e, E, sd_d):
    """study.py multiples: q = e^2 / sigma_d(previous session)^2 on report sessions, NaN elsewhere."""
    return (e ** 2 / sd_d.shift(1) ** 2).where(E)


def pool(q):
    """study.py multiples after q: the pooled multiple c and shrinkage k (refit on the first session of each month on
    the ratios before it; needs >= 200), the firm mean cf of its last <= 12 ratios up to each session, their count nf,
    and c* = (cf n + k c) / (n + k). Returns (c_t, k_t, cs, cf, nf)."""
    T, N = q.shape
    qv = q.to_numpy()
    month = q.index.to_period("M")
    first = np.r_[True, month[1:] != month[:-1]]
    c_t, k_t = np.full(T, np.nan), np.full(T, np.nan)
    c, k = np.nan, np.nan
    for t in range(T):
        if first[t]:
            past = qv[:t]
            n_i = np.isfinite(past).sum(0)
            if n_i.sum() >= MIN_POOLED:
                c = float(np.nanmean(past))
                two = n_i >= 2
                mean_i = np.nanmean(past[:, two], 0)
                s_w = float(np.nansum((past[:, two] - mean_i) ** 2) / (n_i[two].sum() - two.sum()))
                tau = max(float(mean_i.var(ddof=1)) - s_w * float((1 / n_i[two]).mean()), 0.0)
                k = float(np.clip(s_w / tau, 1, 200)) if tau > 0 else 200.0
        c_t[t], k_t[t] = c, k
    cf, nf = np.full((T, N), np.nan), np.zeros((T, N))
    for i in range(N):
        idx = np.where(np.isfinite(qv[:, i]))[0]
        if not len(idx):
            continue
        vals = qv[idx, i]
        m = np.array([vals[max(0, j - FIRM_LAST + 1):j + 1].mean() for j in range(len(idx))])
        n = np.minimum(np.arange(1, len(idx) + 1), FIRM_LAST)
        seg = np.searchsorted(idx, np.arange(T), side="right") - 1
        has = seg >= 0
        cf[has, i], nf[has, i] = m[seg[has]], n[seg[has]]
    cs = (np.nan_to_num(cf) * nf + k_t[:, None] * c_t[:, None]) / (nf + k_t[:, None])
    return c_t, k_t, cs, cf, nf


def multiples(e, E, sd_d):
    """The same return values as research/eventrisk/study.py multiples: (q, c_t, k_t, cs)."""
    q = ratios(e, E, sd_d)
    c_t, k_t, cs, _, _ = pool(q)
    return q, c_t, k_t, cs


def report_frame(index, sessions, names):
    """Boolean (T, N) frame: True on each firm's report reaction sessions."""
    E = pd.DataFrame(False, index=index, columns=names)
    for t in names:
        ss = [s for s in sessions.get(t, []) if s in E.index]
        if ss:
            E.loc[ss, t] = True
    return E


def freeze_ratios(q, stored):
    """Rule 4: a ratio recorded once is never recomputed. stored: {(ticker, session): q}. Returns (q with the stored
    values in place, new rows {(ticker, session): q} not yet recorded)."""
    q = q.copy()
    for (t, s), v in stored.items():
        if t in q.columns and s in q.index and np.isfinite(q.at[s, t]):
            q.at[s, t] = v
    new = {}
    for t in q.columns:
        col = q[t].dropna()
        for s, v in col.items():
            if (t, s) not in stored:
                new[(t, s)] = float(v)
    return q, new


def catalyst_session(e, days):
    """fund/lifecycle.py catalyst_session, unchanged: the session that first trades on an earnings release, from the
    calendar's (date, hour): its date before the open or in hours, else the next session."""
    if not e:
        return None
    d = pd.Timestamp(e[0])
    return next((x for x in days if x > d or (x == d and e[1] in ("bmo", "dmh", ""))), None)


def sigma_entry(e, mask):
    """fund/lifecycle.py entry_vol's estimator on residual returns e (a Series to the entry information set), with the
    sessions in `mask` (bool array) left out: max(EWMA span 60 std, 0.75 x std of the last 252 sessions)."""
    m = np.asarray(mask, bool)
    keep = e[~m]
    ew = float(keep.ewm(span=SPAN).std().iloc[-1])
    tail = e.iloc[-252:][~m[-252:]]
    sd = float(tail.std())
    return {"sigma_ewma": ew, "sigma_252": sd, "sigma": max(ew, FLOOR * sd)}


def window_sessions(entry_day, H, sessions):
    """The H sessions entry+1 .. entry+H, or None when the calendar does not reach that far."""
    after = [s for s in sessions if s > pd.Timestamp(entry_day)][:H]
    return after if len(after) == H else None


def shadow_width(sigma_d, H, n_E, c_star):
    """PLAN.md Decisions 1 and 4: W11 and the size scalar."""
    V = (H - n_E) * sigma_d ** 2 + n_E * c_star * sigma_d ** 2
    return math.sqrt(V), math.sqrt(H * sigma_d ** 2 / V)


def entry_record(lot, row, pooled, e, sessions):
    """The shadow record of one entry. lot: the live lot at entry (ticker, H, sigma_e, W, beta, entry_day, cohort);
    row: the ticker's row of the cohort's p11_screen.json (None: no screen); pooled: its {"c", "k"}; e: residual returns
    (lot beta) to the entry information set, as entry_vol computed them; sessions: trading sessions covering the
    window. Shadow equals live (W11 = W, scalar 1) on any typed defect."""
    H, W, sig_e = int(lot["H"]), float(lot["W"]), float(lot["sigma_e"])
    rec = {"ticker": lot["ticker"], "cohort": lot["cohort"], "entry_day": lot["entry_day"], "H": H, "beta": lot["beta"],
           "sigma_e": sig_e, "W": W, "defect": None}
    defect = None
    if row is None:
        defect = "no_p11_screen"
    elif not (pooled and pooled.get("c") is not None and np.isfinite(pooled["c"])):
        defect = "no_pooled_multiple"
    if row is not None:
        past = set(pd.Timestamp(s) for s in row.get("report_sessions") or [])
        mask = e.index.isin(list(past))
        chk = sigma_entry(e, np.zeros(len(e), bool))
        sd = sigma_entry(e, mask)
        rec.update(sigma_d=sd["sigma"], sigma_d_ewma=sd["sigma_ewma"], sigma_d_252=sd["sigma_252"], sigma_e_check=chk["sigma"],
                   masked_sessions=int(mask.sum()), c_star=row.get("c_star"), c_firm=row.get("c_firm"), n_firm=row.get("n_firm"),
                   c_pooled=(pooled or {}).get("c"), k=(pooled or {}).get("k"), calendar=row.get("calendar") or [])
        win = window_sessions(lot["entry_day"], H, sessions)
        react = [catalyst_session(x, sessions) for x in row.get("calendar") or []]
        rec["reaction_sessions"] = sorted({str(s.date()) for s in react if s is not None})
        if defect is None:
            if abs(chk["sigma"] - sig_e) > SIGMA_TOL * sig_e or abs(W - sig_e * math.sqrt(H)) > 1e-9 or win is None:
                defect = "input_mismatch"            # rule 2: the inputs do not reproduce the live entry
            elif not row.get("calendar"):
                defect = "no_calendar_date"
            elif not row.get("n_firm"):
                defect = "no_report_history"
        if win is not None:
            rec["window"] = [str(win[0].date()), str(win[-1].date())]
            rec["n_E"] = int(sum(1 for s in react if s is not None and s in win))
    if defect is None:
        rec["W11"], rec["scalar"] = shadow_width(rec["sigma_d"], H, rec["n_E"], float(rec["c_star"]))
    else:
        rec["W11"], rec["scalar"] = W, 1.0
    rec["defect"] = defect
    rec["report_inside"] = None if defect in ("no_p11_screen", "no_calendar_date", "input_mismatch") else bool(rec.get("n_E"))
    return rec


def audit_row(key, rec, e_win, sessions_win):
    """One report window passed: realised sum of e^2 over entry+1..entry+H (lot beta, frozen returns) against the
    shadow forecast W11^2 and the live W^2; the report session's own e^2 against c* sigma_d^2."""
    e_win = np.asarray(e_win, float)
    ok = bool(np.isfinite(e_win).all())
    rv = float((e_win ** 2).sum()) if ok else float("nan")
    rep = [i for i, s in enumerate(sessions_win) if str(pd.Timestamp(s).date()) in set(rec.get("reaction_sessions") or [])]
    e2 = float(sum(e_win[i] ** 2 for i in rep)) if ok and rep else float("nan")
    return {"key": key, "ticker": rec["ticker"], "entry_day": rec["entry_day"], "H": rec["H"], "n_E": rec["n_E"],
            "reaction_sessions": " ".join(rec.get("reaction_sessions") or []), "e2_report": e2,
            "forecast_report": float(rec["c_star"]) * rec["sigma_d"] ** 2 * max(len(rep), 1),
            "realised_window": rv, "forecast_W11sq": rec["W11"] ** 2, "forecast_live_Wsq": rec["W"] ** 2,
            "ratio_shadow": rv / rec["W11"] ** 2 if ok else float("nan"), "ratio_live": rv / rec["W"] ** 2 if ok else float("nan"),
            "note": "" if ok else "missing_returns"}


AUDIT_COLS = ["key", "ticker", "entry_day", "H", "n_E", "reaction_sessions", "e2_report", "forecast_report", "realised_window",
              "forecast_W11sq", "forecast_live_Wsq", "ratio_shadow", "ratio_live", "note", "written"]


def removal_rule(rows):
    """PLAN.md: after 100 report windows, realised / forecast variance outside 0.7-1.5 switches the component off."""
    x = [float(r["ratio_shadow"]) for r in rows if r.get("ratio_shadow") not in ("", None) and np.isfinite(float(r["ratio_shadow"]))]
    m = float(np.mean(x)) if x else None
    return {"windows": len(x), "mean_ratio_shadow": m, "decided": len(x) >= 100,
            "outside_0.7_1.5": bool(m is not None and not 0.7 <= m <= 1.5)}


# ======================================================================= I/O (thin)
def alpaca_closes(tickers, start, end):
    """Daily closes, Alpaca SIP, adjusted for splits and dividends (as fund/lifecycle.py closes), never newer than
    15 minutes (the plan refuses SIP data that recent: 2026-11-12)."""
    import broker
    stop = min(pd.Timestamp(end) + pd.Timedelta(days=1), pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(minutes=16))
    rows, names = [], sorted(tickers)
    for i in range(0, len(names), 100):
        token = None
        while True:
            q = (f"/v2/stocks/bars?symbols={','.join(names[i:i + 100])}&timeframe=1Day&adjustment=all&feed=sip&limit=10000"
                 f"&start={pd.Timestamp(start).date()}&end={stop.strftime('%Y-%m-%dT%H:%M:%SZ')}" + (f"&page_token={token}" if token else ""))
            s_, b = broker.api("GET", q, base=broker.DATA)
            assert s_ == 200, f"Alpaca bars unavailable ({s_})"
            for t, xs in (b.get("bars") or {}).items():
                rows += [{"date": pd.Timestamp(x["t"][:10]), "ticker": t, "close": float(x["c"])} for x in xs]
            token = b.get("next_page_token")
            if not token:
                break
    D = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    return D.pivot_table(index="date", columns="ticker", values="close").sort_index()


def _sec_get(url, ua):
    import gzip
    for k in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                return json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
        except Exception:
            if k == 2:
                raise
            time.sleep(3 * (k + 1))


def edgar_202(tickers, lo):
    """8-K / 8-K/A filings with item 2.02 accepted since `lo` (the typed `items` field of EDGAR's submissions API, as
    fund/lifecycle.py edgar_202), including the older filing pages when the recent block does not reach `lo`.
    Returns ({ticker: [acceptanceDateTime (UTC)]}, {ticker: "ok" | "no_cik" | "error: ..."})."""
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    assert ua, "SEC_USER_AGENT is needed for the earnings-release history"
    cik = {v["ticker"]: int(v["cik_str"]) for v in _sec_get("https://www.sec.gov/files/company_tickers.json", ua).values()}
    lo_s = str(pd.Timestamp(lo).date())
    acc, st = {}, {}

    def pick(blk):
        return [blk["acceptanceDateTime"][i][:19] for i, f in enumerate(blk["form"])
                if f in ("8-K", "8-K/A") and "2.02" in str(blk["items"][i]).split(",") and blk["acceptanceDateTime"][i][:10] >= lo_s]
    for t in sorted(tickers):
        c = cik.get(t.replace(".", "-"))
        if c is None:
            st[t] = "no_cik"; continue
        try:
            time.sleep(0.12)                                    # SEC fair access: < 10 requests per second
            sub = _sec_get(f"https://data.sec.gov/submissions/CIK{c:010d}.json", ua)["filings"]
            a = pick(sub["recent"])
            if min(sub["recent"]["filingDate"] or ["9999"]) > lo_s:
                for f in sub.get("files") or []:
                    if f.get("filingTo", "") >= lo_s:
                        time.sleep(0.12)
                        a += pick(_sec_get(f"https://data.sec.gov/submissions/{f['name']}", ua))
            acc[t], st[t] = sorted(set(a)), "ok"
        except Exception as exc:                                # noqa: BLE001 (counted: the firm has no history)
            st[t] = f"error: {type(exc).__name__}"
    return acc, st


def finnhub_calendar(lo, hi):
    """Finnhub's earnings calendar (the fund's source) in 7-day requests: {ticker: [(date, hour)]} with lo < date <= hi."""
    key, out = os.environ["FINNHUB_API_KEY"], {}
    d = pd.Timestamp(lo)
    while d < pd.Timestamp(hi):
        e = min(d + pd.Timedelta(days=7), pd.Timestamp(hi))
        url = f"https://finnhub.io/api/v1/calendar/earnings?from={(d + pd.Timedelta(days=1)).date()}&to={e.date()}&token={key}"
        for k in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    xs = json.load(r).get("earningsCalendar", [])
                break
            except Exception:
                if k == 2:
                    raise
                time.sleep(5 * (k + 1))
        for x in xs:
            if x.get("date") and x.get("symbol"):
                out.setdefault(x["symbol"].replace("-", "."), set()).add((x["date"], (x.get("hour") or "").lower()))
        time.sleep(1.05)
        d = e
    return {t: sorted(v) for t, v in out.items()}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def screen_build(asof, members, closes, acc, cal, days, stored):
    """The weekly screen from its inputs (no network): members; closes (sessions x tickers, with SPY); acc {ticker:
    [8-K 2.02 acceptance, UTC]}; cal {ticker: [(date, hour)]}; days: trading sessions from the history start to
    asof + AHEAD_DAYS; stored: the frozen ratios. Returns (output, new ratios)."""
    from amend7b2 import session_of
    from edgar_time import et_from_api
    past = pd.DatetimeIndex([d for d in days if d <= asof])
    r = closes.reindex(past).pct_change(fill_method=None)
    names = [t for t in members if t in r and r[t].notna().sum() >= 260]
    e = residuals(r[names], r["SPY"])
    sess = {t: sorted({s for s in (session_of(et_from_api(a), days) for a in acc.get(t, [])) if s is not None and s <= asof})
            for t in names}
    E = report_frame(e.index, sess, names)
    q, new = freeze_ratios(ratios(e, E, sd_daily(e, E)), stored)
    c_t, k_t, cs, cf, nf = pool(q)
    c, k = float(c_t[-1]), float(k_t[-1])
    ix = {t: i for i, t in enumerate(names)}
    rows = {}
    for t in members:
        i = ix.get(t)
        cal_t = [list(x) for x in cal.get(t, [])]
        rows[t] = {"priced": i is not None, "calendar": cal_t,
                   "reaction_sessions": sorted({str(s.date()) for s in (catalyst_session(x, days) for x in cal_t) if s is not None}),
                   "report_sessions": [str(s.date()) for s in sess.get(t, []) if s >= asof - pd.Timedelta(days=KEEP_DAYS)],
                   "n_firm": int(nf[-1, i]) if i is not None else 0,
                   "c_firm": float(cf[-1, i]) if i is not None and nf[-1, i] > 0 else None,
                   "c_star": float(cs[-1, i]) if i is not None and np.isfinite(cs[-1, i]) else None}
    n = len(members)
    cov = {"members": n, "priced": sum(x["priced"] for x in rows.values()), "calendar": sum(bool(x["calendar"]) for x in rows.values()),
           "history": sum(x["n_firm"] > 0 for x in rows.values())}
    problems = [f"{k_} for {cov[k_]} of {n} members (< {v:.0%})" for k_, v in COVER.items() if cov[k_] < v * n]
    n_ratios = int(np.isfinite(q.to_numpy()).sum())
    if not np.isfinite(c):
        problems.append(f"no_pooled_multiple: {n_ratios} ratios before this month (< {MIN_POOLED})")
    out = {"asof": str(asof.date()), "status": "ok" if not problems else "; ".join(problems), "coverage": cov,
           "pooled": {"c": c if np.isfinite(c) else None, "k": k if np.isfinite(k) else None, "n_ratios": n_ratios},
           "defects": {"no_calendar_date": n - cov["calendar"], "no_report_history": n - cov["history"]},
           "sessions": [str(d.date()) for d in days if asof - pd.Timedelta(days=10) <= d <= asof + pd.Timedelta(days=AHEAD_DAYS)],
           "rows": rows}
    return out, new


def screen(state=None, asof=None):
    """Weekly (shadow stage of the weekly job). From the first as-of whose entry falls on or after P11_SHADOW."""
    import common
    state = state or common.STATE
    asof = pd.Timestamp(asof) if asof is not None else common.asof_from_env()
    if asof + pd.Timedelta(days=1) < P11_SHADOW:
        print(f"p11 screen: Protocol 11 shadow starts with the session {P11_SHADOW.date()}; nothing written for {asof.date()}")
        return None
    wd = os.path.join(state, common.MODE, str(asof.date()))
    out_p = os.path.join(wd, "p11_screen.json")
    if os.path.exists(out_p) and not json.load(open(out_p))["status"].startswith("shadow_error"):
        print(f"p11 screen {asof.date()}: already recorded (frozen at first write)")
        return json.load(open(out_p))
    store_p = os.path.join(state, common.MODE, "p11", "ratios.csv")
    try:
        import broker
        members = sorted(x["ticker"] for x in json.load(open(os.path.join(wd, "screen.json")))["rows"])
        start = asof - pd.Timedelta(days=HIST_DAYS)
        s_, cal_ = broker.api("GET", f"/v2/calendar?start={start.date()}&end={(asof + pd.Timedelta(days=AHEAD_DAYS)).date()}")
        assert s_ == 200 and cal_, f"calendar unavailable: {s_}"
        days = [pd.Timestamp(x["date"]) for x in cal_]
        closes = alpaca_closes(set(members) | {"SPY"}, start, asof)
        acc, est = edgar_202(members, start)
        cal = finnhub_calendar(asof, asof + pd.Timedelta(days=CAL_DAYS))
        stored = {}
        if os.path.exists(store_p):
            for x in csv.DictReader(open(store_p)):
                stored[(x["ticker"], pd.Timestamp(x["session"]))] = float(x["q"])
        out, new = screen_build(asof, members, closes, acc, cal, days, stored)
        for t, s in est.items():
            out["rows"][t]["edgar"] = s
        os.makedirs(os.path.dirname(store_p), exist_ok=True)
        fresh = not os.path.exists(store_p)
        with open(store_p, "a", newline="") as fh:                       # append-only, frozen at first computation
            w = csv.writer(fh)
            if fresh:
                w.writerow(["ticker", "session", "q", "first_asof"])
            for (t, s), v in sorted(new.items(), key=lambda x: (x[0][1], x[0][0])):
                w.writerow([t, str(s.date()), repr(v), str(asof.date())])
    except Exception as exc:                                             # noqa: BLE001 (shadow: counted, alert raised)
        out = {"asof": str(asof.date()), "status": f"shadow_error:{type(exc).__name__}: {str(exc)[:200]}", "rows": {}}
    out["written"] = _now()
    os.makedirs(wd, exist_ok=True)
    json.dump(out, open(out_p, "w"), indent=0, sort_keys=True, default=str)
    print(f"p11 screen {asof.date()}: {out['status']}; pooled {out.get('pooled')}; coverage {out.get('coverage')}")
    return out


def live_entries(lc):
    """Entries the live book made from P11_SHADOW: (day, lot) for each lot of a submitted live log that entered that day."""
    import glob
    out = []
    for f in sorted(glob.glob(os.path.join(lc, "live", "20*.json"))):
        if f.endswith(".plan.json"):
            continue
        x = json.load(open(f))
        if x.get("status") != "submitted" or pd.Timestamp(x["day"]) < P11_SHADOW:
            continue
        out += [(x["day"], L) for L in x.get("lots_after", []) if L.get("entry_day") == x["day"]]
    return out


def entry_residuals(lot, sessions):
    """Residual returns as entry_vol computed them for a live entry: closes to the previous session, e = r - beta r_SPY."""
    t, day = lot["ticker"], pd.Timestamp(lot["entry_day"])
    end = max(s for s in sessions if s < day)
    px = alpaca_closes({t, "SPY"}, end - pd.Timedelta(days=420), end)
    r = px.loc[:end].pct_change().dropna()
    return r[t] - float(lot["beta"]) * r["SPY"]


def nightly(state=None, residuals_of=entry_residuals):
    """Reconcile job, after the rebuild: shadow records for new entries (frozen), audit rows for report windows passed,
    and the status the runner reads. Reads the live logs, entries.json and returns.csv; writes only lifecycle/p11/."""
    import common
    state = state or common.STATE
    lc = os.path.join(state, common.MODE, "lifecycle")
    todo = live_entries(lc)
    if not todo:
        print(f"p11 nightly: no live entry from {P11_SHADOW.date()} yet; nothing written")
        return None
    pdir = os.path.join(lc, "p11")
    os.makedirs(pdir, exist_ok=True)
    ep = os.path.join(pdir, "entries.json")
    rec = json.load(open(ep)) if os.path.exists(ep) else {}
    errors, new = [], 0
    for day, L in todo:
        key = f"{L['cohort']}|{L['ticker']}|{L['entry_day']}"
        if key in rec:
            continue                                                    # frozen at first write
        try:
            sp = os.path.join(state, common.MODE, L["cohort"], "p11_screen.json")
            scr = json.load(open(sp)) if os.path.exists(sp) else None
            ok_scr = scr is not None and not str(scr.get("status", "")).startswith("shadow_error")
            row = (scr["rows"].get(L["ticker"]) if ok_scr else None)
            sessions = [pd.Timestamp(s) for s in (scr or {}).get("sessions", [])]
            e = residuals_of(L, sessions) if row is not None else pd.Series(dtype=float)
            rec[key] = {**entry_record(L, row, (scr or {}).get("pooled"), e, sessions), "written": _now()}
            new += 1
        except Exception as exc:                                        # noqa: BLE001 (counted, retried next night)
            errors.append(f"shadow_error:{type(exc).__name__} {key}: {str(exc)[:120]}")
    json.dump(rec, open(ep, "w"), indent=0, sort_keys=True, default=str)
    ap = os.path.join(pdir, "audit.csv")
    done = {x["key"] for x in csv.DictReader(open(ap))} if os.path.exists(ap) else set()
    rows = []
    try:
        R = pd.read_csv(os.path.join(lc, "returns.csv"), parse_dates=["date"]).pivot_table(index="date", columns="ticker", values="ret")
        for key, x in sorted(rec.items()):
            if key in done or x.get("defect") or not x.get("n_E") or not x.get("window"):
                continue
            if pd.Timestamp(x["window"][1]) > R.index.max():
                continue                                                # the window has not passed yet
            win = R.index[(R.index > pd.Timestamp(x["entry_day"])) & (R.index <= pd.Timestamp(x["window"][1]))]
            ew = (R.loc[win, x["ticker"]] - float(x["beta"]) * R.loc[win, "SPY"]).to_numpy() if x["ticker"] in R else np.full(len(win), np.nan)
            if len(win) != x["H"]:
                ew = np.full(x["H"], np.nan)
            rows.append({**audit_row(key, x, ew, list(win) if len(win) == x["H"] else []), "written": _now()})
    except Exception as exc:                                            # noqa: BLE001
        errors.append(f"shadow_error:{type(exc).__name__} audit: {str(exc)[:120]}")
    if rows:
        fresh = not os.path.exists(ap)
        with open(ap, "a", newline="") as fh:                           # append-only
            w = csv.DictWriter(fh, AUDIT_COLS)
            if fresh:
                w.writeheader()
            w.writerows(rows)
    allrows = list(csv.DictReader(open(ap))) if os.path.exists(ap) else []
    from collections import Counter
    counts = Counter(x.get("defect") or "ok" for x in rec.values())
    expected = {f"{L['cohort']}|{L['ticker']}|{L['entry_day']}" for _, L in todo}
    problems = list(errors) + [f"{d}: {counts[d]}" for d in ALERT if counts.get(d)]
    if expected - set(rec):
        problems.append(f"{len(expected - set(rec))} of {len(expected)} entries without a shadow record")
    st = {"updated": _now(), "status": "ok" if not problems else "; ".join(problems), "entries": len(rec), "new": new,
          "expected": len(expected), "counts": dict(counts), "report_inside": sum(bool(x.get("report_inside")) for x in rec.values()),
          "audit_rows": len(allrows), "missing_returns": sum(x.get("note") == "missing_returns" for x in allrows),
          "removal_rule": removal_rule(allrows)}
    json.dump(st, open(os.path.join(pdir, "status.json"), "w"), indent=1)
    print(f"p11 nightly: {st['status']}; {len(rec)} entries ({new} new), defects {dict(counts)}, {len(rows)} audit rows added")
    return st


def status(stage, state=None, now=None):
    """What the runner reads: "ok", or the problem. Before the shadow start, or with nothing to do yet, "ok"."""
    import common
    state = state or common.STATE
    now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC").tz_localize(None)
    if stage == "screen":
        asof = common.asof_from_env()
        if asof + pd.Timedelta(days=1) < P11_SHADOW:
            return "ok"
        p = os.path.join(state, common.MODE, str(asof.date()), "p11_screen.json")
        return json.load(open(p))["status"] if os.path.exists(p) else "p11_screen.json missing"
    lc = os.path.join(state, common.MODE, "lifecycle")
    if not live_entries(lc):
        return "ok"
    p = os.path.join(lc, "p11", "status.json")
    if not os.path.exists(p):
        return "lifecycle/p11/status.json missing"
    st = json.load(open(p))
    if now - pd.Timestamp(st["updated"]).tz_localize(None) > pd.Timedelta(hours=20):
        return f"stale: last nightly status {st['updated']}"
    return st["status"]


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "screen":
        screen()
    elif cmd == "nightly":
        nightly()
    elif cmd == "status":
        try:
            print(status(sys.argv[2]))
        except Exception as exc:                                        # noqa: BLE001
            print(f"shadow_error:{type(exc).__name__}: {exc}")
    else:
        raise SystemExit(f"unknown command {cmd}")
