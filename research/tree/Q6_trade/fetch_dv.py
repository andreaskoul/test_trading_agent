"""Q6_trade: consolidated daily dollar volume for the development names, 2011-12-01 .. 2019-12-31 (nothing later).

Why: FINRA `total` (extra_finra.npz) is off-exchange (TRF) SHARE volume; the development panel holds returns only, no
price level, so share volume cannot be turned into the dollar ADV that the square-root model needs (trade $ / ADV $).
Yahoo's split-adjusted Close x split-adjusted Volume is the consolidated dollar volume (the split factor cancels in
the product, so no post-2019 information enters the value). The request ends 2019-12-31.

Content contract (CLAUDE.md rule 2): a name is kept only if Yahoo's daily close-to-close return matches the panel's
D["r"] (on >= 95% of >= 120 common sessions 2013-2019 the two daily returns differ by < 1 percentage point); otherwise (ticker reused, missing) it is a typed
defect, recorded, and the cost model falls back to the FINRA-share route (see lib.adv_dollars).

    python research/tree/Q6_trade/fetch_dv.py      ->  .cache/tree/q6_dv.npz
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import harness  # noqa: E402

OUT = os.path.join(harness.ROOT, ".cache", "tree", "q6_dv.npz")


def main():
    import yfinance as yf
    D = harness.load()
    S, names = D["S"], D["names"]
    rows = np.concatenate([harness.thursdays(D, y) for y in harness.VAL_YEARS])
    used = np.isfinite(D["y5"][rows]).any(0) & D["elig"][rows].any(0)
    tick = [n for n, u in zip(names, used) if u]
    yt = [t.replace(".", "-") for t in tick]
    px = yf.download(yt, start="2011-12-01", end="2020-01-01", auto_adjust=False, progress=False, threads=True)
    close, vol = px["Close"].copy(), px["Volume"].copy()
    miss = [y for y in yt if y not in close.columns or close[y].notna().sum() < 200]
    if miss:                                                        # one retry for transport failures (rule 7)
        px2 = yf.download(miss, start="2011-12-01", end="2020-01-01", auto_adjust=False, progress=False, threads=False)
        c2, v2 = (px2["Close"], px2["Volume"]) if len(miss) > 1 else (px2["Close"].rename(columns={px2["Close"].columns[0]: miss[0]}) if isinstance(px2["Close"], pd.DataFrame) else px2["Close"].to_frame(miss[0]), px2["Volume"].rename(columns={px2["Volume"].columns[0]: miss[0]}) if isinstance(px2["Volume"], pd.DataFrame) else px2["Volume"].to_frame(miss[0]))
        for y in c2.columns:
            if c2[y].notna().sum() > 0:
                close[y], vol[y] = c2[y], v2[y]
    assert close.index.max() <= pd.Timestamp("2019-12-31"), close.index.max()
    close.index = pd.DatetimeIndex(close.index).tz_localize(None).normalize()
    vol.index = close.index
    dv = np.full(D["r"].shape, np.nan, dtype=np.float32)
    clo = np.full(D["r"].shape, np.nan, dtype=np.float32)
    status = {}
    sel = (S >= pd.Timestamp("2013-01-01"))
    for t, y in zip(tick, yt):
        j = names.index(t)
        if y not in close.columns or close[y].notna().sum() < 200:
            status[t] = "missing"
            continue
        c = close[y].reindex(S)
        v = vol[y].reindex(S)
        ry = c.pct_change().to_numpy()
        rp = D["r"][:, j].astype(np.float64)
        m = sel & np.isfinite(ry) & np.isfinite(rp)
        if m.sum() < 120:
            status[t] = f"too short (n {int(m.sum())})"
            continue
        agree = float((np.abs(ry[m] - rp[m]) < 0.01).mean())      # robust to a few spin-off / special-dividend days
        if not (agree >= 0.95):
            status[t] = f"return mismatch (share of days within 1%: {agree:.3f}, n {int(m.sum())})"
            continue
        status[t] = "ok"
        dv[:, j] = (c * v).to_numpy()
        clo[:, j] = c.to_numpy()
    n_ok = sum(v == "ok" for v in status.values())
    note = (f"Yahoo split-adjusted Close x Volume (consolidated dollar volume), 2011-12-01..2019-12-31, aligned to dev.npz; "
            f"{n_ok} of {len(tick)} validation names pass the return-match contract; others NaN (see status).")
    np.savez_compressed(OUT, dv=dv, close_adj=clo, note=np.array(note), status=np.array(json.dumps(status)))
    print(note)
    print({k: v for k, v in status.items() if v != "ok"})


if __name__ == "__main__":
    main()
