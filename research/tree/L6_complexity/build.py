"""Layer 6 T1 build: the book series (development 2013-2019, 2020-2025) with its checks, the frozen macro files
(MANIFEST.json), the VIX file. No timing result is computed here.

    OMP_NUM_THREADS=4 python3 research/tree/L6_complexity/build.py book     # book + checks -> .cache/tree/l6/book_*.parquet
    OMP_NUM_THREADS=4 python3 research/tree/L6_complexity/build.py macro    # freeze FRED (or fallbacks) + VIX
"""
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib as L  # noqa: E402

CHECK = os.path.join(L.HERE, "BUILD_CHECK.json")


def book():
    os.makedirs(L.CACHE, exist_ok=True)
    d, rf = L.panel()
    out = json.load(open(CHECK)) if os.path.exists(CHECK) else {}
    dev = L.sim_book(d, L.dev_scores(d), range(2013, 2020), rf)
    ref_dev = L.L4.sim(d, L.dev_scores(d), L.L4.book_decile, range(2013, 2020), rf=rf)
    rd = L.read_scores()
    red = L.sim_book(d, rd, range(2020, 2026), rf)
    ref_red = L.L4.sim(d, rd, L.L4.book_decile, range(2020, 2026), rf=rf)
    for a, b in ((dev, ref_dev), (red, ref_red)):
        assert (a.index == b.index).all()
        assert np.array_equal(a.book.values, b.book.values) and np.array_equal(a.total.values, b.total.values)
    led = pd.read_csv(os.path.join(L.TREE, "L4_exploit", "b0_audit_runner", "weekly_b0_ledger.csv"))
    same_dates = led.date.tolist() == [str(x.date()) for x in red.index]
    same_days = led.days.tolist() == red.days.tolist()
    diff = float(np.max(np.abs(led.book_net_return.values - red.book.values)))
    exact = bool(same_dates and same_days and diff <= 1e-12)
    w = (dev.book * 7 / dev.days).to_numpy()
    w2 = (red.book * 7 / red.days).to_numpy()
    # the development scores equal the quant-tf file on rows <= 2019
    q = rd[d["S"] <= pd.Timestamp("2019-12-31")]
    p = L.dev_scores(d)[d["S"] <= pd.Timestamp("2019-12-31")]
    both = np.isfinite(q) & np.isfinite(p)
    out["book"] = {
        "simulator": "L4_exploit sim() with book_decile (identical book and total asserted), K.GROSS_SIDE 0.3",
        "reproduces_B0_ledger_book_net_return": exact, "ledger_weeks": int(len(led)), "max_abs_diff": diff,
        "same_dates": same_dates, "same_days": same_days,
        "dev_2013_2019": {"weeks": int(len(dev)), "first": str(dev.index[0].date()), "last": str(dev.index[-1].date()),
                          "last_end_session": str(d["S"][int(dev.end.iloc[-1])].date()),
                          "book_sharpe": L.sharpe(w), "book_pct_per_year_arith": 100 * 52 * float(w.mean()),
                          "mean_book_gross": float(dev.book_gross.mean())},
        "y2020_2025": {"weeks": int(len(red)), "book_sharpe": L.sharpe(w2), "book_pct_per_year_arith": 100 * 52 * float(w2.mean()),
                       "mean_book_gross": float(red.book_gross.mean())},
        "dev_scores_vs_quant_tf_rows_le_2019": {"same_mask": bool((np.isfinite(q) == np.isfinite(p)).all()),
                                                "max_abs_diff": float(np.abs(q[both] - p[both]).max())}}
    json.dump(out, open(CHECK, "w"), indent=1)
    dev.to_parquet(os.path.join(L.CACHE, "book_dev.parquet"))
    red.to_parquet(os.path.join(L.CACHE, "book_2020_2025.parquet"))
    L.log(out["book"])
    if not exact:
        sys.exit("STOP: 2020-2025 book does not reproduce the B0 ledger")


def macro():
    """Freeze at first use; never re-fetched. Fallbacks as registered in STATE.json."""
    man_p = os.path.join(L.CACHE, "MANIFEST.json")
    man = json.load(open(man_p)) if os.path.exists(man_p) else {"files": {}, "notes": []}
    freq = {"DTB3": "daily", "DGS10": "daily", "BAA": "monthly", "AAA": "monthly"}
    fallback = {"DTB3": os.path.join(L.K.QT, ".cache", "quant_trials", "dtb3.csv"),
                "DGS10": os.path.join(L.ROOT, ".cache", "tree", "l4x", "fred", "DGS10.csv")}
    for s, f in freq.items():
        if s in man["files"]:
            continue
        p = os.path.join(L.RAW, f"{s}.csv")
        if os.path.exists(p) and os.path.getsize(p) > 1000 and open(p).readline().startswith("observation_date"):
            man["files"][s] = {"path": os.path.relpath(p, L.ROOT), "sha256": L.sha(p), "frequency": f,
                               "source": f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}",
                               "frozen_utc": pd.Timestamp.utcnow().isoformat()}
        elif s in fallback and os.path.exists(fallback[s]):
            dst = os.path.join(L.RAW, f"{s}_fallback.csv")
            shutil.copyfile(fallback[s], dst)
            man["files"][s] = {"path": os.path.relpath(dst, L.ROOT), "sha256": L.sha(dst), "frequency": f,
                               "source": f"fallback copy of {fallback[s]} (fred.stlouisfed.org unreachable from this session)",
                               "source_sha256": L.sha(fallback[s]), "frozen_utc": pd.Timestamp.utcnow().isoformat()}
        else:
            man["notes"].append(f"{s}: not available (FRED unreachable, no fallback); dropped")
    if "VIX" not in man["files"]:
        import yfinance as yf
        x = yf.download("^VIX", start="2008-01-01", end="2026-01-01", progress=False, auto_adjust=False)
        c = x["Close"]
        c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
        v = pd.DataFrame({"date": pd.DatetimeIndex(c.index).tz_localize(None).normalize(), "close": c.values}).dropna()
        assert len(v) > 4000 and v.date.max() >= pd.Timestamp("2025-12-30")
        p = os.path.join(L.RAW, "VIX.csv")
        v.to_csv(p, index=False)
        man["files"]["VIX"] = {"path": os.path.relpath(p, L.ROOT), "sha256": L.sha(p), "frequency": "daily close",
                               "source": "yfinance ^VIX (Yahoo Finance), 2008-2025", "frozen_utc": pd.Timestamp.utcnow().isoformat()}
    json.dump(man, open(man_p, "w"), indent=1)
    L.log(json.dumps(man, indent=1))


if __name__ == "__main__":
    {"book": book, "macro": macro}[sys.argv[1]]()
