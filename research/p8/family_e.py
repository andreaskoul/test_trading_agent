"""Family E (reports/research/PREREG_family_E.md): data build and the dry fit on 2016-2021.

    python research/p8/family_e.py live       # every firm's filing history from SEC's live API (SEC_USER_AGENT)
    python research/p8/family_e.py items      # 8-K items with acceptance times -> .cache/p8/items8k.parquet
    python research/p8/family_e.py dry-fit    # E1/E2 cell selection, E3 pipeline check -> reports/research/p8/E_DRY_FIT.*
    python research/p8/family_e.py rehearse   # the validation code on the fit sample: no lock, B = 199, nothing written
    python research/p8/family_e.py validate   # ONCE: E1 and E2 on 2022-2025 -> E_VALIDATION.lock, .md, .json

No lock: the fit sample (event sessions 2016-01-01 .. 2021-12-31, target windows ending by 2021-12-31) chooses each
module's one primary cell by the written rule. Validation (2022-2025) and sealed (2026) data are never loaded here:
the price panel stops at 2025-12-31 and every fit statistic drops rows whose window ends after 2021-12-31.

Definitions (PREREG_family_E.md §1-§4):
* Returns: Alpaca SIP adjusted closes from 2016-01-04 (delisted names included), |r| > 75% set missing.
* Residual e = r - b x r_SPY, b = the shrunk Welch beta of research/p8/residuals.betas (252 sessions ending 21
  sessions before the event).
* Info time: an 8-K accepted before 15:40 ET on a session belongs to that session, else to the next (t0). Earnings
  events use the 16:00 rule (events.t0_of), as registered for E1. Acceptance times come from SEC's live API (true
  UTC), converted to Eastern; SEC's bulk file mixes encodings (PREREG_family_E.md Amendment 1).
* E2 hard 8-K: items 2.01, 2.05, 2.06 or 4.02, no 2.02 in the filing, no 2.02 within +-2 sessions.
* E3 soft 8-K: items 5.02 or 1.01, none of E2's items, no 2.02 in the filing or within +-2 sessions.
* S&P 500 membership at t0, point in time. One event per name per h sessions (the first).
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import events as EV                                              # noqa: E402
import prices as PX                                              # noqa: E402
import inference as I                                            # noqa: E402
import residuals as RS                                           # noqa: E402
sys.path.insert(0, os.path.join(PX.ROOT, "fund"))
from edgar_time import et_from_api                               # noqa: E402

FIT0, FIT1 = pd.Timestamp("2016-01-01"), pd.Timestamp("2021-12-31")
LAST = pd.Timestamp("2025-12-31 23:59:59")
HARD, SOFT = {"2.01", "2.05", "2.06", "4.02"}, {"5.02", "1.01"}
E1_GRID = [(entry, h) for entry in ("t0", "t0+1") for h in (5, 10, 20, 40)]
E2_GRID = (5, 10, 20)
C_LIVE, C_STRESS = 4.0, 20.0                                     # round trip, bp (§3)
ITEMS = os.path.join(PX.CACHE, "items8k.parquet")
LIVE = os.path.join(ED.CACHE, "submissions_live")             # live-API histories: acceptance times in true UTC


def returns_2016():
    A = PX.panel().sort_index()
    R = A.pct_change(fill_method=None)
    R = R[R.index > RS.SPLICE]
    bad = R.drop(columns=[c for c in RS.ETF.values() if c in R] + ["SPY"]).abs() > 0.75
    return R.mask(bad.reindex(columns=R.columns, fill_value=False))


def live():
    """Each firm's full filing history from SEC's live API (recent block plus its older pages). Acceptance times there
    are true UTC; SEC's bulk submissions.zip mixes encodings for the same field (PREREG_family_E.md Amendment 1)."""
    os.makedirs(LIVE, exist_ok=True)
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    want = sorted({x["cik"] for x in C.values() if x["cik"]})
    n = 0
    for c in want:
        p = os.path.join(LIVE, f"{c}.json")
        if os.path.exists(p):
            continue
        s = ED.get(f"https://data.sec.gov/submissions/CIK{c:010d}.json")
        if s is not None:
            s["older"] = [ED.get(f"https://data.sec.gov/submissions/{f['name']}") for f in s.get("filings", {}).get("files", [])]
        json.dump(s, open(p, "w"))
        n += 1
    print(f"live submissions: {n} fetched, {len(want)} firms")


