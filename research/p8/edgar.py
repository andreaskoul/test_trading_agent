"""P8 data foundation D5/D6: SEC identifiers, earnings-release times (8-K item 2.02) and first-filed XBRL facts.

    python research/p8/edgar.py ciks       # ticker -> CIK by typed fields only; unmatched names are typed defects
    python research/p8/edgar.py bulk       # SEC's nightly submissions.zip + companyfacts.zip; our CIKs extracted
    python research/p8/edgar.py fetch      # (slow fallback) the same per CIK through the APIs
    python research/p8/edgar.py build      # t0 per report (8-K 2.02), first-filed quarterly EPS, NI, diluted shares
    python research/p8/edgar.py coverage   # firm-quarters with t0 and SUE, against member firm-quarters expected

Ticker -> CIK (CLAUDE.md rule 1: declared fields, never a guess):
  1. SEC's company_tickers.json (current tickers);
  2. the old symbol of a CUSIP-matched ticker change (Alpaca corporate actions): the CIK of its current symbol;
  3. SEC submissions' own `tickers` field, for CIKs already known.
A symbol with no match is recorded as `no_cik` and counted as missing, never matched by name.
Needs SEC_USER_AGENT (run through the secrets wrapper).
"""
import gzip
import json
import os
import sys
import time
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices as PX                                              # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "p8", "edgar")
OUT = os.path.join(ROOT, "reports", "research", "p8")
os.makedirs(os.path.join(CACHE, "submissions"), exist_ok=True)
os.makedirs(os.path.join(CACHE, "facts"), exist_ok=True)
LAST = pd.Timestamp("2025-12-31 23:59:59")                       # never past the validation sample
TAG = ""        # file-name suffix: "" for fit/validation; the sealed read (research/p8/sealed.py) sets "_sealed"
# Declared XBRL concepts for the same quantity, in a fixed order of preference (the first present for a firm-period
# is used): diluted EPS; net income to common holders (diluted first, as diluted EPS uses it); diluted share count.
PREF = {"eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
        "ni": ["NetIncomeLossAvailableToCommonStockholdersDiluted", "NetIncomeLoss",
               "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
        "sh": ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfShareOutstandingBasicAndDiluted"],
        # H3b (Amendment 5 C): inventory is a balance-sheet instant; revenue a duration
        "inv": ["InventoryNet", "InventoryGross"],
        "rev": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]}
INSTANT = {"InventoryNet", "InventoryGross"}


def get(url, tries=4):
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    assert ua, "SEC_USER_AGENT is required"
    for k in range(tries):
        try:
            time.sleep(0.12)
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                return json.loads(gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def ciks():
    sp500, sp400 = PX.universe()
    names = sorted(set(sp500) | set(sp400))
    cur = {v["ticker"].upper(): int(v["cik_str"]) for v in get("https://www.sec.gov/files/company_tickers.json").values()}
    norm = lambda t: t.replace(".", "-").upper()
    al = json.load(open(os.path.join(PX.CACHE, "aliases.json")))
    out = {}
    for t in names:
        if norm(t) in cur:
            out[t] = {"cik": cur[norm(t)], "how": "sec_current"}
        elif t in al and norm(al[t]) in cur:
            out[t] = {"cik": cur[norm(al[t])], "how": f"alias->{al[t]}"}
        else:
            out[t] = {"cik": None, "how": "no_cik"}
    json.dump(out, open(os.path.join(CACHE, "ciks.json"), "w"), indent=0, sort_keys=True)
    miss = [t for t, x in out.items() if x["cik"] is None]
    print(f"{len(names)} symbols: {len(names) - len(miss)} with a CIK, {len(miss)} no_cik")
    print("no_cik:", " ".join(miss))


def fetch():
    C = json.load(open(os.path.join(CACHE, "ciks.json")))
    cik_set = sorted({x["cik"] for x in C.values() if x["cik"]})
    for i, c in enumerate(cik_set):
        sp = os.path.join(CACHE, "submissions", f"{c}.json")
        if not os.path.exists(sp):
            s = get(f"https://data.sec.gov/submissions/CIK{c:010d}.json")
            if s is not None:                                   # older filings are in extra files
                for f in s.get("filings", {}).get("files", []):
                    s.setdefault("older", []).append(get(f"https://data.sec.gov/submissions/{f['name']}"))
            json.dump(s, open(sp, "w"))
        fp = os.path.join(CACHE, "facts", f"{c}.json.gz")
        if not os.path.exists(fp):
            f = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c:010d}.json")
            with gzip.open(fp, "wt") as h:
                json.dump(f, h)
        if i % 100 == 0:
            print(f"{i}/{len(cik_set)} CIKs", flush=True)
    print(f"fetched {len(cik_set)} CIKs")


