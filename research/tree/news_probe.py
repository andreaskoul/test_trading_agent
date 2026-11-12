"""Layer 3, L3.4 step 1: size of the Alpaca (Benzinga) news history, for a cost estimate. No article text is kept.
Run through the redacting wrapper. Sample: 25 names drawn with a fixed seed from the development panel's 2019 members;
every article for each in 2019 is counted (pages of 50), plus the share with a non-empty summary and body length.
"""
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "fund"))
sys.path.insert(0, HERE)
import broker  # noqa: E402
import harness as H  # noqa: E402

D = H.load()
S = D["S"]
i = int(S.searchsorted(__import__("pandas").Timestamp("2019-06-28")))
members = [n for n, e in zip(D["names"], D["elig"][i]) if e]
random.seed(20261112)
sample = sorted(random.sample(members, 25))
out, calls = {}, 0
for t in sample:
    n, summ, token = 0, 0, None
    while True:
        q = f"/v1beta1/news?symbols={t}&start=2019-01-01T00:00:00Z&end=2019-12-31T23:59:59Z&limit=50&sort=asc" + (f"&page_token={token}" if token else "")
        s, b = broker.api("GET", q, base=broker.DATA)
        calls += 1
        if s != 200:
            out[t] = {"error": s}
            break
        arts = b.get("news") or []
        n += len(arts)
        summ += sum(1 for a in arts if (a.get("summary") or "").strip())
        token = b.get("next_page_token")
        if not token:
            out[t] = {"articles_2019": n, "with_summary": summ}
            break
        time.sleep(0.3)
counts = [v["articles_2019"] for v in out.values() if "articles_2019" in v]
res = {"sample": sample, "per_name": out, "api_calls": calls, "mean_articles_per_name_year": sum(counts) / len(counts),
       "median": sorted(counts)[len(counts) // 2], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
json.dump(res, open(os.path.join(HERE, "N4_news", "PROBE.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "per_name"}))
