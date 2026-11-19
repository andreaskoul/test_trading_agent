"""L5 breadth (PREREG Layer 5, branch B): download and parse the SEC DERA Form 13F data sets, one file at a time.
Plan and every rule: STATE.json (written before any breadth quantity).

    OMP_NUM_THREADS=3 python3 research/tree/L5_breadth/fetch_parse.py names        # panel ticker -> CIK -> SEC names
    OMP_NUM_THREADS=3 python3 research/tree/L5_breadth/fetch_parse.py files 2013q3 ... # download, parse, delete zip

Outputs in .cache/tree/l5breadth/: panel_names.json, parsed/<file>.parquet (period, filer, filing_date, issuer),
parsed/<file>.json (stats, map, defects), MANIFEST.json (sha256 of each zip).
"""
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import zipfile
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
C5 = os.path.join(ROOT, ".cache", "tree", "l5breadth")
RAW, PARSED, SUBS = os.path.join(C5, "raw"), os.path.join(C5, "parsed"), os.path.join(C5, "submissions")
P8 = os.path.join(ROOT, ".cache", "p8", "edgar")
UA = "research-script admin@example.com"
BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
PAD = pd.Timedelta(days=180)
DROP_TAIL = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "LLC", "LP", "NV",
             "SA", "AG", "THE", "DEL", "NEW", "DE", "MD"}
_last = [0.0]


def get(url, path=None):
    for k in range(4):
        dt = time.time() - _last[0]
        if dt < 0.15:
            time.sleep(0.15 - dt)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r:
                if path is None:
                    return r.read()
                with open(path, "wb") as f:
                    shutil.copyfileobj(r, f, 1 << 20)
                return path
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            time.sleep(3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"failed: {url}")


