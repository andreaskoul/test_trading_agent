"""Forward paper book for F2, the off-exchange short-volume ratio (research/riskfield/PREREG.md Amendment 16; never
traded). Each Thursday: the 20-session FINRA short-volume ratio of every S&P 500 member; a decile book long the lowest
ratios and short the highest, beta-hedged with SPY; weeks booked with the forward S&P books' arithmetic.

    cd research/quant_trials && PYTHONPATH=. python ../riskfield/forward_f2.py weekly [--asof YYYY-MM-DD] [--dry]
    cd research/quant_trials && PYTHONPATH=. python ../riskfield/forward_f2.py ledger [--dry]

FINRA files: https://cdn.finra.org/equity/regsho/daily/CNMSshvol<YYYYMMDD>.txt (free, no key), cached per day.
"""
import argparse
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.environ.get("F2_REC", os.path.expanduser("~/.fund-runner/research/f2"))
CACHE = os.path.join(os.environ.get("SPX_CACHE", os.path.expanduser("~/.fund-runner/cache/spx")), "finra")
DRY = os.path.join(os.environ.get("SPX_CACHE", os.path.expanduser("~/.fund-runner/cache/spx")), "f2_forward_dry")
HEAD = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market"
MIN_COVERAGE = 0.90


def finra_day(d):
    """One session's consolidated file as (Symbol, ShortVolume, TotalVolume); cached; content-checked."""
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"CNMS{d:%Y%m%d}.parquet")
    if os.path.exists(p):
        return pd.read_parquet(p)
    url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d:%Y%m%d}.txt"
    last = None
    for _ in range(3):
        try:
            t = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research fund-bot@users.noreply.github.com"}),
                                       timeout=60).read().decode("utf-8", "replace")
            break
        except Exception as e:                                           # noqa: BLE001 (transport: retried, then raised)
            last = e
    else:
        raise RuntimeError(f"FINRA file for {d.date()} unavailable: {type(last).__name__}")
    if not t.startswith(HEAD):
        raise RuntimeError(f"FINRA file for {d.date()}: unexpected header")
    x = pd.read_csv(io.StringIO(t), sep="|", dtype={"Date": str, "Symbol": str}, usecols=["Date", "Symbol", "ShortVolume", "TotalVolume"])
    x = x[x.Date == f"{d:%Y%m%d}"][["Symbol", "ShortVolume", "TotalVolume"]]
    if len(x) < 5000:
        raise RuntimeError(f"FINRA file for {d.date()}: only {len(x)} rows")
    x.to_parquet(p)
    return x


def f2_at(S, t, names):
    """Short/total over sessions t-19..t per name; NaN with fewer than 16 of the 20 days (Amendment 14, F2)."""
    sh, tot, cnt = (pd.Series(0.0, index=names) for _ in range(3))
    for d in S[t - 19:t + 1]:
        x = finra_day(d).groupby("Symbol")[["ShortVolume", "TotalVolume"]].sum().reindex(names)
        ok = x.TotalVolume.notna()
        sh[ok] += x.ShortVolume[ok]
        tot[ok] += x.TotalVolume[ok]
        cnt[ok] += 1
    return np.where((cnt >= 16) & (tot > 0), sh / tot.where(tot > 0), np.nan)


def decile_book(score, beta):
    m = np.isfinite(score)
    w = np.zeros(score.shape)
    q = np.nanquantile(score[m], [0.1, 0.9])
    lo, hi = m & (score <= q[0]), m & (score >= q[1])                   # registered sign: low ratio long
    w[lo], w[hi] = 0.5 / lo.sum(), -0.5 / hi.sum()
    return w, -float((w * np.nan_to_num(beta, nan=1.0)).sum())


