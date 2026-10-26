"""How long is earnings information priced? Decay curves on the P8 fit sample (2012-2021) only.

    python research/p8/decay_earnings.py     # -> reports/research/p8/decay_earnings.md

Descriptive evidence for the horizon question (owner, 2026-10-26: "some theses need more than a month"). It is
not one of the registered H tests and decides nothing; it reads only the fit sample (PREREG_thesis_tree.md §1),
so it cannot touch validation or the sealed window. Design fixed in this header before any data was read:

Events. Each quarterly diluted EPS (first-filed XBRL; Q4 derived per Amendment 4 D6) matched to the firm's first
  8-K item 2.02 accepted 1-100 days after the quarter end. t0 by §1: accepted before 09:30 ET or between 09:30 and
  16:00 -> that session (the next one if not a trading day); after 16:00 -> the next session. Kept if
  2012-01-01 <= t0 <= 2021-12-31. Universe: S&P 500 members at t0 (point in time), and the current S&P 400 list
  (survivorship stated), reported separately.
Signals. SUE = (EPS_q - EPS_q-4) / sd(EPS_q-k - EPS_q-k-4, k = 1..8), >= 6 of 8 differences, winsorised at +-10.
  CAR = sum of e over t0-1 .. t0+1 (the market's reaction). Both are known at t0+1's close: the release carries EPS.
Target. Drift D_h = sum of e over t0+2 .. t0+1+h, h in {1, 5, 10, 20, 40, 60, 90, 120} sessions: what a position
  opened after the reaction would earn.
Statistics. Per season (calendar quarter of t0): Spearman IC(signal, D_h). Reported: the mean IC over seasons with
  t = mean / (sd / sqrt(n seasons)), and the top-minus-bottom quintile mean D_h in bp. Rows: all fit years,
  2016-2021 (survivorship-free prices), 2012-2015 (yfinance, biased), and |SUE| top decile (large surprises).
Reading. A signal whose IC(h) keeps rising to h = 60-120 carries information the market prices slowly (a horizon
  of months). One that peaks by h = 5-20 and flattens or reverses is priced within weeks.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

H = [1, 5, 10, 20, 40, 60, 90, 120]
LO, HI = pd.Timestamp("2012-01-01"), pd.Timestamp("2021-12-31")


def t0_of(acc, sessions):
    d = pd.Timestamp(acc.date())
    after_close = acc.hour * 60 + acc.minute >= 16 * 60
    i = sessions.searchsorted(d, side="right" if after_close else "left")
    return sessions[i] if i < len(sessions) else None


def events(R):
    Q = pd.read_parquet(os.path.join(ED.CACHE, "eps_quarterly.parquet")).sort_values(["cik", "end"])
    rel = pd.read_parquet(os.path.join(ED.CACHE, "releases_202.parquet")).sort_values("accepted_et")
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    by_cik = {}
    for t, x in C.items():
        if x["cik"]:
            by_cik.setdefault(x["cik"], []).append(t)
    sessions = R.index
    mem = PX.members(sessions)
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    out = []
    for c, g in Q.groupby("cik"):
        g = g.set_index("end")["eps"]
        ends = list(g.index)
        rc = rel[rel["cik"] == c]["accepted_et"].values
        for j, e in enumerate(ends):
            def back(k):                                         # the quarter ~k quarters before e
                tgt = e - pd.Timedelta(days=91 * k)
                m = [x for x in ends if abs((x - tgt).days) <= 20]
                return g[m[0]] if m else np.nan
            d = [back(k) - back(k + 4) for k in range(1, 9)]
            d = [x for x in d if not np.isnan(x)]
            cur = g[e] - back(4)
            if np.isnan(cur) or len(d) < 6 or np.std(d, ddof=1) <= 0:
                continue
            sue = float(np.clip(cur / np.std(d, ddof=1), -10, 10))
            acc = [pd.Timestamp(a) for a in rc if e + pd.Timedelta(days=1) <= pd.Timestamp(a) <= e + pd.Timedelta(days=100)]
            if not acc:
                continue
            t0 = t0_of(min(acc), sessions)
            if t0 is None or not (LO <= t0 <= HI):
                continue
            names = by_cik.get(c, [])
            members_t0 = set(mem.loc[t0]) if t0 in mem.index and isinstance(mem.loc[t0], list) else set()
            in500 = [t for t in names if t in members_t0 and t in R.columns]
            in400 = [t for t in names if t in sp400 and t in R.columns]
            tick, uni = (sorted(in500)[0], "sp500") if in500 else ((sorted(in400)[0], "sp400") if in400 else (None, None))
            if tick is None:
                continue
            out.append({"cik": c, "ticker": tick, "universe": uni, "t0": t0, "sue": sue})
    return pd.DataFrame(out)


def run():
    R = RS.returns()
    E = events(R)
    rows = []
    idx = {d: i for i, d in enumerate(R.index)}
    for r in E.itertuples():
        i0 = idx[r.t0]
        if i0 + 121 >= len(R):
            continue
        e, kind = RS.residual_path(R, r.ticker, i0)
        if e is None or np.isnan(e[:3]).any():
            continue
        car = float(np.nansum(e[0:3]))                            # t0-1 .. t0+1
        post = e[3:]                                              # t0+2 ..
        rec = {"ticker": r.ticker, "universe": r.universe, "t0": r.t0, "sue": r.sue, "car": car, "resid": kind}
        for h in H:
            seg = post[:h]
            rec[f"d{h}"] = float(np.nansum(seg)) if np.isfinite(seg).sum() >= 0.8 * h else np.nan
        rows.append(rec)
    D = pd.DataFrame(rows)
    D["season"] = D["t0"].dt.to_period("Q")
    D.to_parquet(os.path.join(PX.CACHE, "decay_earnings_events.parquet"))
    return D


def table(D, sig):
    out = []
    for h in H:
        ics, spr = [], []
        for _, g in D.groupby("season"):
            g = g.dropna(subset=[sig, f"d{h}"])
            if len(g) < 30:
                continue
            ics.append(g[sig].rank().corr(g[f"d{h}"].rank()))
            q = pd.qcut(g[sig].rank(method="first"), 5, labels=False)
            spr.append(g[f"d{h}"][q == 4].mean() - g[f"d{h}"][q == 0].mean())
        ics, spr = np.array(ics), np.array(spr)
        n = len(ics)
        out.append((h, ics.mean(), ics.mean() / (ics.std(ddof=1) / np.sqrt(n)) if n > 2 else np.nan,
                    spr.mean() * 1e4, n))
    return out


def report(D):
    L = ["# How long is earnings information priced? (P8 fit sample 2012-2021, descriptive)", "",
         "Design and reading rule: `research/p8/decay_earnings.py` header, fixed before any data was read.",
         "D_h = residual return from t0+2 to t0+1+h (after the 3-day reaction). IC = Spearman per season, averaged; "
         "t over seasons. Q5-Q1 = top minus bottom quintile mean D_h, bp.", "",
         f"Events: {len(D):,} ({(D['universe'] == 'sp500').sum():,} S&P 500 point in time, "
         f"{(D['universe'] == 'sp400').sum():,} S&P 400 current list); seasons {D['season'].nunique()}; "
         f"market-only residuals {(D['resid'] == 'market_only').mean():.0%}.", ""]
    big = D["sue"].abs() >= D["sue"].abs().quantile(0.9)
    cuts = [("S&P 500, all fit years", D[D.universe == "sp500"]),
            ("S&P 500, 2016-2021 (survivorship-free prices)", D[(D.universe == "sp500") & (D.t0 >= "2016-01-04")]),
            ("S&P 500, 2012-2015 (yfinance, survivorship-biased)", D[(D.universe == "sp500") & (D.t0 < "2016-01-04")]),
            ("S&P 400 (current list, survivorship-biased)", D[D.universe == "sp400"]),
            ("All, large surprises (top decile |SUE|)", D[big])]
    for sig, name in (("sue", "SUE (the surprise)"), ("car", "CAR (the market's 3-day reaction)")):
        L += [f"## Signal: {name}", ""]
        for title, g in cuts:
            if len(g) < 200:
                continue
            L += [f"**{title}** (n = {len(g):,})", "", "| h | IC | t | Q5-Q1 bp | seasons |", "|---|---|---|---|---|"]
            for h, ic, t, s, n in table(g, sig):
                L.append(f"| {h} | {ic:+.4f} | {t:+.2f} | {s:+.1f} | {n} |")
            L.append("")
    open(os.path.join(PX.OUT, "decay_earnings.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    report(run())