def _download(url, path):
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    assert ua, "SEC_USER_AGENT is required"
    if os.path.exists(path):
        return
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=600) as r, open(path + ".part", "wb") as f:
        n = 0
        while True:
            b = r.read(1 << 22)
            if not b:
                break
            f.write(b); n += len(b)
    os.replace(path + ".part", path)
    print(f"downloaded {url} ({n / 1e9:.2f} GB)", flush=True)


def bulk():
    """One download each instead of ~2,000 API calls; only our CIKs' entries are read from the archives."""
    import zipfile
    C = json.load(open(os.path.join(CACHE, "ciks.json")))
    want = sorted({x["cik"] for x in C.values() if x["cik"]})
    zs, zf = os.path.join(CACHE, "submissions.zip"), os.path.join(CACHE, "companyfacts.zip")
    _download("https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip", zs)
    _download("https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip", zf)
    with zipfile.ZipFile(zs) as z:
        names = set(z.namelist())
        for c in want:
            main = f"CIK{c:010d}.json"
            s = json.loads(z.read(main)) if main in names else None
            if s is not None:
                for f in s.get("filings", {}).get("files", []):
                    s.setdefault("older", []).append(json.loads(z.read(f["name"])) if f["name"] in names else None)
            json.dump(s, open(os.path.join(CACHE, "submissions", f"{c}.json"), "w"))
    with zipfile.ZipFile(zf) as z:
        names = set(z.namelist())
        for c in want:
            nm = f"CIK{c:010d}.json"
            f = json.loads(z.read(nm)) if nm in names else None
            with gzip.open(os.path.join(CACHE, "facts", f"{c}.json.gz"), "wt") as h:
                json.dump(f, h)
    miss_s = sum(1 for c in want if json.load(open(os.path.join(CACHE, "submissions", f"{c}.json"))) is None)
    print(f"{len(want)} CIKs extracted; without submissions: {miss_s}")


def _filings(s):
    """All filings of a submissions record as a DataFrame (recent + older pages)."""
    parts = [s["filings"]["recent"]] + [o for o in s.get("older", []) if o]
    return pd.concat([pd.DataFrame({k: p[k] for k in ("accessionNumber", "form", "items", "acceptanceDateTime", "reportDate")})
                      for p in parts], ignore_index=True)


def build():
    C = json.load(open(os.path.join(CACHE, "ciks.json")))
    rel, eps = [], []
    for c in sorted({x["cik"] for x in C.values() if x["cik"]}):
        s = json.load(open(os.path.join(CACHE, "submissions", f"{c}.json")))
        if s is None:
            continue
        F = _filings(s)
        k = F[F["form"].isin(["8-K", "8-K/A"]) & F["items"].astype(str).str.split(",").apply(lambda xs: "2.02" in xs)]
        for r in k.itertuples():
            ts = pd.Timestamp(r.acceptanceDateTime[:19])            # EDGAR acceptance time, US Eastern
            if ts <= LAST:
                rel.append({"cik": c, "accession": r.accessionNumber, "form": r.form, "accepted_et": ts})
        with gzip.open(os.path.join(CACHE, "facts", f"{c}.json.gz"), "rt") as h:
            f = json.load(h)
        g = ((f or {}).get("facts") or {}).get("us-gaap", {})
        for concept in {c for cs in PREF.values() for c in cs}:
            for unit, xs in (g.get(concept, {}).get("units") or {}).items():
                for x in xs:
                    inst = concept in INSTANT
                    if x.get("filed") and pd.Timestamp(x["filed"]) <= LAST and x.get("end") and (inst or x.get("start")):
                        eps.append({"cik": c, "concept": concept, "unit": unit, "start": x["end"] if inst else x["start"], "end": x["end"],
                                    "val": x["val"], "filed": x["filed"], "accn": x["accn"], "form": x.get("form"),
                                    "fp": x.get("fp"), "fy": x.get("fy")})
    R = pd.DataFrame(rel).drop_duplicates(["cik", "accession"])
    R.to_parquet(os.path.join(CACHE, f"releases_202{TAG}.parquet"))
    E = pd.DataFrame(eps)
    E["start"], E["end"], E["filed"] = pd.to_datetime(E["start"]), pd.to_datetime(E["end"]), pd.to_datetime(E["filed"])
    E["days"] = (E["end"] - E["start"]).dt.days
    # first-filed value per (firm, concept, period): later restatements are ignored (§1)
    E = E.sort_values(["filed", "accn"]).drop_duplicates(["cik", "concept", "start", "end"], keep="first")
    E.to_parquet(os.path.join(CACHE, f"facts_first{TAG}.parquet"))
    print(f"{len(R):,} earnings releases (8-K 2.02); {len(E):,} first-filed facts")


