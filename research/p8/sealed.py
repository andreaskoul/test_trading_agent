"""The sealed read of P8 family H (PREREG_thesis_tree.md §1, §6; Amendment 4 §1). Made once.

    python3 ~/.claude/hooks/with_secrets.py 'python3 research/p8/sealed.py run'    # fetch + build + read, once

Survivors of the validation read (VALIDATION_READ.md, commit 00b5b31): S&P 400 H1 sympathy reversal only.
Sealed sample: reports with t0 in 2026-01-01 .. 2026-09-30 (§1), S&P 400 (current list), H1 exactly as validated
(research/p8/h1.py: peers, S, CAR, betas, cells, clusters; B = 9,999).
Pass (Amendment 4 §1): beta < 0 (the registered sign) AND net tercile spread > 0. The p-values are reported, no
threshold. Nothing else is read on the sealed window.

Data, loaded here for the first time and kept apart from the validation inputs (which stay byte-identical):
* Alpaca SIP bars 2026-01-02 .. the last complete session -> .cache/p8/alpaca_bars_sealed.parquet;
* 8-K 2.02 releases and first-filed XBRL facts with filing dates up to 2026-10-26 (the SEC bulk files of
  2026-10-26 already on disk; every earlier build stopped at 2025-12-31) -> *_sealed.parquet;
* events with t0 <= 2026-09-30 -> .cache/p8/events_sealed.parquet.
Order: the lock (time + commit) is written first; then the fetch, the build and the read.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import events as EV                                              # noqa: E402
import h1 as H1                                                  # noqa: E402
import prices as PX                                              # noqa: E402
import residuals as RS                                           # noqa: E402

LOCK = os.path.join(PX.OUT, "SEALED_READ.lock")
S0, S1 = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-30")
BARS = "alpaca_bars_sealed.parquet"


def fetch_bars():
    import broker
    sp500, sp400 = PX.universe()
    al = json.load(open(os.path.join(PX.CACHE, "aliases.json")))
    base = set(sp500) | set(sp400) | {"SPY", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"}
    names = sorted(base | {al[t] for t in base if t in al})
    rows = []
    for i in range(0, len(names), 50):
        token = None
        while True:
            q = (f"/v2/stocks/bars?symbols={','.join(names[i:i + 50])}&timeframe=1Day&adjustment=all&feed=sip&limit=10000"
                 f"&start=2026-01-01&end=2026-10-26T00:00:00Z" + (f"&page_token={token}" if token else ""))
            s, b = broker.api("GET", q, base=broker.DATA)
            assert s == 200, f"Alpaca bars failed ({s}); nothing read"
            for t, xs in (b.get("bars") or {}).items():
                rows += [(x["t"][:10], t, float(x["c"]), float(x["v"])) for x in xs]
            token = b.get("next_page_token")
            if not token:
                break
    D = pd.DataFrame(rows, columns=["date", "ticker", "close", "volume"])
    D["date"] = pd.to_datetime(D["date"])
    D.to_parquet(os.path.join(PX.CACHE, BARS))
    return D


def run():
    assert not os.path.exists(LOCK), f"the sealed read has already been made ({open(LOCK).read().strip()})"
    assert os.path.exists(os.path.join(PX.OUT, "VALIDATION_READ.lock")), "the validation read comes first"
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "research/p8"], capture_output=True, text=True, cwd=PX.ROOT).stdout.strip()
    assert not dirty, "commit research/p8 before the sealed read"
    open(LOCK, "w").write(f"{datetime.now(timezone.utc).isoformat()} commit {commit}\n")
    sys.path.insert(0, os.path.join(PX.ROOT, "fund"))

    B = fetch_bars()
    ED.LAST, ED.TAG = pd.Timestamp("2026-10-26 23:59:59"), "_sealed"
    ED.build()
    ED.quarters()
    PX.EXTRA_BARS = [BARS]
    EV.OUT, EV.T0_LAST = os.path.join(PX.CACHE, "events_sealed.parquet"), S1
    R = RS.returns()
    EV.build(R.index)
    D = H1.build()
    D.to_parquet(os.path.join(PX.CACHE, "h1_rows_sealed.parquet"))
    S = D[(D["t0"] >= S0) & (D["t0"] <= S1) & (D["universe"] == "sp400")]
    o = H1.stat(S)
    spread = H1.spread(S)
    passed = bool(o["beta"] < 0 and spread > 0)
    res = {"lock": open(LOCK).read().strip(), "bars_last_session": str(B["date"].max().date()),
           "events": int(len(S)), "seasons": sorted(S["season"].unique().tolist()), **{k: o[k] for k in o},
           "net_spread": spread, "pass": passed}
    json.dump(res, open(os.path.join(PX.OUT, "SEALED_READ.json"), "w"), indent=1, default=float)
    L = ["# P8 family H: the sealed read (Jan-Sep 2026), made once", "",
         f"Lock: {res['lock']}. Bars through {res['bars_last_session']}.", "",
         "Survivor of the validation read: S&P 400 H1 sympathy reversal. Pass (Amendment 4 §1): beta < 0 and net "
         "tercile spread > 0.", "",
         "| events | seasons | beta | t | p_wild | p_RI | net spread | pass |", "|---|---|---|---|---|---|---|---|",
         f"| {o['n']:,} | {', '.join(res['seasons'])} | {o['beta']:+.4f} | {o['t']:+.2f} | {o['p_wild']:.4f} | "
         f"{o['p_ri']:.4f} | {spread * 1e4:+.1f} bp | {'PASS' if passed else 'FAIL'} |", ""]
    open(os.path.join(PX.OUT, "SEALED_READ.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    {"run": run}[sys.argv[1]]()
