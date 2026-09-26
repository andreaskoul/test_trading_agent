"""Confirmation test, reports/research/PROTOCOL_fx_confirm.md (1990-2003).

    python scripts/xs/fx_confirm.py   # -> reports/research/fx/confirm_*.csv
"""

import io
import os
import urllib.request
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "reports", "research", "fx")
H10 = {"JPY": ("DEXJPUS", False, "JP"), "GBP": ("DEXUSUK", True, "GB"), "CHF": ("DEXSZUS", False, "CH"),
       "AUD": ("DEXUSAL", True, "AU"), "NZD": ("DEXUSNZ", True, "NZ"), "CAD": ("DEXCAUS", False, "CA"),
       "SEK": ("DEXSDUS", False, "SE"), "NOK": ("DEXNOUS", False, "NO"), "DKK": ("DEXDNUS", False, "DK"),
       "ZAR": ("DEXSFUS", False, "ZA"), "KRW": ("DEXKOUS", False, "KR"), "MXN": ("DEXMXUS", False, "MX")}
COST = {**{c: 2e-4 for c in "JPY GBP CHF AUD NZD CAD SEK NOK DKK".split()}, "MXN": 6e-4, "KRW": 6e-4, "ZAR": 12e-4}
START, END = "1990-01-01", "2003-12-31"


def fred(fid):
    with urllib.request.urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}", timeout=60) as r:
        s = pd.read_csv(io.BytesIO(r.read()), na_values=".")
    s.columns = ["date", "v"]
    return s.assign(date=pd.to_datetime(s.date)).set_index("date")["v"].dropna()


spot = pd.DataFrame({c: (lambda s: s if usd else 1 / s)(fred(f)) for c, (f, usd, _) in H10.items()})
spot = spot[(spot.index >= "1988-06-01") & (spot.index <= "2004-02-01")]
rates = pd.DataFrame({c: fred(f"IR3TIB01{cc}M156N") / 100 for c, (_, _, cc) in H10.items()})
rates["USD"] = fred("IR3TIB01USM156N") / 100
CCY = list(H10)

days = pd.date_range(spot.index.min(), spot.index.max(), freq="D")
daily = spot.reindex(days).ffill(limit=3)
wed = daily[daily.index.dayofweek == 2]
thu = daily.reindex(wed.index + pd.Timedelta(days=1)); thu.index = wed.index
m_rates = rates.reindex(pd.date_range("1985-01-01", "2004-03-01", freq="MS")).ffill(limit=2)
diff_now = m_rates[CCY].sub(m_rates["USD"], axis=0)
acc = diff_now.reindex(wed.index, method="ffill") / 52
sig_c = diff_now.copy(); sig_c.index = sig_c.index + pd.DateOffset(months=2)
carry = sig_c.reindex(wed.index, method="ffill")
# a currency is in the universe only once both spot and its rate exist
elig = wed.notna() & thu.notna() & acc.notna()
x_wed = (np.log(wed).diff() + acc).where(elig)
x_fwd = (np.log(thu).shift(-1) - np.log(thu) + acc.shift(-1)).where(elig)
scores = {"rev1m": -x_wed.rolling(4, min_periods=4).sum(), "carry": carry.where(elig)}
weeks = wed.index
mask = (weeks >= START) & (weeks <= END)


def rank_w(s):
    r = s.where(elig).rank(axis=1); r = r.sub(r.mean(1), axis=0)
    return r.div(r.abs().sum(1), axis=0).mul(2).fillna(0)


def nw_t(x, L):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; e = x - x.mean(); s = e @ e / len(x)
    for k in range(1, L + 1):
        s += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / len(x)
    return x.mean() / np.sqrt(s / len(x))


cost = pd.Series(COST)[CCY]
dol = x_fwd.mean(1)
rows = []
for hid, sig, H in (("rev1m-1", "rev1m", 1), ("rev1m-4", "rev1m", 4), ("carry-4", "carry", 4)):
    W = rank_w(scores[sig])
    for mult in (1.0, 0.5, 2.0):
        pos = W.where(pd.Series(mask, index=weeks), 0).rolling(H, min_periods=1).mean()
        net = ((pos * x_fwd.fillna(0)).sum(1) - (pos.diff().abs().fillna(0) * cost * mult).sum(1))[mask]
        net = net[W[mask].abs().sum(1) > 0]
        if mult != 1.0:
            rows[-1][f"sharpe_cost{mult}x"] = net.mean() / net.std() * np.sqrt(52)
            continue
        X = np.column_stack([np.ones(len(net)), dol[net.index].fillna(0)])
        b = np.linalg.lstsq(X, net.to_numpy(), rcond=None)[0]
        e = net.to_numpy() - X @ b
        # HAC alpha t
        XtX = np.linalg.inv(X.T @ X); Sg = (X * e[:, None]).T @ (X * e[:, None]) / len(e)
        for k in range(1, 5 + H):
            G = (X[k:] * e[k:, None]).T @ (X[:-k] * e[:-k, None]) / len(e); Sg += (1 - k / (5 + H)) * (G + G.T)
        V = len(e) * XtX @ Sg @ XtX
        sl = []
        for w in weeks[mask]:
            s, y = scores[sig].loc[w], x_fwd.loc[w]; ok = s.notna() & y.notna()
            if ok.sum() >= 6:
                r = s[ok].rank(); r = (r - 1) / (len(r) - 1) - 0.5
                sl.append(np.polyfit(r, y[ok], 1)[0])
        rows.append(dict(hypothesis=hid, weeks=len(net), n_ccy_median=float(elig[mask].sum(1).median()),
                         ann_ret=net.mean() * 52, sharpe=net.mean() / net.std() * np.sqrt(52),
                         t_nw=nw_t(net, 4 + H), alpha_dol_t=b[0] / np.sqrt(V[0, 0]),
                         fm_spread_ann=np.mean(sl) * 52, fm_t=nw_t(sl, 4)))
R = pd.DataFrame(rows)
R["CONFIRMED"] = (R.t_nw > 2.13) & (R.fm_t > 2.13)
R.to_csv(os.path.join(OUT, "confirm_1990_2003.csv"), index=False)
pd.set_option("display.width", 200)
print(R.round(3).to_string())