def quarters():
    """Quarterly first-filed diluted EPS per firm. Quarters are 80-100-day periods; Q4 is derived from the fiscal
    year (330-380 days) as (NI_FY - NI_Q1..Q3) / (4 x FY diluted shares - shares Q1..Q3), flagged (Amendment 4, D6).
    Each quantity takes the first concept of its PREF list present for that firm and period."""
    E = pd.read_parquet(os.path.join(CACHE, f"facts_first{TAG}.parquet"))
    E = E[E["unit"].isin(["USD/shares", "USD", "shares"])]

    def pick(kind):
        rank = {c: i for i, c in enumerate(PREF[kind])}
        x = E[E["concept"].isin(rank)].assign(r=lambda d: d["concept"].map(rank))
        return x.sort_values("r").drop_duplicates(["cik", "start", "end"], keep="first")

    eps, ni, sh = pick("eps"), pick("ni"), pick("sh")
    # one share unit per firm (research/p8/splits.py): values filed before a split are in pre-split shares
    import splits as SP
    C = json.load(open(os.path.join(CACHE, "ciks.json")))
    al = json.load(open(os.path.join(PX.CACHE, "aliases.json")))
    T = SP.table()
    ev = {}
    for t, x in C.items():
        if x["cik"]:
            sy = {t, al.get(t, t)}
            ev.setdefault(x["cik"], []).append(T[T["symbol"].isin(sy)][["ex_date", "ratio"]])
    ev = {c: pd.concat(v).drop_duplicates("ex_date").sort_values("ex_date") for c, v in ev.items()}

    def factor(d):                      # F(filed) / F(last) for each row: < 1 for values filed before a split
        out = []
        for c, f in zip(d["cik"], d["filed"]):
            g = ev.get(c)
            out.append(1.0 if g is None or not len(g) else float(g[g["ex_date"] > f]["ratio"].prod()) ** -1)
        return pd.Series(out, index=d.index)

    eps = eps.assign(val=eps["val"] * factor(eps))
    sh = sh.assign(val=sh["val"] / factor(sh))
    q = lambda d: d[d["days"].between(80, 100)]
    a = lambda d: d[d["days"].between(330, 380)]
    rows = [{"cik": r.cik, "end": r.end, "eps": r.val, "filed": r.filed, "derived": False, "concept": r.concept}
            for r in q(eps).itertuples()]
    niq, shq, sha = q(ni), q(sh), a(sh)
    niq_by = {c: g for c, g in niq.groupby("cik")}
    shq_by = {c: g for c, g in shq.groupby("cik")}
    sha_by = {c: g for c, g in sha.groupby("cik")}
    for r in a(ni).itertuples():
        gq, gs, gf = niq_by.get(r.cik), shq_by.get(r.cik), sha_by.get(r.cik)
        if gq is None or gs is None or gf is None:
            continue
        pn = gq[(gq["end"] > r.start) & (gq["end"] < r.end)]
        ps = gs[(gs["end"] > r.start) & (gs["end"] < r.end)]
        fs = gf[gf["end"] == r.end]
        if len(pn) != 3 or len(ps) != 3 or not len(fs):
            continue
        sh4 = 4 * float(fs["val"].iloc[0]) - float(ps["val"].sum())     # FY average = mean of the 4 quarters
        if sh4 <= 0:
            continue
        rows.append({"cik": r.cik, "end": r.end, "eps": (r.val - float(pn["val"].sum())) / sh4,
                     "filed": r.filed, "derived": True, "concept": "derived:" + r.concept})
    Q = pd.DataFrame(rows).sort_values(["cik", "end", "derived"]).drop_duplicates(["cik", "end"], keep="first")
    Q.to_parquet(os.path.join(CACHE, f"eps_quarterly{TAG}.parquet"))
    return Q


