import sys, os, json, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "research", "tree"))
import harness as H
def nw(x, lags=4):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x); d = x - x.mean(); v = d @ d / n
    for l in range(1, lags + 1): v += 2 * (1 - l / (lags + 1)) * (d[l:] @ d[:-l]) / n
    return x.mean(), x.mean() / np.sqrt(v / n), n
def ind_ic(D, rows, ind, label, extra=None):
    out, cov, sc = [], [], []
    for t in rows:
        m = np.isfinite(D["y5"][t]) & D["elig"][t]
        if extra is not None: m &= extra[t] if extra.ndim == 2 else extra
        if m.sum() < 50: continue
        x = (ind if ind.ndim == 1 else ind[t])[m].astype(float)
        cov.append(x.mean())
        out.append(np.nan if x.std() == 0 else pd.Series(x).corr(pd.Series(D["y5"][t][m].astype(float)), method="spearman"))
    a, t_, n = nw(out)
    print(f"  {label:52s} cov {np.mean(cov):.3f}  IC {a:+.4f}  t {t_:+.2f}  weeks {n}")
def sc_corr(D, rows, pred, ind, label, extra=None):
    out = []
    for t in rows:
        m = np.isfinite(pred[t]) & D["elig"][t] & np.isfinite(D["y5"][t])
        if extra is not None: m &= extra
        x = (ind if ind.ndim == 1 else ind[t])[m].astype(float)
        if m.sum() < 50 or x.std() == 0: continue
        out.append(pd.Series(pred[t][m].astype(float)).corr(pd.Series(x), method="spearman"))
    print(f"  corr(score, indicator) {label:40s} mean {np.mean(out):+.4f}  (sd of weekly {np.std(out):.3f}, weeks {len(out)})")
cur = set(pd.read_csv("data/raw/stocks/sp500_current.csv")["Symbol"])
g = json.load(open(".cache/p8/gics.json"))["firms"]
ev = pd.read_parquet(".cache/p8/events.parquet")
sec = ev.groupby("ticker").sector.last()
print("events tickers with sector all-missing:", int(sec.isna().sum()), "of", len(sec))
# ---------- dev
D = H.load(); names = D["names"]; S = D["S"]
rows = np.concatenate([H.thursdays(D, y) for y in H.VAL_YEARS]); r16 = np.concatenate([H.thursdays(D, y) for y in (2016, 2017, 2018, 2019)])
is_cur = np.array([n in cur for n in names]); has_g = np.array([n in g for n in names])
print("DEV 2013-2019")
ind_ic(D, rows, is_cur, "in sp500_current.csv"); ind_ic(D, rows, has_g, "in gics.json")
R = H.load_extra("intraday")["R"]; hasR = np.isfinite(R).all(1)
print("  intraday: names with any bars", int(hasR.any(0).sum()), "| of them in sp500_current", int((hasR.any(0) & is_cur).sum()), "| current members in panel", int(is_cur.sum()))
ind_ic(D, r16, hasR, "intraday bars available (2016-19)"); ind_ic(D, r16, is_cur, "in sp500_current (2016-19)")
M = D["master_h5_ref"].astype(float)
ind_ic(D, r16, hasR, "intraday available | MASTER finite (N3 universe)", extra=np.isfinite(M))
sc_corr(D, rows, M, is_cur, "MASTER ref vs current-member")
sc_corr(D, rows, M, has_g, "MASTER ref vs in-gics")
for nm in ("A_mse_rank", "D_hgb_mh", "X1_8p"):
    pass
P = H.load_extra("peers"); 
for a, y in enumerate(P["years"]):
    if y in (2013, 2016, 2019):
        hv = P["neighbours"][a, :, 0] >= 0; e = D["elig"][S.year == y].any(0)
        print(f"  peers {y}: names with vector {int(hv.sum())}; eligible that year {int(e.sum())}; eligible with vector {int((hv & e).sum())}; of eligible-with-vector in gics {int((hv & e & has_g).sum())}; eligible w/o vector in gics {int((~hv & e & has_g).sum())}")
