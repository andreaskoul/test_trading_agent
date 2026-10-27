"""H2 link momentum (PREREG_thesis_tree.md §4; gates and definitions: Amendment 5 C).

    python research/p8/h2.py links     # named >= 10% customers from 10-K text -> .cache/p8/h2_links.parquet
    python research/p8/h2.py sample    # S2 contract: 200 random supplier firm-years with a link, for checking
    python research/p8/h2.py gate      # power gate: S&P 400 suppliers per year with a named S&P 500 customer
    python research/p8/h2.py build     # (only if both gates pass) month x supplier rows
    python research/p8/h2.py fit       # fit-sample FM (also the customer-momentum replication check)

Links. In a supplier's 10-K, a sentence that states a share of revenue >= 10% for a customer: it contains a
percentage >= 10, a revenue word (revenue, sales) and a customer cue (customer, accounted for, represented,
comprised). Candidate names are the capitalised word sequences (1-6 tokens) of that sentence. A candidate is a link
only if its normalised form equals the normalised current or former SEC registrant name of a universe CIK
(submissions `name`, `formerNames`): lower-cased, '&' -> 'and', punctuation removed, a leading 'the' and trailing
legal suffixes (inc, incorporated, corp, corporation, co, company, ltd, limited, plc, llc, lp) dropped. No fuzzy
matching. A supplier's own name is never its customer.
Signal for supplier i in month m: mean e_{c,m} over i's customers c named in its latest 10-K filed on or before
the end of m (customers must be S&P 500 members at the month's last session). Target: e_{i,m+1}.
Primary arm (registered): S&P 400 suppliers with >= 1 named S&P 500 customer; run only if >= 100 such suppliers
per year on average, and S2 precision >= 0.9 on 200 randomly drawn firm-years.
"""
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import inference as I                                            # noqa: E402
import monthly as MO                                             # noqa: E402
import prices as PX                                              # noqa: E402
import sections as SE                                            # noqa: E402
import text as TX                                                # noqa: E402

LINKS = os.path.join(PX.CACHE, "h2_links.parquet")
ROWS = os.path.join(PX.CACHE, "h2_rows.parquet")
SUFFIX = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "llc", "lp"}
PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?(?:%|percent\b)")
CAP = re.compile(r"(?:[A-Z][A-Za-z0-9&'\.\-]*)(?:\s+(?:[A-Z][A-Za-z0-9&'\.\-]*|&|of|and)){0,5}")


def norm(name):
    x = name.lower().replace("&", " and ")
    x = re.sub(r"[^a-z0-9 ]", " ", x).split()
    if x and x[0] == "the":
        x = x[1:]
    while x and x[-1] in SUFFIX:
        x = x[:-1]
    return " ".join(x)


def name_index():
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    idx = {}
    for c in sorted({x["cik"] for x in C.values() if x["cik"]}):
        s = json.load(open(os.path.join(ED.CACHE, "submissions", f"{c}.json")))
        if s is None:
            continue
        for nm in [s.get("name")] + [f.get("name") for f in s.get("formerNames", [])]:
            k = norm(nm or "")
            if len(k) >= 3:
                idx.setdefault(k, set()).add(c)
    return {k: v for k, v in idx.items() if len(v) == 1}       # a name shared by two registrants is not a link


_IDX = None


def links_of(f):
    global _IDX
    if _IDX is None:
        _IDX = name_index()
    t = SE.load(f["cik"], f["accession"])
    if t is None:
        return []
    out = []
    for sent in re.split(r"(?<=[\.;])\s+(?=[A-Z])|\n", t):
        if len(sent) > 600 or not re.search(r"\b(revenue|revenues|sales)\b", sent, re.I):
            continue
        if not re.search(r"\b(customer|customers|accounted for|represented|comprised)\b", sent, re.I):
            continue
        if not any(10 <= float(p) <= 100 for p in PCT.findall(sent)):
            continue
        for m in CAP.finditer(sent):
            words = m.group(0).split()
            for i in range(len(words)):
                for j in range(i + 1, min(len(words), i + 6) + 1):
                    c = _IDX.get(norm(" ".join(words[i:j])))
                    if c and next(iter(c)) != f["cik"]:
                        out.append({"supplier": f["cik"], "accession": f["accession"], "filed": f["filed"],
                                    "customer": next(iter(c)), "name": " ".join(words[i:j]), "sentence": sent.strip()[:600]})
    return out


