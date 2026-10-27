"""P8 filings text (H5 Lazy Prices, H2 named customers): every 10-K and 10-Q of the universe's CIKs filed
2010-06-01 .. 2025-12-31, primary document from EDGAR, converted to plain text and stored gzipped.

    python research/p8/text.py fetch       # resumable; SEC fair access (< 10 requests/s); needs SEC_USER_AGENT
    python research/p8/text.py status      # counts fetched / failed

Filings are chosen by their declared `form` (10-K, 10-Q; amendments excluded) and `primaryDocument` in the
SEC submissions record (CLAUDE.md rule 1). HTML -> text: <script>, <style> and inline-XBRL hidden headers
(ix:header) removed, tags stripped, entities unescaped, whitespace collapsed. A document under 2,000 characters
of text is an input defect (logged, counted missing).
"""
import gzip
import html
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402

DIR = os.path.join(ED.CACHE, "text")
LOG = os.path.join(ED.CACHE, "text_log.jsonl")
os.makedirs(DIR, exist_ok=True)
_lock, _last = threading.Lock(), [0.0]


def filings():
    C = json.load(open(os.path.join(ED.CACHE, "ciks.json")))
    out = []
    for c in sorted({x["cik"] for x in C.values() if x["cik"]}):
        s = json.load(open(os.path.join(ED.CACHE, "submissions", f"{c}.json")))
        if s is None:
            continue
        parts = [s["filings"]["recent"]] + [o for o in s.get("older", []) if o]
        for p in parts:
            for f, d, a, doc, rd in zip(p["form"], p["filingDate"], p["accessionNumber"], p["primaryDocument"], p["reportDate"]):
                if f in ("10-K", "10-Q") and "2010-06-01" <= d <= "2025-12-31" and doc:
                    out.append({"cik": c, "form": f, "filed": d, "accession": a, "doc": doc, "period": rd})
    return out


def to_text(b, tables=True):
    t = b.decode("utf-8", errors="ignore")
    t = re.sub(r"(?is)<(script|style|ix:header)[^>]*>.*?</\1>", " ", t)
    if not tables:                                       # the parser check compares with edgar-corpus, which drops tables
        t = re.sub(r"(?is)<table[^>]*>.*?</table>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t).replace("\xa0", " ")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def get(url):
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    assert ua, "SEC_USER_AGENT is required"
    for k in range(4):
        with _lock:                                           # global pacing: <= 9 requests per second
            wait = _last[0] + 0.111 - time.time()
            if wait > 0:
                time.sleep(wait)
            _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=90) as r:
                b = r.read()
                return gzip.decompress(b) if r.headers.get("Content-Encoding") == "gzip" else b
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (k + 1))
        except Exception:
            time.sleep(5 * (k + 1))
    return None


def one(f):
    p = os.path.join(DIR, str(f["cik"]), f["accession"] + ".txt.gz")
    if os.path.exists(p):
        return None
    url = f"https://www.sec.gov/Archives/edgar/data/{f['cik']}/{f['accession'].replace('-', '')}/{f['doc']}"
    b = get(url)
    if b is None:
        return {**f, "status": "fetch_failed"}
    t = to_text(b)
    if len(t) < 2000:
        return {**f, "status": "input_defect", "chars": len(t)}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, "wt") as h:
        h.write(t)
    return None


def fetch():
    F = filings()
    todo = [f for f in F if not os.path.exists(os.path.join(DIR, str(f["cik"]), f["accession"] + ".txt.gz"))]
    print(f"{len(F):,} filings; {len(todo):,} to fetch", flush=True)
    done = 0
    with ThreadPoolExecutor(8) as ex, open(LOG, "a") as log:
        for r in ex.map(one, todo):
            done += 1
            if r is not None:
                log.write(json.dumps(r) + "\n"); log.flush()
            if done % 1000 == 0:
                print(f"{done:,}/{len(todo):,}", flush=True)
    json.dump(F, open(os.path.join(ED.CACHE, "filings_text_index.json"), "w"))
    print("done")


def status():
    F = filings()
    have = sum(os.path.exists(os.path.join(DIR, str(f["cik"]), f["accession"] + ".txt.gz")) for f in F)
    bad = [json.loads(x) for x in open(LOG)] if os.path.exists(LOG) else []
    print(f"{have:,}/{len(F):,} fetched; logged problems {len(bad)}: "
          f"{ {s: sum(b['status'] == s for b in bad) for s in {b['status'] for b in bad}} }")


if __name__ == "__main__":
    {"fetch": fetch, "status": status}[sys.argv[1]]()
