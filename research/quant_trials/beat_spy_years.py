"""Calendar-year returns of every model x horizon x strategy that beat SPY buy-and-hold over 2013-25 (descriptive;
predictions already seen). Same backtest as strategies.run_all: long/short book + the owner's dynamic SPY sleeve,
broker costs. Writes BEAT_SPY_YEARS.md/.csv.

    python beat_spy_years.py
"""

import os

import numpy as np
import pandas as pd

import panel as P
import sp500_test as T
import sp500_transformers as X
import strategies as ST
import timestral_sp500 as TS

R = P.REPORT
OUT = os.path.join(R, "BEAT_SPY_YEARS.md")


def preds_all():
    preds = {}
    for p_ in X.PARTS:
        z = np.load(X.part_path(p_))
        for k in z.files:
            if k.startswith("h"):
                preds[(p_.split("_h")[0], int(k[1:]))] = z[k]
    z = np.load(TS.PART)
    for h in X.HS:
        preds[("timestral", h)] = z[f"h{h}"]
        with np.errstate(invalid="ignore", divide="ignore"):
            preds[("timestral_unc", h)] = z[f"h{h}"] / np.where(z[f"w{h}"] > 0, z[f"w{h}"], np.nan)
    return preds


def main():
    tab = pd.concat([pd.read_csv(os.path.join(R, f)) for f in ("SP500_STRATEGIES.csv", "SP500_STRATEGIES_TIMESTRAL.csv")])
    tab = tab[tab.span == "2013-25"].drop_duplicates(["model", "h", "strategy"])
    win = tab[tab.vs_spy_pct_yr > 0].sort_values("book_sleeve_pct_yr", ascending=False)
    d, preds = T.build(), preds_all()
    rf, vol = ST.dtb3(), ST.vol60(d)
    years = list(X.YEARS)
    rows, bench = [], None
    for _, r in win.iterrows():
        df = ST.backtest(d, preds[(r.model, int(r.h))], int(r.h), r.strategy, X.YEARS, rf, vol)
        yr = df.groupby("year").total.apply(lambda x: (np.prod(1 + x) - 1) * 100)
        label = "S5" if r.model == "timestral_unc" and r.strategy == "S3" else r.strategy
        model = "timestral" if r.model == "timestral_unc" else r.model
        if r.model == "timestral_unc" and r.strategy != "S3":
            label = f"{r.strategy} (unc.)"
        rows.append({"model": model, "h": int(r.h), "strategy": label, **{y: yr.get(y, np.nan) for y in years},
                     "2013-25 %/yr": r.book_sleeve_pct_yr, "vs SPY": r.vs_spy_pct_yr,
                     "vs risk-matched": r.vs_risk_matched_pct_yr})
        if bench is None:
            sbar = df.s.mean()
            rm = sbar * df.spy - np.maximum(sbar - 1, 0) * df.mrate
            g = df.assign(rm=rm).groupby("year")
            bench = [{"model": "SPY buy-and-hold", **{y: v * 100 for y, v in g.spy.apply(lambda x: np.prod(1 + x) - 1).items()},
                      "2013-25 %/yr": r.spy_pct_yr},
                     {"model": f"risk-matched S&P ({sbar:.2f}x)", **{y: v * 100 for y, v in g.rm.apply(lambda x: np.prod(1 + x) - 1).items()},
                      "2013-25 %/yr": r.risk_matched_pct_yr}]
        X.log(r.model, r.h, r.strategy)
    out = pd.DataFrame(rows)
    b = pd.DataFrame(bench)
    spy = b.iloc[0]
    out["years beating SPY"] = [int(sum(row[y] > spy[y] for y in years)) for _, row in out.iterrows()]
    full = pd.concat([b, out], ignore_index=True)
    full = full[["model", "h", "strategy"] + years + ["2013-25 %/yr", "vs SPY", "vs risk-matched", "years beating SPY"]]
    full.to_csv(OUT.replace(".md", ".csv"), index=False)
    with open(OUT, "w") as f:
        f.write("# Every combination that beat SPY buy-and-hold over 2013-25, by calendar year (descriptive)\n\n"
                "Calendar-year returns in %; book + the owner's dynamic SPY sleeve (1.3x / 0.7x), broker costs "
                "(5 bp per side, margin DTB3 + 2.43%). These predictions were seen at scoring: descriptive only. "
                "Only MASTER h5 passed the pre-registered read (SP500_TRANSFORMERS.md); Timestral failed "
                "(SP500_TIMESTRAL.md). 'unc.' = Timestral's uncertainty-adjusted score; its S3 is S5.\n\n"
                + full.round(1).to_markdown(index=False) + "\n")
    print(full.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