def links():
    F = [f for f in TX.filings() if f["form"] == "10-K"]
    out = []
    with ProcessPoolExecutor(6) as ex:
        for rows in ex.map(links_of, F, chunksize=20):
            out += rows
    L = pd.DataFrame(out).drop_duplicates(["supplier", "accession", "customer"])
    L["filed"] = pd.to_datetime(L["filed"])
    L.to_parquet(LINKS)
    print(f"{len(L):,} links from {L['accession'].nunique():,} 10-Ks of {L['supplier'].nunique()} suppliers")


def sample(n=200, seed=20261027):
    L = pd.read_parquet(LINKS)
    L["year"] = L["filed"].dt.year
    fy = L.drop_duplicates(["supplier", "year"])[["supplier", "year"]]
    pick = fy.sample(n=min(n, len(fy)), random_state=seed)
    S = L.merge(pick, on=["supplier", "year"])
    out = os.path.join(PX.OUT, "h2_s2_sample.jsonl")
    with open(out, "w") as h:
        for r in S.itertuples():
            h.write(json.dumps({"supplier": int(r.supplier), "year": int(r.year), "customer": int(r.customer),
                                "name": r.name, "sentence": r.sentence}) + "\n")
    print(f"{len(S)} links in {len(pick)} firm-years written to {out}")


def gate():
    L = pd.read_parquet(LINKS)
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    c400 = {x["cik"] for t, x in C.items() if t in sp400 and x["cik"]}
    m = PX.members()
    rows = []
    for y in range(2012, 2026):
        mem = {t for d, ts in m[m.index.year == y].items() for t in ts}
        c500 = {C[t]["cik"] for t in mem if t in C and C[t]["cik"]}
        x = L[(L["filed"].dt.year == y) & L["supplier"].isin(c400) & L["customer"].isin(c500)]
        rows.append((y, x["supplier"].nunique()))
    for y, k in rows:
        print(y, k)
    avg = np.mean([k for _, k in rows])
    print(f"average S&P 400 suppliers per year with a named S&P 500 customer: {avg:.1f} (gate: >= 100)")
    return avg


def build():
    """Month x supplier rows (registered arm: S&P 400 suppliers; customers S&P 500 members at the month's last
    session). Signal: mean e_{c,m} over the customers named in the supplier's latest 10-K filed by the end of m."""
    L = pd.read_parquet(LINKS).sort_values("filed")
    Em = pd.read_parquet(MO.OUT)
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    tick = {}
    for t, x in C.items():
        if x["cik"]:
            tick.setdefault(x["cik"], []).append(t)
    sessions = pd.DatetimeIndex(pd.read_parquet(os.path.join(PX.CACHE, "alpaca_bars.parquet"))["date"].unique()).union(
        pd.read_parquet(os.path.join(PX.CACHE, "yf_sp500_close.parquet")).index)
    mem = PX.members(sessions)
    months = list(Em.index)
    rows = []
    for a, m in enumerate(months[:-1]):
        end = pd.Period(m).end_time.normalize()
        last = mem.index[mem.index <= end]
        if not len(last):
            continue
        m500 = set(mem.loc[last[-1]])
        latest = L[L["filed"] <= end]
        latest = latest[latest["accession"].isin(latest.groupby("supplier")["accession"].last())]
        for sup, g in latest.groupby("supplier"):
            st = [t for t in sorted(tick.get(sup, [])) if t in sp400 and t not in m500 and t in Em.columns]
            if not st:
                continue
            cust = [t for c in g["customer"].unique() for t in sorted(tick.get(c, [])) if t in m500 and t in Em.columns]
            vals = [Em.at[m, t] for t in dict.fromkeys(cust) if np.isfinite(Em.at[m, t])]
            y = Em.at[months[a + 1], st[0]]
            if vals and np.isfinite(y):
                rows.append({"month": m, "ticker": st[0], "universe": "sp400", "signal": float(np.mean(vals)),
                             "n_customers": len(vals), "target": float(y)})
    D = pd.DataFrame(rows)
    D.to_parquet(ROWS)
    print(f"rows {len(D):,}; months {D['month'].nunique()}; suppliers per month (median) "
          f"{D.groupby('month').size().median():.0f}")


def stat(D):
    return I.fm_test(D, "signal", "target", month="month", firm="ticker", direction=1)


if __name__ == "__main__":
    {"links": links, "sample": sample, "gate": gate, "build": build}[sys.argv[1]]()
