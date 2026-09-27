"""Audits for stock_ladder.py (run from repo root): independent decile-sort
re-computation of gross spreads, and a sanity check of the equal-weight
universe against SPY."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
src = open("scripts/xs/stock_ladder.py").read().split("def rank_weights")[0]
G = {"__file__": "scripts/xs/stock_ladder.py"}; exec(compile(src, "s", "exec"), G)
weeks, fwd, elig, S = G["weeks"], G["fwd"], G["elig"], G["S"]
hold = (weeks >= "2016-01-01") & (weeks <= "2026-03-31")
spy = yf.download("SPY", start="2015-12-01", end="2026-04-10", progress=False, auto_adjust=True)["Close"].squeeze()
spy.index = spy.index.tz_localize(None)
thu = weeks[hold] + pd.Timedelta(days=1)
spy_w = spy.reindex(pd.date_range(spy.index.min(), spy.index.max())).ffill().reindex(thu)
spy_r = (spy_w.shift(-1) / spy_w - 1).to_numpy()
ew = fwd.where(elig).mean(1)[hold].to_numpy()
ok = ~np.isnan(spy_r)
print("EW universe vs SPY weekly, holdout: corr %.3f, ann EW %.3f, ann SPY %.3f" % (
    np.corrcoef(ew[ok], spy_r[ok])[0, 1], np.nanmean(ew) * 52, np.nanmean(spy_r) * 52))
for sig in ("mom12_1", "rev1m", "rev1w", "lowvol"):
    for split, m in (("dev", (weeks >= "2004-01-01") & (weeks <= "2015-12-31")), ("hold", hold)):
        sp = []
        for w in weeks[m]:
            s = S[sig].loc[w]; y = fwd.loc[w]; ok_ = s.notna() & y.notna()
            if ok_.sum() < 100: continue
            q = pd.qcut(s[ok_].rank(method="first"), 10, labels=False)
            sp.append(y[ok_][q == 9].mean() - y[ok_][q == 0].mean())
        sp = np.array(sp)
        print(f"{sig:8s} {split:4s} gross top-bottom decile: {sp.mean() * 52:+.3f}/yr  t {sp.mean() / sp.std() * np.sqrt(len(sp)):+.2f}")
