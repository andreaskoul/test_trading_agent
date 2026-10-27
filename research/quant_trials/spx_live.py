"""Live S&P 500 data for the forward research books (PREREG_quant_transformers.md Amendment 3). Never traded.

    python spx_live.py download            # prices of every name ever in the index since 2009, plus today's members
    python spx_live.py train PART          # live model on all data to now (owner, 2026-10-24), saved by tag
"""

import os
import sys

import numpy as np
import pandas as pd

import panel as P
import sp500_test as T

LIVE_PX = os.path.join(os.environ.get("SPX_CACHE", P.CACHE), "sp500_close_live.parquet")
_BUILD = T.build                                               # the research build, before any patching
CURRENT = os.path.join(P.ROOT, "data", "raw", "stocks", "sp500_current.csv")


def current_members():
    return set(pd.read_csv(CURRENT)["Symbol"].astype(str))


def download(end=None):
    import yfinance as yf
    end = pd.Timestamp(end) if end is not None else pd.Timestamp.now().normalize()
    m = pd.read_csv(os.path.join(P.ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    names = sorted(set().union(*m[m.date >= T.START]["tickers"].map(lambda s: set(s.split(","))).values)
                   | current_members())
    ymap = {t: t.replace(".", "-") for t in names}
    frames = []
    for k in range(0, len(names), 100):
        chunk = [ymap[t] for t in names[k: k + 100]]
        frames.append(yf.download(chunk + (["SPY"] if k == 0 else []), start=str(T.START.date()),
                                  end=str((end + pd.Timedelta(days=1)).date()), auto_adjust=True, progress=False,
                                  threads=True)["Close"])
    px = pd.concat(frames, axis=1)
    px = px.loc[:, ~px.columns.duplicated()].rename(columns={v: k for k, v in ymap.items()})
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    px = px[px.index <= end]
    missing = sorted(t for t in current_members() if t not in px or px[t].iloc[-5:].isna().all())
    px.to_parquet(LIVE_PX)
    print(f"prices to {px.index.max().date()}: {px.notna().any().sum()} names; current members without recent "
          f"prices: {len(missing)} {missing[:10]}")
    return missing


def build():
    """sp500_test.build() on the live prices: data to the last close; eligibility is the point-in-time membership,
    and from its last row (2026-08-18) on, today's member list."""
    px = pd.read_parquet(LIVE_PX)
    end = pd.to_datetime(px.index).max()
    m = pd.read_csv(os.path.join(P.ROOT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    last = m.date.max()
    T.PX, T.END = LIVE_PX, end

    def membership():
        s = m.set_index("date")["tickers"].map(lambda x: set(x.split(",")))
        extra = pd.Series([current_members()], index=[last + pd.Timedelta(days=1)])
        return pd.concat([s, extra])
    T.membership = membership
    return _BUILD()


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "download":
        download()
    elif cmd == "train":
        import sp500_transformers as X
        X.T.build = build                                      # all data to the last close (owner, 2026-10-24)
        end = pd.read_parquet(LIVE_PX).index.max()
        X.train_final(sys.argv[2], year=end.year + 1, tag=f"live_{end.date()}")