def inv_sales():
    """Quarterly first-filed inventory and revenue per firm (H3b). Revenue: 80-100-day periods, Q4 derived as
    FY - Q1..Q3 (flagged); inventory: the instant at the quarter end (+-5 days). Each quantity takes the first concept
    of its PREF list present. `filed` = the later of the two first-filing dates (the ratio is known only then)."""
    E = pd.read_parquet(os.path.join(CACHE, f"facts_first{TAG}.parquet"))
    E = E[E["unit"] == "USD"]

    def pick(kind):
        rank = {c: i for i, c in enumerate(PREF[kind])}
        x = E[E["concept"].isin(rank)].assign(r=lambda d: d["concept"].map(rank))
        return x.sort_values("r").drop_duplicates(["cik", "start", "end"], keep="first")

    rev, inv = pick("rev"), pick("inv")
    rq = rev[rev["days"].between(80, 100)][["cik", "start", "end", "val", "filed"]].assign(derived=False)
    ra = rev[rev["days"].between(330, 380)]
    q_by = {c: g for c, g in rq.groupby("cik")}
    der = []
    for r in ra.itertuples():
        g = q_by.get(r.cik)
        if g is None:
            continue
        p = g[(g["end"] > r.start) & (g["end"] < r.end)]
        if len(p) == 3:
            der.append({"cik": r.cik, "start": p["end"].max(), "end": r.end, "val": r.val - p["val"].sum(),
                        "filed": r.filed, "derived": True})
    RQ = pd.concat([rq, pd.DataFrame(der)]).sort_values(["cik", "end", "derived"]).drop_duplicates(["cik", "end"], keep="first")
    out = []
    inv_by = {c: g for c, g in inv.groupby("cik")}
    for r in RQ.itertuples():
        g = inv_by.get(r.cik)
        if g is None or r.val <= 0:
            continue
        m = g[(g["end"] - r.end).abs() <= pd.Timedelta(days=5)]
        if not len(m):
            continue
        out.append({"cik": r.cik, "end": r.end, "inv": float(m["val"].iloc[0]), "rev": float(r.val),
                    "ratio": float(m["val"].iloc[0]) / float(r.val), "filed": max(r.filed, m["filed"].iloc[0]),
                    "rev_derived": r.derived})
    X = pd.DataFrame(out)
    X.to_parquet(os.path.join(CACHE, "inv_sales.parquet"))
    return X


def coverage():
    Q = quarters()
    R = pd.read_parquet(os.path.join(CACHE, f"releases_202{TAG}.parquet"))
    C = json.load(open(os.path.join(CACHE, "ciks.json")))
    sp500, sp400 = PX.universe()
    lines = ["# P8 data foundation D5/D6: identifiers, earnings releases, quarterly EPS", "",
             f"Symbols: {len(C)}; with a CIK by typed fields: {sum(1 for x in C.values() if x['cik'])}; "
             f"no_cik (typed defect, counted missing): {sum(1 for x in C.values() if not x['cik'])}.", "",
             "S&P 500 member firm-years with at least 4 earnings releases (8-K 2.02) and 4 quarterly EPS values:", "",
             "| year | member firms | with CIK | >= 4 releases | >= 4 EPS quarters | EPS derived (Q4) share |", "|---|---|---|---|---|---|"]
    m = PX.members()
    for y in range(2012, 2026):
        ts = sorted({t for d, xs in m[m.index.year == y].items() for t in xs})
        ck = [C.get(t, {}).get("cik") for t in ts]
        withc = [c for c in ck if c]
        nr = R[R["accepted_et"].dt.year == y].groupby("cik").size()
        ne = Q[Q["end"].dt.year == y].groupby("cik").size()
        der = Q[(Q["end"].dt.year == y) & Q["cik"].isin(withc)]["derived"].mean()
        lines.append(f"| {y} | {len(ts)} | {len(withc) / len(ts):.1%} | {sum(nr.get(c, 0) >= 4 for c in withc) / len(ts):.1%} | "
                     f"{sum(ne.get(c, 0) >= 4 for c in withc) / len(ts):.1%} | {der:.1%} |")
    miss = sorted(t for t, x in C.items() if not x["cik"])
    lines += ["", f"no_cik symbols ({len(miss)}): " + " ".join(miss), ""]
    open(os.path.join(OUT, "D5_D6_coverage.md"), "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    {"ciks": ciks, "bulk": bulk, "fetch": fetch, "build": build, "coverage": coverage}[sys.argv[1]]()
