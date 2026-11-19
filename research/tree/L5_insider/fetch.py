"""Layer 5 branch I data: SEC DERA Insider Transactions Data Sets (Form 3/4/5), 2006Q1-2025Q4.

    python3 -I research/tree/L5_insider/fetch.py

One quarterly zip at a time, generic User-Agent, < 10 requests per second, stop if free disk < 4 GB. Keeps Form 4 and
5 (no amendments) open-market codes P and S for issuers that are panel CIKs (ciks.json) or whose typed
ISSUERTRADINGSYMBOL is a panel ticker (for the CIK verification). Zip sha256 recorded, zip deleted after parsing.
Output: .cache/tree/l5insider/trades.parquet (+ sha256), filings_by_year.json, MANIFEST.json.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, ".cache", "tree", "l5insider")
RAW = os.path.join(OUT, "raw")
UA = "research-script admin@example.com"
BASE = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}q{}_form345.zip"
QUARTERS = [(y, q) for y in range(2006, 2026) for q in (1, 2, 3, 4)]


def norm(s):
    return s.astype(str).str.upper().str.replace(r"[.\-/ ]", "", regex=True).str.strip()


def free_gb():
    o = subprocess.run(["df", "-k", "/System/Volumes/Data"], capture_output=True, text=True).stdout.splitlines()[1].split()
    return int(o[3]) / 1024 ** 2


def panel():
    z = np.load(os.path.join(ROOT, ".cache", "tree", "dev.npz"), allow_pickle=False)
    names = [str(n) for n in z["names"]]
    c = json.load(open(os.path.join(ROOT, ".cache", "p8", "edgar", "ciks.json")))
    ciks = {int(c[n]["cik"]) for n in names if n in c and c[n]["cik"]}
    ticks = {n.upper().replace(".", "").replace("-", "") for n in names}
    return ciks, ticks


def tsv(zf, name, cols):
    with zf.open(name) as f:
        return pd.read_csv(f, sep="\t", usecols=cols, dtype=str, on_bad_lines="warn", low_memory=False)


def main():
    os.makedirs(RAW, exist_ok=True)
    ciks, ticks = panel()
    man_p = os.path.join(OUT, "MANIFEST.json")
    man = json.load(open(man_p)) if os.path.exists(man_p) else {"quarters": {}}
    parts_dir = os.path.join(OUT, "parts")
    os.makedirs(parts_dir, exist_ok=True)
    for y, q in QUARTERS:
        key = f"{y}q{q}"
        if key in man["quarters"] and os.path.exists(os.path.join(parts_dir, key + ".parquet")):
            continue
        gb = free_gb()
        if gb < 4:
            sys.exit(f"STOP: free disk {gb:.1f} GB < 4 GB before {key}")
        url = BASE.format(y, q)
        zp = os.path.join(RAW, key + ".zip")
        for k in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=300) as r, open(zp, "wb") as f:
                    shutil.copyfileobj(r, f)
                break
            except Exception as e:  # noqa: BLE001
                print(key, "retry", k, e, flush=True)
                time.sleep(5 * (k + 1))
        else:
            sys.exit(f"STOP: {key} download failed")
        sha = hashlib.sha256(open(zp, "rb").read()).hexdigest()
        size = os.path.getsize(zp)
        zf = zipfile.ZipFile(zp)
        sub = tsv(zf, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "PERIOD_OF_REPORT", "DOCUMENT_TYPE",
                                         "ISSUERCIK", "ISSUERTRADINGSYMBOL"])
        own = tsv(zf, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK"])
        tr = tsv(zf, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                                            "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
        zf.close()
        # contract: required fields present and non-trivial
        n_sub, n_tr = len(sub), len(tr)
        assert n_sub > 10000 and n_tr > 10000, (key, n_sub, n_tr)
        acc_re = r"^\d{10}-\d{2}-\d{6}$"
        bad_acc = {k: float(1 - v.ACCESSION_NUMBER.astype(str).str.match(acc_re).mean()) for k, v in (("sub", sub), ("own", own), ("tr", tr))}
        assert max(bad_acc.values()) < 1e-3, (key, bad_acc)
        sub["FILING_DATE"] = pd.to_datetime(sub.FILING_DATE, format="%d-%b-%Y", errors="coerce")
        bad_fd = int(sub.FILING_DATE.isna().sum())
        sub["cik"] = pd.to_numeric(sub.ISSUERCIK, errors="coerce")
        sub["sym"] = norm(sub.ISSUERTRADINGSYMBOL.fillna(""))
        f45 = sub[sub.DOCUMENT_TYPE.isin(["4", "5"])]
        counts = {"all_4_5_filings": int(len(f45)), "all_submissions": n_sub,
                  "panel_cik_4_5_filings": int(f45.cik.isin(ciks).sum()), "bad_filing_date": bad_fd, "bad_accession_share": bad_acc}
        keep = f45[f45.cik.isin(ciks) | f45.sym.isin(ticks)].copy()
        # per-issuer filing counts (any 4/5, for coverage and availability), dated by filing date
        fil = keep[["ACCESSION_NUMBER", "FILING_DATE", "cik", "sym", "DOCUMENT_TYPE"]].copy()
        o = own.dropna().copy()
        o["owner"] = pd.to_numeric(o.RPTOWNERCIK, errors="coerce")
        o = o.groupby("ACCESSION_NUMBER").owner.min()
        fil["owner"] = fil.ACCESSION_NUMBER.map(o)
        t = tr[tr.TRANS_CODE.isin(["P", "S"]) & tr.ACCESSION_NUMBER.isin(set(fil.ACCESSION_NUMBER))].copy()
        t["TRANS_DATE"] = pd.to_datetime(t.TRANS_DATE, format="%d-%b-%Y", errors="coerce")
        t["shares"] = pd.to_numeric(t.TRANS_SHARES, errors="coerce")
        t["price"] = pd.to_numeric(t.TRANS_PRICEPERSHARE, errors="coerce")
        t = t.rename(columns={"TRANS_CODE": "code", "TRANS_ACQUIRED_DISP_CD": "ad", "TRANS_DATE": "trans_date"})
        t = t[["ACCESSION_NUMBER", "trans_date", "code", "shares", "price", "ad"]]
        fil.rename(columns={"ACCESSION_NUMBER": "acc", "FILING_DATE": "filing_date", "DOCUMENT_TYPE": "doc"}).assign(
            quarter=key).to_parquet(os.path.join(parts_dir, key + "_filings.parquet"))
        t.rename(columns={"ACCESSION_NUMBER": "acc"}).assign(quarter=key).to_parquet(os.path.join(parts_dir, key + ".parquet"))
        counts.update({"kept_filings": int(len(fil)), "kept_PS_transactions": int(len(t))})
        man["quarters"][key] = {"url": url, "sha256": sha, "bytes": size, "counts": counts,
                                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        json.dump(man, open(man_p, "w"), indent=1)
        os.remove(zp)
        print(key, f"{size / 1e6:.0f} MB", counts, f"free {gb:.1f} GB", flush=True)
        time.sleep(0.5)

    # combine
    F = pd.concat([pd.read_parquet(os.path.join(parts_dir, f"{y}q{q}_filings.parquet")) for y, q in QUARTERS])
    T = pd.concat([pd.read_parquet(os.path.join(parts_dir, f"{y}q{q}.parquet")) for y, q in QUARTERS])
    dup = int(F.acc.duplicated().sum())
    F = F.drop_duplicates("acc")
    T = T.merge(F[["acc", "filing_date", "cik", "sym", "owner", "doc"]], on="acc", how="inner")
    fp, tp = os.path.join(OUT, "filings.parquet"), os.path.join(OUT, "trades.parquet")
    F.to_parquet(fp)
    T.to_parquet(tp)
    man["combined"] = {"filings": int(len(F)), "trades": int(len(T)), "duplicate_accessions_dropped": dup,
                       "filings_sha256": hashlib.sha256(open(fp, "rb").read()).hexdigest(),
                       "trades_sha256": hashlib.sha256(open(tp, "rb").read()).hexdigest()}
    json.dump(man, open(man_p, "w"), indent=1)
    shutil.rmtree(parts_dir)
    print("combined", man["combined"])


if __name__ == "__main__":
    main()