def norm(s):
    s = str(s).upper().replace("&", " AND ")
    s = re.sub(r"[/\\]\s*[A-Z]{2,3}(\s*[/\\]|\b)", " ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    t = s.split()
    if t and t[0] == "THE":
        t = t[1:]
    while t and t[-1] in DROP_TAIL:
        t = t[:-1]
    return " ".join(t)


def free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return st.f_bavail * st.f_frsize / 1e9


# ---------------------------------------------------------------- panel ticker -> CIK -> names with windows
def names():
    os.makedirs(SUBS, exist_ok=True)
    z = np.load(os.path.join(ROOT, ".cache", "tree", "dev.npz"), allow_pickle=False)
    tick = [str(n) for n in z["names"]]
    C = json.load(open(os.path.join(P8, "ciks.json")))
    absent = [t for t in tick if t not in C]
    cur = {v["ticker"].upper(): int(v["cik_str"]) for v in json.loads(get("https://www.sec.gov/files/company_tickers.json")).values()}
    t2c, how = {}, {}
    for t in tick:
        if t in C:
            if C[t]["cik"]:
                t2c[t], how[t] = int(C[t]["cik"]), "p8_ciks.json:" + C[t]["how"]
            else:
                how[t] = "no_cik (p8 typed defect)"
        else:
            k = t.replace(".", "-").upper()
            if k in cur:
                t2c[t], how[t] = cur[k], "sec_company_tickers_2026-11-19"
            else:
                how[t] = "no_cik (absent from ciks.json and SEC current tickers)"
    out = {}
    for c in sorted(set(t2c.values())):
        p = os.path.join(P8, "submissions", f"{c}.json")
        if not os.path.exists(p):
            p = os.path.join(SUBS, f"{c}.json")
            if not os.path.exists(p):
                open(p, "wb").write(get(f"https://data.sec.gov/submissions/CIK{c:010d}.json"))
        s = json.load(open(p))
        f = s["filings"]
        first = min([x["filingFrom"] for x in f.get("files", [])] + list(f["recent"]["filingDate"]) or ["1990-01-01"])
        win = []
        fn = s.get("formerNames") or []
        for x in fn:
            win.append({"name": x["name"], "norm": norm(x["name"]), "from": x["from"][:10], "to": x["to"][:10]})
        start = max([w["to"] for w in win] + [first])
        win.append({"name": s["name"], "norm": norm(s["name"]), "from": start, "to": "2099-12-31"})
        out[c] = {"windows": win, "tickers": sorted(t for t, v in t2c.items() if v == c)}
    res = {"tickers": tick, "ticker_cik": t2c, "how": how, "absent_from_ciks_json": absent, "ciks": out,
           "n_tickers": len(tick), "n_with_cik": len(t2c), "n_ciks": len(out), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(res, open(os.path.join(C5, "panel_names.json"), "w"), indent=0)
    print(f"{len(tick)} tickers, {len(t2c)} with CIK ({len(absent)} absent from ciks.json, "
          f"{sum(1 for t in absent if t in t2c)} of them found in SEC current tickers), {len(out)} CIKs")


# ---------------------------------------------------------------- one data-set file
def read_tsv(zf, name, cols):
    m = [n for n in zf.namelist() if n.upper().endswith(name + ".TSV")]
    assert len(m) == 1, (name, zf.namelist())
    with zf.open(m[0]) as f:
        head = f.readline().decode("utf-8", "replace").rstrip("\r\n").split("\t")
    miss = [c for c in cols if c not in head]
    if miss:
        raise SystemExit(f"typed defect: {name} lacks columns {miss}")
    with zf.open(m[0]) as f:
        return pd.read_csv(f, sep="\t", usecols=cols, dtype=str, quoting=csv.QUOTE_NONE, keep_default_na=False,
                           on_bad_lines="warn", encoding_errors="replace")


def parse(tag, path, PN):
    zf = zipfile.ZipFile(path)
    sub = read_tsv(zf, "SUBMISSION", ["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"])
    cov = read_tsv(zf, "COVERPAGE", ["ACCESSION_NUMBER", "REPORTTYPE", "ISAMENDMENT"])
    summ = read_tsv(zf, "SUMMARYPAGE", ["ACCESSION_NUMBER", "TABLEENTRYTOTAL"])
    info = read_tsv(zf, "INFOTABLE", ["ACCESSION_NUMBER", "NAMEOFISSUER", "CUSIP", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    st = {"file": tag, "submissions": len(sub), "infotable_rows": len(info)}
    st["submission_types"] = sub.SUBMISSIONTYPE.value_counts().to_dict()
    s = sub.merge(cov, on="ACCESSION_NUMBER", how="left")
    s["filing_date"] = pd.to_datetime(s.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    s["period"] = pd.to_datetime(s.PERIODOFREPORT, format="%d-%b-%Y", errors="coerce")
    st["report_types"] = s.REPORTTYPE.value_counts().to_dict()
    k = s[(s.SUBMISSIONTYPE.str.strip() == "13F-HR") & s.REPORTTYPE.str.strip().isin(["13F HOLDINGS REPORT", "13F COMBINATION REPORT"])].copy()
    st["bad_dates"] = int(k.filing_date.isna().sum() + k.period.isna().sum())
    k = k.dropna(subset=["filing_date", "period"])
    qe = k.period.dt.is_quarter_end & (k.period.dt.normalize() == k.period)
    st["non_quarter_end_periods"] = int((~qe).sum())
    k = k[qe]
    k["filer"] = k.CIK.astype(int)
    k = k.sort_values(["filer", "period", "filing_date", "ACCESSION_NUMBER"]).drop_duplicates(["filer", "period"])
    st["reports_kept"] = len(k)
    st["periods"] = {str(p.date()): int(n) for p, n in k.period.value_counts().sort_index().items()}
    acc = set(k.ACCESSION_NUMBER)
    # rows vs SUMMARYPAGE
    cnt = info[info.ACCESSION_NUMBER.isin(acc)].groupby("ACCESSION_NUMBER").size()
    sm = summ.set_index("ACCESSION_NUMBER").TABLEENTRYTOTAL.reindex(sorted(acc))
    sm = pd.to_numeric(sm, errors="coerce")
    agree = (cnt.reindex(sm.index).fillna(0) == sm)
    st["summarypage_rows_agree_share"] = float(agree[sm.notna()].mean())
    st["reports_with_no_infotable_rows"] = int((cnt.reindex(sm.index).fillna(0) == 0).sum())
    # holdings filter
    h = info[info.ACCESSION_NUMBER.isin(acc)]
    h = h[(h.SSHPRNAMTTYPE.str.strip() == "SH") & (h.PUTCALL.str.strip() == "")]
    h = h[pd.to_numeric(h.SSHPRNAMT, errors="coerce").fillna(0) > 0]
    cu = h.CUSIP.str.strip().str.upper()
    okl = cu.str.len().isin([8, 9])
    st["cusip_bad_length_rows"] = int((~okl).sum())
    cu8 = cu.str[:8]
    eq = okl & cu8.str[6:8].str.fullmatch(r"\d\d")
    st["non_equity_issue_rows"] = int((okl & ~eq).sum())
    h = h.assign(cusip=cu8)[eq.values]
    h = h.merge(k[["ACCESSION_NUMBER", "filer"]], on="ACCESSION_NUMBER")
    st["equity_sh_rows"] = len(h)
    # name strings used by >= 2 distinct filers, per CUSIP
    ns = h.assign(nm=h.NAMEOFISSUER.str.strip().str.upper()).groupby(["cusip", "nm"]).filer.nunique()
    ns = ns[ns >= 2].reset_index()
    ns["n"] = ns.nm.map(norm)
    qmid = k.period.max()                     # the file's main period (quarter) date for name validity
    fd = k.filing_date.median()
    valid = defaultdict(set)                  # normalised name -> panel CIKs valid at the file's dates
    for c, v in PN["ciks"].items():
        for w in v["windows"]:
            if pd.Timestamp(w["from"]) - PAD <= fd and qmid <= pd.Timestamp(w["to"]) + PAD and w["norm"]:
                valid[w["norm"]].add(int(c))
    shared = {n for n, cs in valid.items() if len(cs) > 1}
    cmap, defects = {}, {"name_shared_by_2plus_panel_ciks": sorted(shared), "cusip_matches_2plus_ciks": []}
    for cusip, g in ns.groupby("cusip"):
        cs = set()
        for n in g.n:
            if n in valid and n not in shared:
                cs |= valid[n]
        if len(cs) == 1:
            cmap[cusip] = cs.pop()
        elif len(cs) > 1:
            defects["cusip_matches_2plus_ciks"].append(cusip)
    st["cusips_mapped"] = len(cmap)
    st["panel_ciks_mapped"] = len(set(cmap.values()))
    st["panel_ciks_valid_name"] = len({c for cs in valid.values() for c in cs})
    hh = h[h.cusip.isin(cmap)]
    hh = hh.assign(issuer=hh.cusip.map(cmap).astype(np.int32))
    hold = hh[["ACCESSION_NUMBER", "issuer"]].drop_duplicates().merge(k[["ACCESSION_NUMBER", "filer", "filing_date", "period"]], on="ACCESSION_NUMBER")
    fil = k[["filer", "filing_date", "period"]].assign(issuer=np.int32(-1))
    out = pd.concat([fil, hold[["filer", "filing_date", "period", "issuer"]]], ignore_index=True)
    out = out.astype({"filer": np.int32, "issuer": np.int32})
    out.to_parquet(os.path.join(PARSED, f"{tag}.parquet"), index=False)
    st["out_rows"] = len(out)
    json.dump({"stats": st, "map": cmap, "defects": defects}, open(os.path.join(PARSED, f"{tag}.json"), "w"), indent=0, default=str)
    return st


def files(tags):
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(PARSED, exist_ok=True)
    PN = json.load(open(os.path.join(C5, "panel_names.json")))
    mp = os.path.join(C5, "MANIFEST.json")
    man = json.load(open(mp)) if os.path.exists(mp) else {}
    for tag in tags:
        if os.path.exists(os.path.join(PARSED, f"{tag}.json")):
            print(tag, "already parsed")
            continue
        fg = free_gb()
        if fg < 4:
            raise SystemExit(f"STOP: free disk {fg:.1f} GB < 4 GB")
        path = os.path.join(RAW, f"{tag}_form13f.zip")
        get(BASE + f"{tag}_form13f.zip", path)
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        man[tag] = {"url": BASE + f"{tag}_form13f.zip", "bytes": os.path.getsize(path), "sha256": sha,
                    "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "free_gb_before": round(fg, 1)}
        json.dump(man, open(mp, "w"), indent=1)
        st = parse(tag, path, PN)
        os.remove(path)
        man[tag]["zip_deleted_after_parse"] = True
        json.dump(man, open(mp, "w"), indent=1)
        print(tag, json.dumps({k: st[k] for k in ("reports_kept", "summarypage_rows_agree_share", "equity_sh_rows", "cusips_mapped",
                                                  "panel_ciks_mapped", "panel_ciks_valid_name", "out_rows")}), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "names":
        names()
    else:
        files(sys.argv[2:])
