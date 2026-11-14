import sys, os, json, numpy as np, pandas as pd
ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "research", "tree"))
import harness as H
D = H.load()
S, names = D["S"], D["names"]; N = len(names)
print("dev", D["y5"].shape, S.min().date(), S.max().date(), "keys", sorted(D.keys()))
rows = np.concatenate([H.thursdays(D, y) for y in H.VAL_YEARS])
def nw(x, lags=4):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x); d = x - x.mean(); v = d @ d / n
    for l in range(1, lags + 1): v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return x.mean(), x.mean() / np.sqrt(v / n), n
def ind_ic(ind, label, D=D, rows=rows):
    """ind: bool (N,) or (T,N). IC over eligible names with a target."""
    out, cov = [], []
    for t in rows:
        m = np.isfinite(D["y5"][t]) & D["elig"][t]
        x = (ind if ind.ndim == 1 else ind[t])[m].astype(float)
        cov.append(x.mean())
        if m.sum() < 50 or x.std() == 0: out.append(np.nan); continue
        out.append(pd.Series(x).corr(pd.Series(D["y5"][t][m].astype(float)), method="spearman"))
    a, t_, n = nw(out)
    # mean y5 difference in bp/week
    print(f"{label:48s} cov {np.mean(cov):.3f}  IC {a:+.4f}  t {t_:+.2f}  n {n}")
el = D["elig"][rows]; hasy = np.isfinite(D["y5"][rows])
ever = el.any(0)
print("ever eligible (val Thursdays):", ever.sum(), "of", N, "| with any target:", (el & hasy).any(0).sum(), "| eligible name-weeks w/o target:", 1 - (el & hasy).sum() / el.sum())
g = json.load(open(".cache/p8/gics.json"))["firms"]
has_g = np.array([n in g for n in names]); ind_ic(has_g, "in gics.json (Q7 reproduction)")
for f in ("sp500_current.csv", "sp400_current.csv"):
    p = os.path.join(ROOT, "data", "raw", "stocks", f)
    print(f, os.path.exists(p))
ev = pd.read_parquet(".cache/p8/events.parquet")
print("events cols", list(ev.columns), len(ev), ev.universe.value_counts().to_dict(), "tickers", ev.ticker.nunique())
sec = ev.groupby("ticker").sector.last()
in_ev = np.array([n in sec.index for n in names]); ind_ic(in_ev, "ticker in events.parquet")
sec_known = np.array([isinstance(sec.get(n, None), str) for n in names]); ind_ic(sec_known, "events sector known (construct.sectors)")
t2c = ev.dropna(subset=["cik"]).groupby("ticker").cik.last().astype(int).to_dict()
has_cikfile = np.array([(n in t2c) and os.path.exists(f".cache/tree/sec/{t2c[n]:010d}.json.gz") for n in names]); ind_ic(has_cikfile, "matched to SEC companyfacts file (N1)")
C = json.load(open(".cache/p8/edgar/ciks.json"))
print("ciks.json:", len(C), "no_cik", sum(1 for x in C.values() if not x["cik"]))
priced_ever = (el & hasy).any(0)
print("among names with a target: in gics %d/%d, in events %d, cik file %d" % ((has_g & priced_ever).sum(), priced_ever.sum(), (in_ev & priced_ever).sum(), (has_cikfile & priced_ever).sum()))
print("among ever-eligible w/o any target (unpriced): n %d, in gics %d, in events %d, cik %d" % ((ever & ~priced_ever).sum(), (has_g & ever & ~priced_ever).sum(), (in_ev & ever & ~priced_ever).sum(), (has_cikfile & ever & ~priced_ever).sum()))
for key in ("fundamentals", "peers", "finra", "intraday"):
    z = H.load_extra(key)
    print("==", key, {k: v.shape for k, v in z.items() if k != "note"})
    print(str(z["note"])[:700])
    if key == "fundamentals":
        for k in ("assets_0", "revenue_0", "net_income_0", "shares_0", "sue"):
            ind_ic(np.isfinite(z[k]), f"fundamentals {k} available")
        anyf = np.zeros(D["y5"].shape, bool)
        for k, v in z.items():
            if k not in ("note", "sue"): anyf |= np.isfinite(v)
        ind_ic(anyf, "fundamentals any XBRL field available")
    if key == "peers":
        yrs = list(z["years"]); nb = z["neighbours"]
        hasp = np.zeros(D["y5"].shape, bool)
        for a, y in enumerate(yrs): hasp[S.year == y] = (nb[a, :, 0] >= 0)[None, :]
        ind_ic(hasp, "peer graph vector available")
    if key == "finra":
        for k in z:
            if k != "note" and z[k].shape == D["y5"].shape: ind_ic(np.isfinite(z[k]), f"finra {k} available")
    if key == "intraday":
        r16 = np.concatenate([H.thursdays(D, y) for y in (2016, 2017, 2018, 2019)])
        for k in z:
            if k == "note": continue
            v = z[k]
            if v.shape[:2] == D["y5"].shape: ind_ic(np.isfinite(v).reshape(v.shape[0], v.shape[1], -1).any(2), f"intraday {k} available 2016-19", rows=r16)
            else: print(k, v.shape)
de = pd.read_parquet(".cache/p8/decay_earnings_events.parquet", columns=["ticker", "t0"])
has_de = np.array([n in set(de.ticker) for n in names]); ind_ic(has_de, "ticker in decay_earnings_events")
cur = set(pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_current.csv"))["Symbol"]) if os.path.exists(os.path.join(ROOT, "data", "raw", "stocks", "sp500_current.csv")) else None
if cur: ind_ic(np.array([n in cur for n in names]), "in sp500_current.csv")
