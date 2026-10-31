"""Company news from Finnhub and the headline normaliser, shared by the lifecycle book and the news audit.

Moved out of fund/lifecycle.py unchanged (2026-10-31), so that modules which must not import lifecycle.py (it reads
sys.argv at import) can fetch and compare news the same way.
"""

import json
import os
import time
import urllib.request


def finnhub_news(t, lo, hi):
    """Articles of ticker t published in (lo, hi] (pandas Timestamps, UTC), or None if Finnhub fails three times."""
    key = os.environ["FINNHUB_API_KEY"]
    url = f"https://finnhub.io/api/v1/company-news?symbol={t.replace('.', '-')}&from={lo.date()}&to={hi.date()}&token={key}"
    for k in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                arts = json.load(r)
            time.sleep(1.05)
            return [a for a in arts if lo.timestamp() < a.get("datetime", 0) <= hi.timestamp()]
        except Exception:
            time.sleep(5 * (k + 1))
    return None


def norm(s):
    return " ".join("".join(ch for ch in str(s or "").lower() if ch.isalnum() or ch == " ").split())