def items():
    """Every 8-K / 8-K/A with its items and EDGAR acceptance time (US Eastern), accepted by 2025-12-31."""
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    rows = []
    for c in sorted({x["cik"] for x in C.values() if x["cik"]}):
        p = os.path.join(LIVE, f"{c}.json")
        if not os.path.exists(p):
            continue
        s = json.load(open(p))
        if s is None:
            continue
        F = ED._filings(s)
        F = F[F["form"].isin(["8-K", "8-K/A"])]
        for r in F.itertuples():
            ts = et_from_api(r.acceptanceDateTime)         # the live API's time is UTC (Amendment 1)
            if ts <= LAST:
                rows.append({"cik": c, "accession": r.accessionNumber, "form": r.form, "items": str(r.items or ""),
                             "accepted_et": ts, "accepted_utc": pd.Timestamp(r.acceptanceDateTime[:19])})
    D = pd.DataFrame(rows)
    D.to_parquet(ITEMS)
    print(f"items8k: {len(D):,} filings from {D['cik'].nunique():,} firms -> {ITEMS}")
    return D


def live_202_time(E):
    """The Eastern acceptance time of each event's 8-K 2.02 from the live API: the filing of that firm whose live UTC
    time equals the bulk time, or is 4 or 5 hours earlier (to the second). NaT when none or several match."""
    D = pd.read_parquet(ITEMS)
    D = D[D["items"].str.contains("2.02", regex=False)]
    utc = {c: set(pd.to_datetime(g["accepted_utc"])) for c, g in D.groupby("cik")}
    et_of = dict(zip(zip(D["cik"], pd.to_datetime(D["accepted_utc"])), D["accepted_et"]))
    out = []
    for c, a in zip(E["cik"], pd.to_datetime(E["accepted_et"])):
        hits = [a - pd.Timedelta(hours=k) for k in (0, 4, 5) if (a - pd.Timedelta(hours=k)) in utc.get(c, set())]
        out.append(et_of[(c, hits[0])] if len(hits) == 1 else pd.NaT)
    return pd.Series(out, index=E.index)


def t0_info(acc, sessions):
    """The session an 8-K belongs to under the info-time rule: accepted before 15:40 ET on a session -> that session."""
    d = pd.Timestamp(acc.date())
    late = acc.hour * 60 + acc.minute >= 15 * 60 + 40
    i = sessions.searchsorted(d, side="right" if late else "left")
    return sessions[i] if i < len(sessions) else None


def fund_entry(info_et, sessions):
    """The fund's entry for news known at info_et (US Eastern): the first Wednesday whose 22:00 UTC desk cutoff is at
    or after it is the as-of; entry is the first session after that Wednesday."""
    t = pd.Timestamp(info_et).tz_localize("America/New_York")
    d = t.normalize()
    for k in range(0, 15):
        w = d + pd.Timedelta(days=k)
        if w.weekday() != 2:
            continue
        cut = pd.Timestamp(w.date()).tz_localize("UTC") + pd.Timedelta(hours=22)
        if cut >= t.tz_convert("UTC"):
            i = sessions.searchsorted(pd.Timestamp(w.date()), side="right")
            return sessions[i] if i < len(sessions) else None
    return None


def ticker_at(c, t0, by_cik, mem):
    names = sorted(by_cik.get(c, []))
    m = set(mem.loc[t0]) if t0 in mem.index and isinstance(mem.loc[t0], list) else set()
    inn = [t for t in names if t in m]
    return inn[0] if inn else None


