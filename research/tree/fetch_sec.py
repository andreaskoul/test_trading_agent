"""Phase 2, N1 data: SEC XBRL company facts for every name in the development panel (point in time by filing date).
Run through the redacting wrapper (needs SEC_USER_AGENT). Raw JSON per CIK in .cache/tree/sec/ (gzip)."""
import gzip, json, os, sys, time, urllib.request
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, ".cache", "tree", "sec")
EV = "/Users/apollogodofthesun/test_trading_agent/.claude/worktrees/riskfield/.cache/p8/events.parquet"
UA = os.environ.get("SEC_USER_AGENT", "").strip()
assert UA, "SEC_USER_AGENT not set"
ev = pd.read_parquet(EV, columns=["cik", "ticker"]).drop_duplicates()
ciks = sorted(set(int(c) for c in ev.cik.dropna()))
ok = fail = skip = 0
for c in ciks:
    p = os.path.join(OUT, f"{c:010d}.json.gz")
    if os.path.exists(p):
        skip += 1; continue
    for k in range(3):
        try:
            req = urllib.request.Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c:010d}.json", headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                b = b if r.headers.get("Content-Encoding") == "gzip" else gzip.compress(b)
            open(p, "wb").write(b); ok += 1; break
        except urllib.error.HTTPError as e:
            if e.code == 404: fail += 1; break
            time.sleep(2 * (k + 1))
        except Exception:
            time.sleep(2 * (k + 1))
    else:
        fail += 1
    time.sleep(0.12)
print(f"companyfacts: {len(ciks)} CIKs, fetched {ok}, already had {skip}, failed {fail}")
json.dump({"ciks": len(ciks), "fetched": ok, "had": skip, "failed": fail, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(os.path.join(OUT, "_manifest.json"), "w"))
