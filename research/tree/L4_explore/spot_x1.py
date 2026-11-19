"""Independent-source check of the frozen ETF files against FRED series (sha256 in the output): IEF/TLT daily
return vs the change in the 10y/20y Treasury yield, UUP vs the broad dollar index, DBC vs WTI. Whole-sample
correlation plus 3 spot dates. GLD: no free independent daily gold series reachable (stooq blocked; FRED's LBMA
series discontinued) -> not checked, stated."""
import hashlib, json, os
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
C = os.path.join(ROOT, ".cache", "tree", "l4x")
def etf(t): return pd.read_csv(os.path.join(C, t + ".csv"), parse_dates=["Date"], index_col="Date")["Adj Close"]
def fred(s):
    x = pd.read_csv(os.path.join(C, "fred", s + ".csv"), parse_dates=["observation_date"], index_col="observation_date", na_values=".")[s]
    return x.dropna()
pairs = {"IEF": ("DGS10", "diff", -1), "TLT": ("DGS20", "diff", -1), "UUP": ("DTWEXBGS", "pct", 1), "DBC": ("DCOILWTICO", "pct", 1)}
out = {"fred_sha256": {f: hashlib.sha256(open(os.path.join(C, "fred", f), "rb").read()).hexdigest() for f in sorted(os.listdir(os.path.join(C, "fred")))}}
dates = ["2013-06-20", "2016-06-24", "2019-08-05"]
for t, (s, kind, sign) in pairs.items():
    r = etf(t).pct_change()
    f = fred(s); f = f.diff() if kind == "diff" else f.pct_change()
    j = pd.concat([r, f], axis=1, join="inner").dropna(); j.columns = ["etf", "fred"]
    j = j[j.fred != 0] if kind == "pct" else j
    out[t] = {"series": s, "corr_daily": float(j.corr().iloc[0, 1]), "expected_sign": sign, "n": len(j),
              "spot": {d: {"etf_ret_pct": round(100 * float(j.etf.get(pd.Timestamp(d), np.nan)), 3), "fred_change": round(float(j.fred.get(pd.Timestamp(d), np.nan)) * (1 if kind == "diff" else 100), 3)} for d in dates}}
out["GLD"] = "not checked against an independent source (none reachable); passes the internal contract only"
ok = all(np.sign(out[t]["corr_daily"]) == pairs[t][2] and abs(out[t]["corr_daily"]) > 0.3 for t in pairs)
out["pass"] = bool(ok)
json.dump(out, open(os.path.join(HERE, "X1_SPOT.json"), "w"), indent=1); print(json.dumps(out, indent=1))
