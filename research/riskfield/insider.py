"""Risk-field round 7: insider trading from the SEC Insider Transactions Data Sets (Forms 3/4/5, structured, quarterly).

    python3 ~/.claude/hooks/with_secrets.py 'python research/riskfield/insider.py download'   # needs SEC_USER_AGENT
    python research/riskfield/insider.py build     # -> .cache/riskfield/insider_trades.parquet (no statistic)

Source: https://www.sec.gov/dera/data/form-345 (files <yyyy>q<q>_form345.zip, 2006 onwards), as filed.
Only typed fields are used (CLAUDE.md rule 1): TRANS_CODE (P = open-market purchase, S = open-market sale),
TRANS_ACQUIRED_DISP_CD, TRANS_SHARES, TRANS_PRICEPERSHARE, the filing's ISSUERCIK, the owner's RPTOWNERCIK and
relationship flags, FILING_DATE and TRANS_DATE. Amendments (4/A) are dropped; the signal date is the filing date (public).
"""
import io
import os
import sys
import time
import urllib.request
import zipfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panel as PN                                                                    # noqa: E402

RAW = os.path.join(PN.CACHE, "form345")
OUT = os.path.join(PN.CACHE, "insider_trades.parquet")
QUARTERS = [f"{y}q{q}" for y in range(2010, 2026) for q in range(1, 5)]
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}_form345.zip"


def download():
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    assert ua, "SEC_USER_AGENT is required"
    os.makedirs(RAW, exist_ok=True)
    for q in QUARTERS:
        p = os.path.join(RAW, f"{q}_form345.zip")
        if os.path.exists(p) and zipfile.is_zipfile(p):
            continue
        for attempt in range(4):
            try:
                req = urllib.request.Request(URL.format(q), headers={"User-Agent": ua})
                data = urllib.request.urlopen(req, timeout=120).read()
                zipfile.ZipFile(io.BytesIO(data)).namelist()                 # content check: a real zip
                open(p, "wb").write(data)
                print(q, f"{len(data) / 1e6:.1f} MB")
                break
            except Exception as e:                                           # noqa: BLE001
                print(q, "attempt", attempt + 1, type(e).__name__)
                time.sleep(5 * 2 ** attempt)
        else:
            raise SystemExit(f"{q}: download failed 4 times")
        time.sleep(0.5)


def build():
    rows = []
    for q in QUARTERS:
        z = zipfile.ZipFile(os.path.join(RAW, f"{q}_form345.zip"))
        rd = lambda n, cols: pd.read_csv(z.open(n), sep="\t", usecols=cols, dtype=str, low_memory=False)
        sub = rd("SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERTRADINGSYMBOL"])
        sub = sub[sub.DOCUMENT_TYPE.isin(["4", "5"])]
        own = rd("REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"])
        own = own.drop_duplicates("ACCESSION_NUMBER")                       # first reporting owner per filing
        tr = rd("NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                                       "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD", "DIRECT_INDIRECT_OWNERSHIP"])
        tr = tr[tr.TRANS_CODE.isin(["P", "S"])]
        x = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
        rows.append(x)
        print(q, len(x))
    D = pd.concat(rows, ignore_index=True)
    for c in ("FILING_DATE", "TRANS_DATE"):
        D[c] = pd.to_datetime(D[c], format="%d-%b-%Y", errors="coerce")
    for c in ("TRANS_SHARES", "TRANS_PRICEPERSHARE"):
        D[c] = pd.to_numeric(D[c], errors="coerce")
    D["ISSUERCIK"] = pd.to_numeric(D.ISSUERCIK, errors="coerce").astype("Int64")
    D["RPTOWNERCIK"] = pd.to_numeric(D.RPTOWNERCIK, errors="coerce").astype("Int64")
    D["value"] = D.TRANS_SHARES * D.TRANS_PRICEPERSHARE
    D = D[(D.FILING_DATE <= PN.END) & D.FILING_DATE.notna() & D.TRANS_DATE.notna()]
    # content contract: purchases are acquisitions, sales dispositions; dates sane
    bad = ((D.TRANS_CODE == "P") & (D.TRANS_ACQUIRED_DISP_CD != "A")) | ((D.TRANS_CODE == "S") & (D.TRANS_ACQUIRED_DISP_CD != "D")) | \
          (D.TRANS_DATE > D.FILING_DATE) | (D.FILING_DATE - D.TRANS_DATE > pd.Timedelta(days=400))
    print(f"input defects dropped: {int(bad.sum())} of {len(D)}")
    D = D[~bad].drop(columns=["TRANS_ACQUIRED_DISP_CD"])
    D.to_parquet(OUT)
    print(f"{len(D)} open-market trades; purchases {int((D.TRANS_CODE == 'P').sum())}; issuers {D.ISSUERCIK.nunique()}; "
          f"filings {D.FILING_DATE.min().date()}..{D.FILING_DATE.max().date()}")


if __name__ == "__main__":
    {"download": download, "build": build}[sys.argv[1]]()
