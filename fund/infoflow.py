"""Point-in-time readers for the two archives (Amendment 6). Shadow desks only.

    news(lo, hi)        S&P 500 company news (fund/archive.py), one row per (sym, article), published in [lo, hi]
    context(cutoff)     context archive rows (fund/context_archive.py) fetched at or before the cutoff, the
                        latest fetch of each (source, key), payload parsed

Both read the private Hugging Face datasets into local mirrors (fund_archive/, fund_context/) and download
only the day files they need. A row counts only if it was available at the cutoff: news by its publication
time, context by its fetch time.
"""

import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_DIR, CONTEXT_DIR = os.path.join(ROOT, "fund_archive"), os.path.join(ROOT, "fund_context")
_api = None


def _hf():
    global _api
    if _api is None:
        from huggingface_hub import HfApi
        _api = HfApi(token=os.environ["HF_TOKEN"])
        _api.user = _api.whoami()["name"]
    return _api


def _days(repo, local, lo, hi):
    """Local paths of the day files in [lo, hi] (inclusive dates), downloading the missing ones."""
    from huggingface_hub import hf_hub_download
    api = _hf()
    want = [f for f in api.list_repo_files(f"{api.user}/{repo}", repo_type="dataset")
            if f.startswith("days/") and str(lo) <= f[5:15] <= str(hi)]
    out = []
    for f in sorted(want):
        p = os.path.join(local, f)
        if not os.path.exists(p) or f[5:15] >= str(pd.Timestamp(hi).date() - pd.Timedelta(days=2)):
            p = hf_hub_download(f"{api.user}/{repo}", f, repo_type="dataset", local_dir=local, token=os.environ["HF_TOKEN"])
        out.append(p)
    return out


def news(lo, hi):
    """Company news published in [lo, hi] (timestamps, UTC)."""
    lo, hi = pd.Timestamp(lo, tz="UTC") if pd.Timestamp(lo).tz is None else pd.Timestamp(lo), \
        pd.Timestamp(hi, tz="UTC") if pd.Timestamp(hi).tz is None else pd.Timestamp(hi)
    files = _days("fund-news-archive", NEWS_DIR, lo.date(), hi.date())
    if not files:
        return pd.DataFrame(columns=["sym", "t", "desc", "publisher", "published", "tickers", "h"])
    A = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    A["published"] = pd.to_datetime(A["published"], utc=True, errors="coerce")
    A = A[(A["published"] >= lo) & (A["published"] <= hi)]
    A["tickers"] = A["tickers"].map(lambda x: list(x) if x is not None else [])
    return A.reset_index(drop=True)


def context(cutoff, sources=None, lookback_days=120):
    """Context rows fetched at or before the cutoff: the latest fetch of each (source, key)."""
    cutoff = pd.Timestamp(cutoff, tz="UTC") if pd.Timestamp(cutoff).tz is None else pd.Timestamp(cutoff)
    files = _days("fund-context-archive", CONTEXT_DIR, (cutoff - pd.Timedelta(days=lookback_days)).date(), cutoff.date())
    if not files:
        return pd.DataFrame(columns=["source", "key", "published_at", "fetched_at", "payload"])
    C = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    C["fetched_at"] = pd.to_datetime(C["fetched_at"], utc=True, errors="coerce")
    C = C[C["fetched_at"] <= cutoff]
    if sources:
        C = C[C["source"].isin(sources)]
    C = C.sort_values("fetched_at").drop_duplicates(["source", "key"], keep="last")
    C["payload"] = C["payload"].map(json.loads)
    return C.reset_index(drop=True)
