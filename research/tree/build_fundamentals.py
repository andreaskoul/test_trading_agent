"""Phase 2, N1 data: point-in-time fundamentals aligned to the development panel (.cache/tree/extra_fundamentals.npz).

Source: SEC XBRL company facts (.cache/tree/sec/, fetched 2026-11-12). Point in time: a value is known from the session
after the FIRST filing that reported it (later amendments ignored); only filings dated on or before 2019-12-31 are read.
Annual flows: facts with a 350-380 day duration from 10-K filings; stocks: instant facts. For each concept and each
session: the latest annual value known ("_0") and the one before it ("_1"); for stocks, the value at the latest
fiscal-year end known and one year before. Plus the latest standardised earnings surprise (SUE) from the P8 events
file, known from its reaction session. Names are matched to CIKs by ticker in the events file.
"""
import glob
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import harness as H  # noqa: E402

EV = "/Users/apollogodofthesun/test_trading_agent/.claude/worktrees/riskfield/.cache/p8/events.parquet"
FULL = os.environ.get("FUND_FULL") == "1"            # holdout read (PREREG phase 2, Amendment 2): full panel, filings to 2025
CUT = pd.Timestamp("2025-12-31" if FULL else "2019-12-31")
FLOWS = {"revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
         "gross_profit": ["GrossProfit"], "operating_income": ["OperatingIncomeLoss"], "net_income": ["NetIncomeLoss"],
         "cfo": ["NetCashProvidedByUsedInOperatingActivities"], "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
         "rnd": ["ResearchAndDevelopmentExpense"], "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
         "buybacks": ["PaymentsForRepurchaseOfCommonStock"]}
STOCKS = {"assets": ["Assets"], "equity": ["StockholdersEquity"], "liabilities": ["Liabilities"],
          "cash": ["CashAndCashEquivalentsAtCarryingValue"], "debt_lt": ["LongTermDebt", "LongTermDebtNoncurrent"],
          "shares": ["CommonStockSharesOutstanding"]}


def first_filed(facts, annual):
    """{period end: (filed date, value)} keeping the first filing that reported each period end."""
    out = {}
    for f in facts:
        if f.get("form") not in ("10-K", "10-K405", "10-KT") and annual:
            continue
        filed = pd.Timestamp(f["filed"])
        if filed > CUT:
            continue
        end = pd.Timestamp(f["end"])
        if annual:
            if "start" not in f:
                continue
            dur = (end - pd.Timestamp(f["start"])).days
            if not 350 <= dur <= 380:
                continue
        elif f.get("fp") != "FY" and f.get("form") not in ("10-K", "10-K405", "10-KT"):
            continue                                     # stocks: fiscal-year-end balance sheets only
        if end not in out or filed < out[end][0]:
            out[end] = (filed, float(f["val"]))
    return out


def series(facts_by_tag, tags, annual):
    best = {}
    for t in tags:                                       # each period end is dated by its earliest filing under any tag
        for end, v in first_filed(facts_by_tag.get(t, []), annual).items():
            if end not in best or v[0] < best[end][0]:
                best[end] = v
    return sorted((v[0], end, v[1]) for end, v in best.items())   # (filed, end, value)


def main():
    if FULL:
        import holdout as HO
        D = HO.full_panel()
    else:
        D = H.load()
    S, names = D["S"], D["names"]
    ev = pd.read_parquet(EV)
    tick2cik = ev.dropna(subset=["cik"]).groupby("ticker").cik.last().astype(int).to_dict()
    concepts = list(FLOWS) + list(STOCKS)
    A = {f"{c}_{k}": np.full((len(S), len(names)), np.nan, np.float32) for c in concepts for k in (0, 1)}
    have = 0
    for j, n in enumerate(names):
        c = tick2cik.get(n)
        p = os.path.join(ROOT, ".cache", "tree", "sec", f"{c:010d}.json.gz") if c else None
        if not p or not os.path.exists(p):
            continue
        g = json.loads(gzip.decompress(open(p, "rb").read())).get("facts", {}).get("us-gaap", {})
        byt = {t: [u for unit in g[t]["units"].values() for u in unit] for t in g}
        have += 1
        for cname, tags in list(FLOWS.items()) + list(STOCKS.items()):
            sr = series(byt, tags, cname in FLOWS)
            if not sr:
                continue
            known = []                                   # periods known so far, by end date
            k = 0
            for i, d in enumerate(S):
                while k < len(sr) and sr[k][0] < d:      # filed before session d: usable at d
                    known.append((sr[k][1], sr[k][2])); k += 1
                if known:
                    ks = sorted(known)
                    A[f"{cname}_0"][i, j] = ks[-1][1]
                    if len(ks) > 1:
                        A[f"{cname}_1"][i, j] = ks[-2][1]
    # earnings surprise: latest SUE known from its reaction session
    sue = np.full((len(S), len(names)), np.nan, np.float32)
    e = ev[(ev.universe == "sp500") & (ev.t0 <= CUT) & ev.sue.notna()]
    ix = pd.Index(names)
    for t, g in e.groupby("ticker"):
        j = ix.get_indexer([t])[0]
        if j < 0:
            continue
        pos = S.searchsorted(pd.DatetimeIndex(g.t0.sort_values()))
        vals = g.sort_values("t0").sue.to_numpy()
        for a, b, v in zip(pos, list(pos[1:]) + [len(S)], vals):
            sue[a:b, j] = v
    A["sue"] = sue
    elig = D["elig"]
    cov = {k: float(np.isfinite(v)[elig & (S.year >= 2013)[:, None]].mean()) for k, v in A.items()}
    note = ("Point-in-time annual fundamentals from SEC XBRL company facts (first filing; filings <= 2019-12-31), "
            "aligned to dev.npz. <concept>_0 = latest fiscal year known at the session, _1 = the year before. Flows: "
            + ", ".join(FLOWS) + ". Stocks (fiscal-year-end): " + ", ".join(STOCKS) + ". 'sue' = latest standardised "
            "earnings surprise from its reaction session. Values in reported units (USD; shares in shares). "
            "Coverage of eligible name-days 2013-2019: " + json.dumps({k: round(v, 3) for k, v in cov.items()}))
    np.savez_compressed(os.path.join(ROOT, ".cache", "tree", "extra_fundamentals_full.npz" if FULL else "extra_fundamentals.npz"), note=np.array(note), **A)
    print(f"names matched to a CIK file: {have} of {len(names)}")
    print(json.dumps({k: round(v, 3) for k, v in cov.items()}))


if __name__ == "__main__":
    main()