def weekly(asof=None, dry=False):
    import spx_forward as FW
    import spx_live as L
    out = DRY if dry else REC
    if asof is None:
        exp = FW.expected_thursday()
        if exp is None or os.path.exists(os.path.join(out, f"f2_{exp.date()}.json")):
            print("nothing to record (already recorded, or a holiday week)")
            return None
        asof = str(exp.date())
    d = L.build()
    S, names = d["S"], list(d["names"])
    if pd.Timestamp(asof) not in S:
        sys.exit(f"prices for {asof} are missing (data to {S[-1].date()}): no record written")
    t = int(np.searchsorted(S, pd.Timestamp(asof)))
    path = os.path.join(out, f"f2_{asof}.json")
    if os.path.exists(path):
        sys.exit(f"{path} exists: records are append-only")
    el = d["elig"][t]
    f2 = np.where(el, f2_at(S, t, names), np.nan)
    cov = float(np.isfinite(f2[el]).mean())
    w, wspy = decile_book(f2, d["beta"][t])
    problems = [] if cov >= MIN_COVERAGE else [f"short-volume ratio for {cov:.0%} of members (< {MIN_COVERAGE:.0%})"]
    rec = {"asof": asof, "data_end": str(S[-1].date()), "dry": dry,
           "code": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip(),
           "coverage": cov, "members": int(el.sum()),
           "f2": {n: round(float(x), 5) for n, x in zip(names, f2) if np.isfinite(x)},
           "books": {"f2": {"weights": {n: float(x) for n, x in zip(names, w) if x != 0}, "w_spy": wspy}}, "problems": problems}
    os.makedirs(out, exist_ok=True)
    json.dump(rec, open(path, "w"), indent=1)
    print(f"written {path}: {int(el.sum())} members, coverage {cov:.1%}, long {int((w > 0).sum())} short {int((w < 0).sum())}, "
          f"median ratio {np.nanmedian(f2):.3f}")
    if problems:
        sys.exit("; ".join(problems))
    return path


def ledger(dry=False):
    import spx_forward as FW
    import spx_live as L
    path = DRY if dry else REC
    recs = [json.load(open(os.path.join(path, f))) for f in sorted(os.listdir(path)) if f.startswith("f2_20")] if os.path.isdir(path) else []
    lp = os.path.join(path, "ledger.json")
    led = json.load(open(lp)) if os.path.exists(lp) else {"pl": []}
    have = {r["asof"] for r in led["pl"]}
    d = L.build()
    stamp = str(d["S"][-1].date())
    for a, b in zip(recs[:-1], recs[1:]):
        if a["asof"] in have:
            continue
        if FW.period(d, a, b) is None:
            break
        book, Rm, days, net_exp, dw = FW.book_return(d, a, b, "f2")
        led["pl"].append({"asof": a["asof"], "to": b["asof"], "book": book, "spy": Rm, "turnover": dw,
                          "computed_with_data_to": stamp})
    os.makedirs(path, exist_ok=True)
    json.dump(led, open(lp, "w"), indent=1)
    r = np.array([x["book"] for x in led["pl"]])
    page = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "records": len(recs), "weeks": len(r),
            "cum": float(np.prod(1 + r) - 1) if len(r) else None, "weekly": led["pl"],
            "latest": {k: recs[-1][k] for k in ("asof", "coverage", "members")} if recs else None,
            "evidence": {"oos_2020_2025": {"bp_per_sd": -3.4, "t": -1.88, "net_pct_yr_2bp": 2.08, "sharpe": 0.49},
                         "sp400_2016_2025": {"bp_per_sd": -2.7, "t": -1.61, "p": 0.054}}}
    json.dump(page, open(os.path.join(path, "page.json"), "w"), indent=1, allow_nan=False)
    print(json.dumps({k: page[k] for k in ("records", "weeks", "cum")}))
    return page


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["weekly", "ledger"])
    ap.add_argument("--asof")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    sys.path = [p for p in sys.path if os.path.abspath(p or ".") != HERE]
    weekly(a.asof, a.dry) if a.cmd == "weekly" else ledger(a.dry)