def filing_events(kind, R):
    """E2 ('hard') or E3 ('soft') 8-K events: cik, ticker, accepted_et, t0, S&P 500 at t0."""
    D = pd.read_parquet(ITEMS)
    sessions = R.index
    its = D["items"].str.split(",").apply(lambda xs: {x.strip() for x in xs if x.strip()})
    has202 = its.apply(lambda s: "2.02" in s)
    if kind == "hard":
        sel = its.apply(lambda s: bool(s & HARD)) & ~has202
    else:
        sel = its.apply(lambda s: bool(s & SOFT) and not (s & HARD)) & ~has202
    rel = D[has202]
    rel_t0 = {}
    for r in rel.itertuples():
        t = t0_info(r.accepted_et, sessions)
        if t is not None:
            rel_t0.setdefault(r.cik, []).append(sessions.get_loc(t))
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    by_cik = {}
    for t, x in C.items():
        if x["cik"]:
            by_cik.setdefault(x["cik"], []).append(t)
    mem = PX.members(sessions)
    rows = []
    for r in D[sel].itertuples():
        t0 = t0_info(r.accepted_et, sessions)
        if t0 is None:
            continue
        i0 = sessions.get_loc(t0)
        if any(abs(i0 - j) <= 2 for j in rel_t0.get(r.cik, [])):
            continue
        tick = ticker_at(r.cik, t0, by_cik, mem)
        if tick is None or tick not in R:
            continue
        rows.append({"cik": r.cik, "ticker": tick, "accession": r.accession, "items": r.items,
                     "accepted_et": r.accepted_et, "t0": t0, "i0": i0})
    return pd.DataFrame(rows).sort_values(["ticker", "t0"]).drop_duplicates(["ticker", "t0"])


def first_per_window(E, h, col="i0"):
    keep, last = [], {}
    for r in E.sort_values(["ticker", col]).itertuples():
        j = getattr(r, col)
        if r.ticker in last and j - last[r.ticker] < h:
            continue
        last[r.ticker] = j
        keep.append(r.Index)
    return E.loc[keep]


def resid_sum(R, t, i_from, n, beta_idx):
    """Sum of e over the n sessions after position i_from (exclusive), beta fixed before beta_idx; NaN if incomplete."""
    b = RS.betas(R, t, beta_idx)
    if b is None or i_from + n >= len(R.index):
        return np.nan, None
    w = R.iloc[i_from + 1: i_from + n + 1]
    e = w[t] - b[0] * w["SPY"]
    return (float(e.sum()) if e.notna().all() else np.nan), R.index[i_from + n]


def day0(R, t, i0):
    b = RS.betas(R, t, i0)
    if b is None:
        return np.nan
    v = R[t].iloc[i0] - b[0] * R["SPY"].iloc[i0]
    return float(v) if np.isfinite(v) else np.nan


def week_t(y, dates):
    """Mean and its CR1 t clustered by calendar week (descriptive in the dry fit)."""
    y = pd.Series(np.asarray(y, float)); w = pd.Series(pd.to_datetime(np.asarray(dates))).dt.strftime("%G-%V")
    ok = y.notna()
    y, w = y[ok], w[ok]
    m, G = y.mean(), w.nunique()
    sc = (y - m).groupby(w.values).sum()
    se = np.sqrt(G / (G - 1) * (sc ** 2).sum()) / len(y) if G > 1 else np.nan
    return float(m), float(m / se) if se and se > 0 else np.nan, int(len(y)), int(G)


def e1_fit(R):
    E = pd.read_parquet(os.path.join(PX.CACHE, "events.parquet"))
    sessions = R.index
    # Amendment 1: events.parquet's times come from SEC's bulk file. Each event takes the live-API time of its firm's
    # 8-K 2.02 that the bulk time encodes (equal, or 4 or 5 hours later), and t0 is recomputed (16:00 rule).
    E["et"] = live_202_time(E)
    E = E[E["et"].notna()].copy()
    E["t0"] = E["et"].map(lambda a: EV.t0_of(a, sessions))
    E = E[E["t0"].notna()]
    E["season"] = pd.to_datetime(E["t0"]).dt.to_period("Q").astype(str)
    E = E[(E["universe"] == "sp500") & (E["t0"] >= FIT0) & (E["t0"] <= FIT1) & E["sue"].notna()]
    out = {}
    for entry, h in E1_GRID:
        rows = []
        for r in first_per_window(E.assign(i0=E["t0"].map(lambda d: sessions.get_loc(d) if d in sessions else -1)), h).itertuples():
            if r.i0 < 0 or r.ticker not in R:
                continue
            i_e = r.i0 + (0 if entry == "t0" else 1)
            D, end = resid_sum(R, r.ticker, i_e, h, r.i0 - 1)
            if end is None or end > FIT1 or not np.isfinite(D):
                continue
            rows.append({"season": r.season, "sector": r.sector, "sue": r.sue, "D": D})
        X = pd.DataFrame(rows)
        ics = X.groupby("season").apply(lambda g: g["sue"].rank().corr(g["D"].rank()) if len(g) >= 20 else np.nan).dropna()
        t = float(ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics))) if len(ics) > 2 else np.nan
        q = X["sue"].rank(pct=True)
        S = (X.loc[q > 2 / 3, "D"].mean() - X.loc[q <= 1 / 3, "D"].mean()) * 1e4
        out[f"{entry}|{h}"] = {"entry": entry, "h": h, "n": int(len(X)), "seasons": int(len(ics)), "ic": float(ics.mean()),
                               "ic_t": t, "tercile_spread_bp": float(S), "net_live_bp": float(S - 2 * C_LIVE),
                               "net_stress_bp": float(S - 2 * C_STRESS)}
    best = max(out.values(), key=lambda x: (x["ic_t"], -x["h"], x["entry"] == "t0"))
    return out, best


