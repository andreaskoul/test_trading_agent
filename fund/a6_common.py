"""Amendment 6 shared plumbing: the context archive (fund/context_archive.py) read point in time.

Used only by the Amendment 6 shadow desks (macro_desk, neighbours, shadow_info, review_context);
no champion desk imports it.
"""

import glob
import json
import os
import re

import pandas as pd

from common import DRYRUN, MOCK, ROOT

CTX = os.path.join(ROOT, "fund_context")
# 8-K item numbers -> plain names (SEC Form 8-K General Instructions)
ITEMS = {"1.01": "material agreement", "1.02": "agreement terminated", "1.03": "bankruptcy", "1.05": "cybersecurity incident",
         "2.01": "acquisition or disposal completed", "2.02": "results of operations", "2.03": "new debt obligation",
         "2.04": "debt acceleration", "2.05": "exit or restructuring costs", "2.06": "impairment",
         "3.01": "delisting notice", "3.02": "unregistered equity sale", "3.03": "security holder rights changed",
         "4.01": "auditor change", "4.02": "financials no longer reliable", "5.01": "change in control",
         "5.02": "director or officer change", "5.03": "bylaws or fiscal year change", "5.07": "shareholder vote",
         "7.01": "Reg FD disclosure", "8.01": "other events", "9.01": "exhibits"}
MAJOR = re.compile(r"employment situation|consumer price index|producer price|gross domestic product|personal income|"
                   r"retail sales|job openings|unemployment insurance|industrial production|housing starts|"
                   r"durable goods|university of michigan|fomc|beige book|international trade in goods", re.I)
SECTOR_ETF = {"Communication Services": "XLC", "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Energy": "XLE",
              "Financials": "XLF", "Health Care": "XLV", "Industrials": "XLI", "Information Technology": "XLK",
              "Materials": "XLB", "Real Estate": "XLRE", "Utilities": "XLU"}
GICS = ["Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials", "Health Care",
        "Industrials", "Information Technology", "Materials", "Real Estate", "Utilities"]


def effective_cutoff(cutoff) -> pd.Timestamp:
    """The week's cutoff. A6_TEST_CUTOFF may move it, for testing only: honoured in mock and dry runs,
    never in a live run (the context archive starts after past weeks' cutoffs, so a replayed week sees nothing)."""
    t = os.environ.get("A6_TEST_CUTOFF")
    return pd.Timestamp(t) if t and (MOCK or DRYRUN) else pd.Timestamp(cutoff)


def load_context(lo, cutoff) -> pd.DataFrame:
    """Rows fetched on UTC days lo..cutoff, keeping only those with fetched_at <= cutoff (point in time).
    Empty in mock mode or when the archive is unreachable; a desk then works without it."""
    lo, cutoff = pd.Timestamp(lo).normalize(), effective_cutoff(cutoff)
    days = [str(d.date()) for d in pd.date_range(lo, cutoff.normalize())]
    try:
        if not MOCK:
            from huggingface_hub import HfApi, snapshot_download
            api = HfApi(token=os.environ["HF_TOKEN"])
            repo = f"{api.whoami()['name']}/{os.environ.get('CONTEXT_REPO', 'fund-context-archive')}"
            have = set(api.list_repo_files(repo, repo_type="dataset"))
            want = [f"days/{d}.parquet" for d in days if f"days/{d}.parquet" in have]
            if want:
                snapshot_download(repo, repo_type="dataset", allow_patterns=want, local_dir=CTX, token=os.environ["HF_TOKEN"])
        fs = [p for p in glob.glob(os.path.join(CTX, "days", "*.parquet")) if os.path.basename(p)[:10] in days]
        df = pd.concat([pd.read_parquet(p) for p in fs]) if fs else pd.DataFrame()
    except Exception as exc:
        print(f"context archive unavailable ({exc!r}); working without it")
        df = pd.DataFrame()
    if df.empty:
        return pd.DataFrame(columns=["source", "key", "published_at", "fetched_at", "h", "payload", "fetched", "p"])
    ft = pd.to_datetime(df["fetched_at"], utc=True).dt.tz_localize(None)
    df = df[ft <= cutoff].assign(fetched=ft[ft <= cutoff]).sort_values("fetched")
    return df.assign(p=df["payload"].map(json.loads))


def latest(df, source, before=None) -> pd.DataFrame:
    """The last stored version of each key of a source (optionally as fetched before a time)."""
    d = df[df["source"] == source]
    if before is not None:
        d = d[d["fetched"] <= pd.Timestamp(before)]
    return d.drop_duplicates("key", keep="last")


def filings(df, ticker, lo, hi) -> list:
    """8-K / 8-K/A of one firm accepted in (lo, hi], newest first, items in plain words."""
    e = latest(df, "edgar")
    if e.empty:
        return []
    acc = pd.to_datetime(e["published_at"], utc=True, errors="coerce").dt.tz_localize(None)
    e = e[(acc > pd.Timestamp(lo)) & (acc <= pd.Timestamp(hi)) & (e["p"].map(lambda p: p.get("ticker")) == ticker)]
    return [{"accepted": a[:16].replace("T", " "), "form": p["form"],
             "items": [f"{ITEMS.get(i.strip(), 'item ' + i.strip())} ({i.strip()})" for i in str(p.get("items") or "").split(",") if i.strip()]}
            for a, p in sorted(zip(e["published_at"], e["p"]), key=lambda x: x[0], reverse=True)]