# ---------- full panel 2020-25
import holdout as HO
F = HO.full_panel(); fn = F["names"]; FS = F["S"]
fr = np.concatenate([H.thursdays(F, y) for y in HO.YEARS]); fr = fr[fr < len(FS) - 7]
fcur = np.array([n in cur for n in fn]); fg = np.array([n in g for n in fn])
el = F["elig"][fr]; hy = np.isfinite(F["y5"][fr])
print("FULL PANEL 2020-2025 (S&P 500 holdout, spent)", F["y5"].shape, "names==dev names:", fn == names)
print("  ever eligible", int(el.any(0).sum()), "| with a target", int((el & hy).any(0).sum()), "| eligible name-weeks w/o target %.3f" % (1 - (el & hy).sum() / el.sum()))
for y in HO.YEARS:
    rr = H.thursdays(F, y); rr = rr[rr < len(FS) - 7]; e = F["elig"][rr]; h = np.isfinite(F["y5"][rr])
    print(f"   {y}: eligible/wk {e.sum(1).mean():.0f}, with target {(e & h).sum(1).mean():.0f}")
ind_ic(F, fr, fcur, "in sp500_current.csv"); ind_ic(F, fr, fg, "in gics.json")
fsec = np.array([isinstance(sec.get(n, None), str) for n in fn]); ind_ic(F, fr, fsec, "events sector known (construct.sectors)")
FM = F["master_h5_ref"].astype(float)
sc_corr(F, fr, FM, fcur, "MASTER vs current-member 2020-25")
allr = np.concatenate([H.thursdays(F, y) for y in range(2013, 2026)]); allr = allr[allr < len(FS) - 7]
ind_ic(F, allr, fcur, "in sp500_current.csv 2013-2025")
ZF = dict(np.load(".cache/tree/extra_fundamentals_full.npz", allow_pickle=False))
anyf = np.zeros(F["y5"].shape, bool)
for k, v in ZF.items():
    if k not in ("note", "sue") and v.shape == anyf.shape: anyf |= np.isfinite(v)
ind_ic(F, fr, anyf, "fundamentals_full any XBRL field available"); ind_ic(F, fr, np.isfinite(ZF["sue"]), "fundamentals_full sue available")
for nm in ("holdout2_pred_N1",):
    p = np.load(f".cache/tree/{nm}.npy").astype(float)
    if p.shape == F["y5"].shape: sc_corr(F, fr, p, fcur, f"{nm} vs current-member")
# ---------- S&P 400 panel
import panel400 as P4
D4, is400 = P4.build(); n4 = D4["names"]; S4 = D4["S"]
s400cur = set(pd.read_csv("data/raw/stocks/sp400_current.csv")["Symbol"])
print("S&P 400 PANEL: scored columns", int(is400.sum()), "| current list", len(s400cur), "| events sp400 tickers", ev[ev.universe == "sp400"].ticker.nunique(), "| scored not in current list", sum(1 for n, f in zip(n4, is400) if f and n not in s400cur), "| current-list names that are S&P 500 panel columns", len(s400cur & set(names)))
fb = pd.Series({n: S4[np.argmax(D4["valid"][:, j])] for j, n in enumerate(n4) if is400[j]})
print("  first close: on 2016-01-04:", int((fb <= pd.Timestamp("2016-01-05")).sum()), "| 2016-2018:", int(((fb > pd.Timestamp("2016-01-05")) & (fb < pd.Timestamp("2019-01-01"))).sum()), "| 2019 or later:", int((fb >= pd.Timestamp("2019-01-01")).sum()))
last = pd.Series({n: S4[len(S4) - 1 - np.argmax(D4["valid"][::-1, j])] for j, n in enumerate(n4) if is400[j]})
print("  last close before 2025-12-01:", int((last < pd.Timestamp("2025-12-01")).sum()))
for y in range(2019, 2026):
    rr = H.thursdays(D4, y); rr = rr[rr < len(S4) - 7]
    print(f"   {y}: S&P 400 names with target/wk {(np.isfinite(D4['y5'][rr]) & D4['elig'][rr])[:, is400].sum(1).mean():.0f}")
r4 = np.concatenate([H.thursdays(D4, y) for y in range(2019, 2026)]); r4 = r4[r4 < len(S4) - 7]
c4 = np.array([n in cur for n in n4])
p2 = np.load(".cache/tree/holdout2_pred_M2.npy").astype(float)
print("  M2 pred shape", p2.shape, "panel", D4["y5"].shape)
ind_ic(D4, r4, c4, "S&P500 cols: in sp500_current, 2019-25", extra=~is400)
if p2.shape == D4["y5"].shape:
    sc_corr(D4, r4, p2, c4, "M2 IPCA score vs current-member (S&P500 cols)", extra=~is400)
    p4 = np.load(".cache/tree/holdout2_pred_M4.npy").astype(float); sc_corr(D4, r4, p4, c4, "M4 SDF score vs current-member (S&P500 cols)", extra=~is400)