def e2_fit(R, E2):
    out = {}
    for h in E2_GRID:
        rows = []
        for r in first_per_window(E2[(E2["t0"] >= FIT0) & (E2["t0"] <= FIT1)], h).itertuples():
            d = np.sign(day0(R, r.ticker, r.i0))
            if not d:
                continue
            s, end = resid_sum(R, r.ticker, r.i0 + 1, h, r.i0 - 1)
            if end is None or end > FIT1 or not np.isfinite(s):
                continue
            rows.append({"y": d * s, "t0": r.t0})
        X = pd.DataFrame(rows)
        m, t, n, G = week_t(X["y"], X["t0"])
        out[str(h)] = {"h": h, "n": n, "weeks": G, "mean_bp": m * 1e4, "t": t, "net_live_bp": m * 1e4 - C_LIVE,
                       "net_stress_bp": m * 1e4 - C_STRESS}
    best = max(out.values(), key=lambda x: (x["t"], -x["h"]))
    return out, best


def e3_fit(R, E3):
    rows = []
    sessions = R.index
    for r in first_per_window(E3[(E3["t0"] >= FIT0) & (E3["t0"] <= FIT1)], 5).itertuples():
        d = np.sign(day0(R, r.ticker, r.i0))
        ent = fund_entry(r.accepted_et, sessions)
        if not d or ent is None:
            continue
        s, end = resid_sum(R, r.ticker, sessions.get_loc(ent), 5, r.i0 - 1)
        if end is None or end > FIT1 or not np.isfinite(s):
            continue
        rows.append({"y": d * s, "t0": r.t0, "items": r.items})
    X = pd.DataFrame(rows)
    m, t, n, G = week_t(X["y"], X["t0"])
    by = {}
    for it in ("5.02", "1.01"):
        Y = X[X["items"].str.contains(it, regex=False)]
        mm, tt, nn, gg = week_t(Y["y"], Y["t0"])
        by[it] = {"n": nn, "mean_bp": mm * 1e4, "t": tt}
    return {"n": n, "weeks": G, "mean_bp": m * 1e4, "t": t, "by_item": by,
            "note": "descriptive: rule A has no free parameter; the decision read is the locked holdout"}


