"""H3a funnel lead-lag (PREREG_thesis_tree.md §4; operational definition: Amendment 5 C).

    python research/p8/h3a.py build    # -> .cache/p8/h3a_rows.parquet (all months; no statistic)
    python research/p8/h3a.py fit      # fit-sample statistic (signal months 2012-01 .. 2021-11), + placebo

Firm i belongs to (chain, stage) by its GICS sub-industry in fund/chains.json (frozen at sign-off). For each
membership with stage k in S0..S3 and month m: signal = equal-weight mean of e_{j,m} over firms j != i in stage
k+1 of the same chain and the same universe as i; target = e_{i,m+1}. A row enters only if stages k and k+1 each
have >= 3 firms with e that month. Universe of i in month m: S&P 500 member at the month's first session (point in
time), else the current S&P 400 list. Signal and its peers come from i's own universe, so each universe's result
stands alone (§1). Registered sign: positive (demand travels upstream). Months are labelled by the signal month.
Placebo (registered, expected null): stage labels shuffled within each chain, once, seed 1.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference as I                                            # noqa: E402
import monthly as MO                                             # noqa: E402
import prices as PX                                              # noqa: E402

ROWS = os.path.join(PX.CACHE, "h3a_rows.parquet")
STAGES = ["S0", "S1", "S2", "S3", "S4"]


def memberships(shuffle_seed=None):
    c = json.load(open(os.path.join(PX.ROOT, "fund", "chains.json")))["chains"]
    g = json.load(open(os.path.join(PX.CACHE, "gics.json")))["firms"]
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    out = []
    for ch, v in c.items():
        sub_stage = {s: st for st in STAGES for s in v.get(st, [])}
        firms = [(t, sub_stage[x["sub"]]) for t, x in g.items() if x["sub"] in sub_stage]
        if rng is not None:                                   # placebo: permute the stage labels across the chain's firms
            st = [s for _, s in firms]
            rng.shuffle(st)
            firms = [(t, s) for (t, _), s in zip(firms, st)]
        out += [{"ticker": t, "chain": ch, "stage": s} for t, s in firms]
    return pd.DataFrame(out)


def build(shuffle_seed=None):
    Em = pd.read_parquet(MO.OUT)
    M = memberships(shuffle_seed)
    sessions = pd.DatetimeIndex(pd.to_datetime([m + "-01" for m in Em.index]))
    mem = PX.members(pd.read_parquet(os.path.join(PX.CACHE, "alpaca_bars.parquet"))["date"].drop_duplicates().sort_values()
                     .pipe(lambda s: pd.DatetimeIndex(s)).union(pd.DatetimeIndex(pd.read_parquet(
                         os.path.join(PX.CACHE, "yf_sp500_close.parquet")).index)))
    sp400 = set(pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", "sp400_current.csv"))["Symbol"])
    months = list(Em.index)
    rows = []
    for a, m in enumerate(months[:-1]):
        nxt = months[a + 1]
        first = mem.index[mem.index.to_period("M") == pd.Period(m)]
        if not len(first):
            continue
        m500 = set(mem.loc[first[0]])
        uni = {t: ("sp500" if t in m500 else ("sp400" if t in sp400 else None)) for t in M["ticker"].unique()}
        e_m, e_n = Em.loc[m], Em.loc[nxt]
        X = M.assign(universe=M["ticker"].map(uni), e=M["ticker"].map(e_m), y=M["ticker"].map(e_n)).dropna(subset=["universe"])
        for (ch, u), g in X.groupby(["chain", "universe"]):
            for k in range(4):
                up, dn = g[(g["stage"] == STAGES[k])], g[(g["stage"] == STAGES[k + 1]) & g["e"].notna()]
                if up["e"].notna().sum() < 3 or len(dn) < 3:
                    continue
                for r in up.dropna(subset=["y"]).itertuples():
                    peers = dn[dn["ticker"] != r.ticker]["e"]
                    if len(peers) < 3:
                        continue
                    rows.append({"month": m, "ticker": r.ticker, "universe": u, "chain": ch, "link": f"{STAGES[k]}<-{STAGES[k + 1]}",
                                 "signal": float(peers.mean()), "target": float(r.y)})
    return pd.DataFrame(rows)


def stat(D):
    """FM over months (all rows); L/S legs de-duplicated by firm (first row in chain order)."""
    fm = I.fm_test(D, "signal", "target", month="month", firm="ticker", direction=1)
    return fm


if __name__ == "__main__":
    if sys.argv[1] == "build":
        D = build()
        D.to_parquet(ROWS)
        D["year"] = D["month"].str[:4]
        print(D.groupby(["year", "universe"]).size().unstack().to_string())
        print(f"rows {len(D):,}; firms {D['ticker'].nunique()}; links {D.groupby(['chain', 'link']).ngroups}")
    elif sys.argv[1] == "fit":
        D = pd.read_parquet(ROWS)
        F = D[(D["month"] >= "2012-01") & (D["month"] <= "2021-11")]
        for u in ("sp500", "sp400"):
            x = F[F["universe"] == u].drop_duplicates(["month", "ticker", "chain", "link"])
            o = stat(x)
            print(f"H3a fit {u}: months {o['months']}, mean slope {o['slope'] * 1e4:+.1f} bp per sd, NW t {o['t']:+.2f}, "
                  f"p {o['p']:.4f}; L/S gross {o['ls_gross'] * 1e4:+.1f} bp/month, net {o['ls_net'] * 1e4:+.1f}")
        P = build(shuffle_seed=1)
        P = P[(P["month"] >= "2012-01") & (P["month"] <= "2021-11")]
        for u in ("sp500", "sp400"):
            o = stat(P[P["universe"] == u])
            print(f"H3a placebo (shuffled stages) {u}: slope {o['slope'] * 1e4:+.1f} bp, t {o['t']:+.2f}, p {o['p']:.4f}")