def dry_fit():
    R = returns_2016()
    if R.index.max() > LAST:
        raise SystemExit("the price panel reaches past 2025: the dry fit must not load validation-plus data")
    E1, b1 = e1_fit(R)
    E2all = filing_events("hard", R)
    E3all = filing_events("soft", R)
    E2, b2 = e2_fit(R, E2all)
    E3 = e3_fit(R, E3all)
    rep = {"written": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fit": [str(FIT0.date()), str(FIT1.date())],
           "E1": {"grid": E1, "chosen": b1}, "E2": {"grid": E2, "chosen": b2}, "E3": E3,
           "events_total": {"E2_hard_8k_all_years": int(len(E2all)), "E3_soft_8k_all_years": int(len(E3all))}}
    os.makedirs(PX.OUT, exist_ok=True)
    json.dump(rep, open(os.path.join(PX.OUT, "E_DRY_FIT.json"), "w"), indent=1)
    L = ["# Family E dry fit (2016-2021; selection only, no lock)", "",
         "Rule (PREREG_family_E.md §4): E1 picks the cell with the highest season-level IC t; E2 the h with the highest t "
         "of mean y; ties to the shorter h. Validation and sealed data are not loaded.", "",
         "## E1 earnings_post (SUE)", "", "| entry | h | n | seasons | IC | IC t | tercile spread bp | net live | net stress |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {x['entry']} | {x['h']} | {x['n']} | {x['seasons']} | {x['ic']:+.4f} | {x['ic_t']:+.2f} | {x['tercile_spread_bp']:+.1f} | "
          f"{x['net_live_bp']:+.1f} | {x['net_stress_bp']:+.1f} |" for x in E1.values()]
    L += ["", f"**Chosen: entry {b1['entry']}, h {b1['h']}.**", "", "## E2 news_8k (hard items, direction of day 0)", "",
          "| h | n | weeks | mean bp | t | net live | net stress |", "|---:|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {x['h']} | {x['n']} | {x['weeks']} | {x['mean_bp']:+.1f} | {x['t']:+.2f} | {x['net_live_bp']:+.1f} | {x['net_stress_bp']:+.1f} |"
          for x in E2.values()]
    L += ["", f"**Chosen: h {b2['h']}.**", "", "## E3 soft 8-K (items 5.02, 1.01), the fund's entry, 5 sessions (descriptive)", "",
          f"n {E3['n']}, weeks {E3['weeks']}, mean {E3['mean_bp']:+.1f} bp, t {E3['t']:+.2f}; "
          + "; ".join(f"item {k}: n {v['n']}, mean {v['mean_bp']:+.1f} bp, t {v['t']:+.2f}" for k, v in E3["by_item"].items()),
          "", "The E3 decision is the locked holdout read (rule A); this fit line only checks the pipeline."]
    open(os.path.join(PX.OUT, "E_DRY_FIT.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ======================================================================= the validation read (§5 rule B, steps 1-3)
V0, V1 = pd.Timestamp("2022-01-01"), pd.Timestamp("2025-12-31")
VHALVES = ((pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31")), (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-12-31")))
FHALVES = ((pd.Timestamp("2016-01-01"), pd.Timestamp("2018-12-31")), (pd.Timestamp("2019-01-01"), pd.Timestamp("2021-12-31")))
N_BEFORE = 34                                     # hypotheses read on 2022-2025 before Family E (DATA_USE.md)
LOCK = os.path.join(PX.OUT, "E_VALIDATION.lock")


def gics_of():
    return json.load(open(os.path.join(PX.CACHE, "gics.json")))["firms"]


def e1_rows(R, a, b, entry, h):
    E = pd.read_parquet(os.path.join(PX.CACHE, "events.parquet"))
    sessions = R.index
    E["et"] = live_202_time(E)
    E = E[E["et"].notna()].copy()
    E["t0"] = E["et"].map(lambda x: EV.t0_of(x, sessions))
    E = E[E["t0"].notna() & (E["universe"] == "sp500") & E["sue"].notna()]
    E = E[(E["t0"] >= a) & (E["t0"] <= b)].copy()
    E["season"] = pd.to_datetime(E["t0"]).dt.to_period("Q").astype(str)
    E["i0"] = E["t0"].map(lambda d: sessions.get_loc(d) if d in sessions else -1)
    rows = []
    for r in first_per_window(E[E["i0"] >= 0], h).itertuples():
        if r.ticker not in R:
            continue
        D, end = resid_sum(R, r.ticker, r.i0 + (0 if entry == "t0" else 1), h, r.i0 - 1)
        if end is None or end > b or not np.isfinite(D):
            continue
        rows.append({"t0": r.t0, "season": r.season, "sector": r.sector, "industry": r.industry, "sue": r.sue, "D": D})
    X = pd.DataFrame(rows)
    # names without a current GICS code (mostly delisted; kept by the survivorship-free prices) share one "NA"
    # sector cell and one "NA" industry cluster: fixed before the read, the conservative choice for clustering
    X["sector"], X["industry"] = X["sector"].fillna("NA"), X["industry"].fillna("NA").astype(str)
    X["cell"] = X["season"] + "|" + X["sector"]
    g = X.groupby("cell")["sue"]
    X["z"] = (X["sue"] - g.transform("mean")) / g.transform("std")
    return X[X["z"].notna()]


def cr1_month(y, s, cell, month, direction=1):
    """Slope of y on s with cell fixed effects, CR1 clustered by calendar month; one-sided p from t(G-1)."""
    d = pd.DataFrame({"y": y, "s": s, "c": cell, "m": month})
    yt = d["y"] - d.groupby("c")["y"].transform("mean")
    st = d["s"] - d.groupby("c")["s"].transform("mean")
    D = float(st @ st)
    b = float(st @ yt) / D
    e = yt - b * st
    sc = (st * e).groupby(d["m"]).sum()
    G, N, C = sc.size, len(d), d["c"].nunique()
    V = G / (G - 1) * (N - 1) / (N - 1 - C) * float(sc @ sc) / D ** 2
    t = b / np.sqrt(V)
    return float(t), float(I.stats.t.sf(direction * t, G - 1))


def e1_read(R, a, b, halves, entry, h, B):
    X = e1_rows(R, a, b, entry, h)
    ev = I.event_test(X["D"].values, X["z"].values, X["cell"].values, X["industry"].values, direction=1, B=B)
    t_m, p_m = cr1_month(X["D"].values, X["z"].values, X["cell"].values, pd.to_datetime(X["t0"]).dt.strftime("%Y-%m").values)
    half = []
    for lo, hi in halves:
        Y = X[(X["t0"] >= lo) & (X["t0"] <= hi)]
        st = Y["z"] - Y.groupby("cell")["z"].transform("mean")
        yt = Y["D"] - Y.groupby("cell")["D"].transform("mean")
        half.append(float(st @ yt / (st @ st)))
    ics = X.groupby("season").apply(lambda g: g["sue"].rank().corr(g["D"].rank()) if len(g) >= 20 else np.nan).dropna()
    q = X["sue"].rank(pct=True)
    S = (X.loc[q > 2 / 3, "D"].mean() - X.loc[q <= 1 / 3, "D"].mean()) * 1e4
    return {"n": int(len(X)), "n_no_gics": int((X["industry"] == "NA").sum()), "beta_bp_per_sd": ev["beta"] * 1e4, "t": ev["t"], "p_wild": ev["p_wild"], "p_ri": ev["p_ri"],
            "t_month": t_m, "p_cr1_month": p_m, "p": max(ev["p_wild"], ev["p_ri"], p_m), "half_betas_bp": [x * 1e4 for x in half],
            "half_signs_ok": all(x > 0 for x in half), "ic": float(ics.mean()), "ic_seasons": int(len(ics)),
            "tercile_spread_bp": float(S), "net_live_bp": float(S - 2 * C_LIVE), "net_stress_bp": float(S - 2 * C_STRESS),
            "economic_ok": bool(S - 2 * C_LIVE > C_LIVE and S - 2 * C_STRESS >= 0)}


def e2_read(R, a, b, halves, h, B):
    E2 = filing_events("hard", R)
    gi = gics_of()
    rows = []
    for r in first_per_window(E2[(E2["t0"] >= a) & (E2["t0"] <= b)], h).itertuples():
        d = np.sign(day0(R, r.ticker, r.i0))
        if not d:
            continue
        s_, end = resid_sum(R, r.ticker, r.i0 + 1, h, r.i0 - 1)
        if end is None or end > b or not np.isfinite(s_):
            continue
        rows.append({"y": d * s_, "t0": r.t0, "industry": (gi.get(r.ticker) or {}).get("industry_code", "NA")})
    X = pd.DataFrame(rows)
    mt = I.mean_test(X["y"].values, pd.to_datetime(X["t0"]).dt.strftime("%G-%V").values, X["industry"].values, B=B)
    half = [float(X.loc[(X["t0"] >= lo) & (X["t0"] <= hi), "y"].mean()) for lo, hi in halves]
    m = mt["mean"] * 1e4
    return {"n": mt["n"], "mean_bp": m, "t_week": mt["t_week"], "t_two_way": mt["t_two_way"], "p": mt["p"],
            "p_parts": mt["p_parts"], "half_means_bp": [x * 1e4 for x in half], "half_signs_ok": all(x > 0 for x in half),
            "net_live_bp": m - C_LIVE, "net_stress_bp": m - C_STRESS,
            "economic_ok": bool(m - C_LIVE > C_LIVE and m - C_STRESS >= 0)}


def read(a, b, halves, B):
    fit = json.load(open(os.path.join(PX.OUT, "E_DRY_FIT.json")))
    c1, c2 = fit["E1"]["chosen"], fit["E2"]["chosen"]
    R = returns_2016()
    out = {"E1": {"cell": {"entry": c1["entry"], "h": c1["h"]}, **e1_read(R, a, b, halves, c1["entry"], c1["h"], B)},
           "E2": {"cell": {"h": c2["h"]}, **e2_read(R, a, b, halves, c2["h"], B)}}
    adj, ok = I.holm([out["E1"]["p"], out["E2"]["p"]])
    for k, ad, o in zip(("E1", "E2"), adj, ok):
        out[k].update(p_holm=float(ad), bonferroni_all_reads=float(min(1.0, out[k]["p"] * (N_BEFORE + 2))),
                      passes=bool(o and out[k]["half_signs_ok"] and out[k]["economic_ok"]))
    return out


def rehearse():
    out = read(FIT0, FIT1, FHALVES, B=199)
    print(json.dumps({k: {x: v[x] for x in ("n", "p", "half_signs_ok", "economic_ok", "passes")} for k, v in out.items()}, indent=1))
    print("rehearsal on the fit sample only: no lock, nothing written")


def validate():
    if os.path.exists(LOCK):
        raise SystemExit(f"{LOCK} exists: the validation read has been made")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    open(LOCK, "w").write(f"{datetime.now(timezone.utc).isoformat()} commit {commit}\n")
    out = read(V0, V1, VHALVES, B=9999)
    out["lock"] = open(LOCK).read().strip()
    json.dump(out, open(os.path.join(PX.OUT, "E_VALIDATION.json"), "w"), indent=1)
    L = ["# Family E validation read (2022-2025, once)", "", f"Lock: {out['lock']}", "",
         "Rule B (PREREG_family_E.md §5): Holm p <= 0.05 over E1 and E2; the registered sign in 2022-23 and in 2024-25; "
         "net per event at the live cost above the 4 bp margin and >= 0 at the 20 bp stress. A passing module then goes "
         "to the sealed 2026 check.", "",
         "| module | n | effect | p (max of tests) | Holm p | halves | net live bp | net stress bp | passes |", "|---|---:|---|---:|---:|---|---:|---:|---|"]
    e1, e2 = out["E1"], out["E2"]
    L.append(f"| E1 earnings_post (t0+1, h {e1['cell']['h']}) | {e1['n']} | slope {e1['beta_bp_per_sd']:+.1f} bp/sd, IC {e1['ic']:+.4f} | "
             f"{e1['p']:.4f} | {e1['p_holm']:.4f} | {'ok' if e1['half_signs_ok'] else 'no'} {[round(x, 1) for x in e1['half_betas_bp']]} | "
             f"{e1['net_live_bp']:+.1f} | {e1['net_stress_bp']:+.1f} | **{'PASS' if e1['passes'] else 'no'}** |")
    L.append(f"| E2 news_8k (h {e2['cell']['h']}) | {e2['n']} | mean {e2['mean_bp']:+.1f} bp | {e2['p']:.4f} | {e2['p_holm']:.4f} | "
             f"{'ok' if e2['half_signs_ok'] else 'no'} {[round(x, 1) for x in e2['half_means_bp']]} | {e2['net_live_bp']:+.1f} | "
             f"{e2['net_stress_bp']:+.1f} | **{'PASS' if e2['passes'] else 'no'}** |")
    L += ["", f"Diagnostic: Bonferroni over every hypothesis read on 2022-2025 ({N_BEFORE} before + 2): "
          f"E1 {e1['bonferroni_all_reads']:.4f}, E2 {e2['bonferroni_all_reads']:.4f}.",
          f"E1 tests: wild (industry) {e1['p_wild']:.4f}, randomisation {e1['p_ri']:.4f}, CR1 (month) {e1['p_cr1_month']:.4f}. "
          f"E2 tests: {', '.join(f'{k} {v:.4f}' for k, v in e2['p_parts'].items())}."]
    open(os.path.join(PX.OUT, "E_VALIDATION.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    {"live": live, "items": items, "dry-fit": dry_fit, "rehearse": rehearse, "validate": validate}[sys.argv[1]]()
