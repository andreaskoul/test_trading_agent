"""H9 forward phase (PREREG Layer 3, Amendment 9): three constructions of the broad trees book, side by side.

    python3 research/tree/h9_forward.py selftest                      # unit tests, synthetic data only
    python3 research/tree/h9_forward.py books --through 2026-11-19    # build the books, append the weekly records
    python3 research/tree/h9_forward.py books --through DATE --h7check   # + the H7 reproduction check (equality only)
    python3 research/tree/h9_forward.py status [--backfill]           # mechanical quantities only

THIS SCRIPT NEVER COMPARES CONSTRUCTIONS' RETURNS. The registered test (F1 - F0, F2 - F0 at matched volatility) is
read once by the coordinator at forward week 104. `books` and `status` print turnover, cost, holdings counts and
neutrality only; gross and net returns are written to the record files and never printed.

Inputs (built by h7_build.py; directory .cache/tree/y2026, or $H9_Y):
  broad_panel.npz                                   S, names, isb, y5, elig, e, r, beta, dv (63-session mean $ volume)
  trees_2025_refit.npy, trees_2026.npy, trees_YYYY.npy   scores; each year from the model fitted on targets before it
  .cache/tree/broad/chunks_raw (<= 2025-12-31), y2026/chunks_raw (after)   unadjusted close and volume

Books (all weights chosen on Thursday t from data <= t, entered at the next close, held 5 sessions, return w . y5 with
y5 clipped at +-1, M1's mask, weeks with >= 50 masked names; carried from January 2025 exactly as h7_read.broad_books
arm H7a: eligible broad names only):
  F0        deciles                     M1 build("decile")                        the H7a book
  F1        rank hysteresis             Q6 build("T1"): enter 10% tails, exit outside 30%
  F2        covariance book             Q4 mvnl_nt: LW2020 mean-variance, dollar- and beta-neutral target, L1 no-trade
                                        region k 2, gross 1
  F0_flat14 F0 at a flat 14 bp a unit traded (the H7 extension; net identical to h7_read's H7a book)

Registered cost (F0, F1, F2), per name and week, as a fraction of AUM:
    cost_i = |dw_i| * ( HS_i + K * sigma_i * sqrt(|dw_i| * AUM / ADV_i) ),   K 0.5, AUM $10M
  HS_i    9.4 / 6.2 / 4.2 bp by the week's dollar-volume tercile (63-session mean, panel `dv`) among eligible broad
          names, smallest / middle / largest, tercile = ceil(3 x percentile rank) as cost_study.py. A traded name that
          is not eligible this week (an exit) is placed by its own dv on the eligible names' scale; no dv -> 9.4 bp.
  sigma_i sd (ddof 1) of the panel's daily return r over the 60 sessions to t; fewer than 40 -> cross-section median
          (Q6_trade/lib.py cost_inputs).
  ADV_i   median of the positive daily unadjusted close x volume over the 20 sessions to t. The panel only holds the
          63-session mean, so the daily series is rebuilt from the raw chunks exactly as h7_build.broad_panel builds
          its own (pivot_table per date and ticker; <= 2025-12-31 from broad/chunks_raw, later from y2026/chunks_raw),
          and checked by reproducing the panel's `dv` from it. No positive day in 20 -> the panel's dv; none either ->
          the 10th percentile of the eligible broad names' ADV (Q6's last resort). Fallbacks are counted per week.

Records: one line per week and construction. Weeks after 2026-11-12 -> F_forward/RECORDS.jsonl (+ WEIGHTS.jsonl);
earlier weeks -> F_forward/BACKFILL_2025_2026.jsonl ("not forward; code check only"). Append-only: an existing
(date, construction) line is never rewritten; a recomputed value that differs from the recorded one is reported as
drift and the run exits non-zero after saving (CLAUDE.md rules 4, 9, 14).
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import sys
import time

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "3")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
Y = os.environ.get("H9_Y", os.environ.get("H7_Y26", os.path.join(ROOT, ".cache", "tree", "y2026")))
BROAD = os.path.join(ROOT, ".cache", "tree", "broad")
FDIR = os.environ.get("H9_OUT", os.path.join(HERE, "F_forward"))
RECORDS = os.path.join(FDIR, "RECORDS.jsonl")
BACKFILL = os.path.join(FDIR, "BACKFILL_2025_2026.jsonl")
WEIGHTS = os.path.join(FDIR, "WEIGHTS.jsonl")
CHECKS = os.path.join(FDIR, "CHECKS.json")
sys.path.insert(0, HERE)

END25 = pd.Timestamp("2025-12-31")
FORWARD_AFTER = pd.Timestamp("2026-11-12")          # forward weeks: Thursdays after this date (Amendment 9)
HS_BP = {1: 9.4, 2: 6.2, 3: 4.2}                    # half-spread by dollar-volume tercile, 1 = smallest
K_IMP, AUM, SIG_WIN, ADV_WIN, DV_WIN = 0.5, 1e7, 60, 20, 63
FLAT = 14e-4
NT_K = 2.0
MIN_NAMES = 50
CONSTRUCTIONS = ("F0", "F1", "F2", "F0_flat14")
NUMERIC = ("gross", "cost_spread", "cost_impact", "net", "turnover", "n_long", "n_short")
BACKFILL_HEADER = {"_header": "NOT FORWARD; CODE CHECK ONLY. Weeks up to 2026-11-12, simulated to test h9_forward.py. "
                              "They are not part of the Amendment 9 forward test and no construction is to be "
                              "compared on them."}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_LIBS = {}


def h7():
    """h7_build, pointed at this script's data folder (Y), so both read the same bars."""
    if "h7" not in _LIBS:
        import h7_build as HB
        HB.Y26 = Y
        _LIBS["h7"] = HB
    return _LIBS["h7"]


def libs():
    """Q6 lib (hysteresis T1), which itself loads Q4 lib (mvnl target) and M1 lib (mask, decile)."""
    if not _LIBS:
        q6 = _mod("q6lib_h9", os.path.join(HERE, "Q6_trade", "lib.py"))
        _LIBS.update(q6=q6, q4=q6.q4, m1=q6.m1)
    return _LIBS["q6"], _LIBS["q4"], _LIBS["m1"]


# ------------------------------------------------------------------------------------------------ inputs
def load_panel():
    z = np.load(os.path.join(Y, "broad_panel.npz"), allow_pickle=False)
    D = {k: z[k] for k in ("y5", "elig", "e", "r", "beta", "dv")}
    D["S"] = pd.DatetimeIndex(z["S"])
    D["names"] = [str(n) for n in z["names"]]
    return D, z["isb"].astype(bool)


def predictions(D):
    """Scores panel: 2025 rows from the 2025 refit, each later year from trees_YYYY.npy (model fitted on targets
    ending before that year). A file whose shape does not match the panel is an input defect (no guess by position)."""
    S, n = D["S"], len(D["names"])
    p = np.full((len(S), n), np.nan)
    used = {}
    for year in range(2025, int(S.year.max()) + 1):
        f = os.path.join(Y, "trees_2025_refit.npy" if year == 2025 else "trees_%d.npy" % year)
        if not os.path.exists(f):
            used[year] = None
            continue
        a = np.load(f, mmap_mode="r")
        if a.shape[1] != n or (a.shape[0] != len(S) and not (year == 2025 and a.shape[0] <= len(S))):
            sys.exit("input_defect: %s has shape %s, panel is %s x %d; rebuild it on this panel with h7_build.py trees"
                     % (os.path.basename(f), a.shape, len(S), n))
        rows = np.where(S.year == year)[0]
        rows = rows[rows < a.shape[0]]
        p[rows] = np.asarray(a[rows], dtype=np.float64)
        used[year] = os.path.basename(f)
    return p, used


def raw_dollar_volume(D, isb, start):
    """Daily unadjusted close x volume for the broad names, sessions S[start:], built as h7_build.broad_panel builds
    the series behind `dv`: pivot_table (mean of duplicate bars) of close and of volume, product; dates <= 2025-12-31
    from broad/chunks_raw, later dates through h7_build.read_chunks("chunks_raw") (the frozen y2026 fetch plus every
    complete forward window fwd_<end>, the earlier bar standing on each overlap session) up to h7_build.fetch_end();
    never chain-linked. The same reader as the panel's, so the dv reproduction check covers the forward windows."""
    HB = h7()
    S = D["S"]
    names = [n for n, b in zip(D["names"], isb) if b]
    want, lo = set(names), str(S[start].date())

    def read(folder, keep):
        out = []
        for f in sorted(glob.glob(os.path.join(folder, "*.parquet"))):
            b = pd.read_parquet(f)
            if len(b):
                b = b[b.ticker.isin(want) & (b.date.astype(str) >= lo)]
                b = b[keep(b.date.astype(str))]
                if len(b):
                    out.append(b)
        return out
    e25 = str(END25.date())
    old = pd.concat(read(os.path.join(BROAD, "chunks_raw"), lambda d: d <= e25))
    old["close"], old["volume"] = old["close"].astype(np.float64), old["volume"].astype(np.float64)
    old["date"] = pd.to_datetime(old["date"])
    new, _ = HB.read_chunks("chunks_raw")
    end = HB.fetch_end()
    new = new[new.ticker.isin(want) & (new.date > END25) & (new.date < end) & (new.date >= pd.Timestamp(lo))]
    rc = pd.concat([old, new])
    idx = S[start:]
    c = rc.pivot_table(index="date", columns="ticker", values="close").reindex(idx).reindex(columns=names)
    v = rc.pivot_table(index="date", columns="ticker", values="volume").reindex(idx).reindex(columns=names)
    return (c * v), names


def cost_inputs(D, isb, rows):
    """Per scored Thursday and name: sigma, ADV ($), half-spread; all from data <= t. Plus the dv reproduction check."""
    S, n = D["S"], len(D["names"])
    start = max(0, int(rows.min()) - 2 * DV_WIN - ADV_WIN)
    dvd, bnames = raw_dollar_volume(D, isb, start)
    bcol = np.where(isb)[0]
    assert [D["names"][i] for i in bcol] == bnames
    # check: the 63-session mean of this daily series is the panel's dv (same raw bars, same construction)
    roll = dvd.rolling(DV_WIN, min_periods=DV_WIN).mean().to_numpy()
    ref = D["dv"][start:][:, bcol].astype(np.float64)
    sl = slice(DV_WIN - 1, None)
    a, b = roll[sl], ref[sl]
    fa, fb = np.isfinite(a), np.isfinite(b)
    both = fa & fb
    pos = both & (np.abs(b) > 0)                               # zero-volume windows: dv = 0 exactly, compared absolutely
    rel = np.abs(a[pos] / b[pos] - 1)                          # panel dv is float32: ~1e-7 relative
    zero_abs = float(np.abs(a[both & ~pos]).max()) if (both & ~pos).any() else 0.0
    dvcheck = {"cells_compared": int(both.sum()), "cells_dv_zero": int((both & ~pos).sum()),
               "nan_pattern_mismatch_cells": int((fa != fb).sum()),
               "max_rel_diff": float(rel.max()) if pos.any() else None, "max_abs_where_dv_zero": zero_abs,
               "pass": bool((fa != fb).sum() == 0 and pos.any() and rel.max() < 1e-5 and zero_abs < 1e-6)}
    d = dvd.to_numpy()
    r = D["r"]
    SIG, ADV, HSA = np.zeros((len(rows), n)), np.full((len(rows), n), np.nan), np.zeros((len(rows), n))
    FB = np.zeros((len(rows), n), np.int8)                    # 0 = 20-session median, 1 = panel dv, 2 = 10th percentile
    for j, t in enumerate(rows):
        rr = r[t - SIG_WIN + 1:t + 1].astype(np.float64)
        with np.errstate(all="ignore"):
            s = np.nanstd(rr, 0, ddof=1)
        ok = np.isfinite(rr).sum(0) >= 40
        s[~ok] = np.nanmedian(s[ok])
        SIG[j] = s
        w = d[t - start - ADV_WIN + 1:t - start + 1]
        with np.errstate(all="ignore"):
            adv_b = np.nanmedian(np.where(w > 0, w, np.nan), 0)
        adv = np.full(n, np.nan)
        adv[bcol] = adv_b
        dvt = D["dv"][t].astype(np.float64)
        m1_ = ~np.isfinite(adv) & np.isfinite(dvt) & (dvt > 0)
        adv[m1_] = dvt[m1_]
        FB[j][m1_] = 1
        el = D["elig"][t] & isb
        m2_ = ~np.isfinite(adv)
        adv[m2_] = np.nanpercentile(adv[el & ~m2_], 10)
        FB[j][m2_] = 2
        ADV[j] = adv
        HSA[j] = half_spread(dvt, el)
    return SIG, ADV, HSA, FB, dvcheck


def half_spread(dv, el):
    """Half-spread per name: tercile = ceil(3 x share of eligible broad names with dv <= the name's dv), clipped to
    1..3 (cost_study.py's ceil(3 x percentile rank)); names without a dv get the smallest tercile's spread."""
    e = el & np.isfinite(dv)
    vals = np.sort(dv[e])
    k = np.searchsorted(vals, np.nan_to_num(dv, nan=-np.inf), side="right")
    terc = np.clip(-(-3 * k // max(len(vals), 1)), 1, 3)
    return np.array([HS_BP[1], HS_BP[1], HS_BP[2], HS_BP[3]])[terc] * 1e-4


# ------------------------------------------------------------------------------------------------ cost and simulation
def trade_cost(dw, sig, adv, hs, aum=AUM, k=K_IMP):
    """(spread, impact) per name, fractions of AUM, for trades dw (fractions of AUM)."""
    a = np.abs(dw)
    return a * hs, a * k * sig * np.sqrt(a * aum / adv)


def simulate(W, D, rows, SIG, ADV, HSA, FB=None, flat=None):
    """Weekly records for one weight panel. flat=None: registered model; flat=x: x per unit traded (M1.simulate)."""
    prev = np.zeros(W.shape[1])
    out = []
    for j, t in enumerate(rows):
        w = W[j]
        y = np.nan_to_num(D["y5"][t])
        g = float(w @ y)
        dw = w - prev
        tot = float(np.abs(dw).sum())
        if flat is None:
            sp, im = trade_cost(dw, SIG[j], ADV[j], HSA[j])
            cs, ci = float(sp.sum()), float(im.sum())
            net = g - (cs + ci)
        else:
            cs, ci = flat * tot, 0.0
            net = g - flat * tot
        tr = dw != 0
        beta = np.nan_to_num(D["beta"][t].astype(np.float64), nan=1.0)
        out.append({"gross": g, "cost_spread": cs, "cost_impact": ci, "net": net, "turnover": tot / 2,
                    "n_long": int((w > 0).sum()), "n_short": int((w < 0).sum()),
                    "gross_weight": float(np.abs(w).sum()), "net_weight": float(w.sum()), "beta_exposure": float(w @ beta),
                    "names_traded": int(tr.sum()),
                    "adv_fallback_traded": int((FB[j][tr] > 0).sum()) if FB is not None and flat is None else 0})
        prev = w
    return out


# ------------------------------------------------------------------------------------------------ constructions
def build_f2(scores, D, rows, q4, m1, progress=False):
    """Q4 mvnl_nt (lib.build with {"target": "mvnl", "nt": 2.0}), the same statements, with the covariance cache
    emptied each week (the broad panel's matrices are ~100 MB each). Also returns the target's neutrality per week."""
    n = scores.shape[1]
    W = np.zeros((len(rows), n))
    prev = np.zeros(n)
    tgt = []
    for j, t in enumerate(rows):
        m = m1.mask(scores, D, t)
        x = q4.t_mvnl(scores[t], m, D, t)
        beta = np.nan_to_num(D["beta"][t].astype(np.float64), nan=1.0)
        tgt.append((float(x.sum()), float(x @ beta), float(np.abs(x).sum())))
        if j > 0:
            dl = NT_K * np.abs(x[x != 0]).mean()
            p = np.where(m, prev, 0.0)
            x = np.where(m, np.clip(p, x - dl, x + dl), 0.0)
            x = x / np.abs(x).sum()
        prev = x.copy()
        W[j] = x
        q4._COV.clear()
        if progress and (j % 10 == 0 or j == len(rows) - 1):
            log("F2 week", j + 1, "of", len(rows))
    return W, np.array(tgt)


def build_all(through=None, progress=True):
    q6, q4, m1 = libs()
    D, isb = load_panel()
    S = D["S"]
    p, used = predictions(D)
    elig_b = D["elig"] & isb[None, :]
    Dc = dict(D)
    Dc["elig"] = elig_b
    Dc["y5"] = np.clip(D["y5"], -1.0, 1.0)
    s = np.where(elig_b, p, np.nan)
    th = np.where((S.weekday == 3) & (S.year >= 2025))[0]
    if through is not None:
        th = th[S[th] <= pd.Timestamp(through)]
    nm = {int(t): int(m1.mask(s, Dc, t).sum()) for t in th}
    rows = np.array([t for t in th if nm[int(t)] >= MIN_NAMES])
    # input contracts on the forward Thursdays whose 5-session target is complete (rule 2, rule 3)
    defects = []
    for t in th:
        if S[t] <= FORWARD_AFTER or t + 6 > len(S) - 1:
            continue
        ne, ns = int(elig_b[t].sum()), int((np.isfinite(s[t])).sum())
        if ne < 1400:
            defects.append({"date": str(S[t].date()), "defect": "eligible broad names %d < 1400" % ne})
        if ns < 0.9 * max(ne, 1):
            defects.append({"date": str(S[t].date()), "defect": "scored names %d < 90%% of eligible %d (scores file: %s)"
                            % (ns, ne, used.get(int(S[t].year)))})
        if nm[int(t)] < MIN_NAMES:
            defects.append({"date": str(S[t].date()), "defect": "no book: %d masked names" % nm[int(t)]})
    if progress:
        log("panel", str(S[0].date()), "..", str(S[-1].date()), "| scores", used, "| weeks", len(rows),
            str(S[rows[0]].date()), "..", str(S[rows[-1]].date()))
    SIG, ADV, HSA, FB, dvcheck = cost_inputs(D, isb, rows)
    if progress:
        log("cost inputs built; dv reproduction", dvcheck)
    W = {"F0": m1.build("decile", s, Dc, rows), "F1": q6.build("T1", s, Dc, rows)}
    W["F2"], tgt = build_f2(s, Dc, rows, q4, m1, progress)
    sims = {k: simulate(W[k], Dc, rows, SIG, ADV, HSA, FB) for k in ("F0", "F1", "F2")}
    sims["F0_flat14"] = simulate(W["F0"], Dc, rows, SIG, ADV, HSA, flat=FLAT)
    return {"D": Dc, "isb": isb, "rows": rows, "W": W, "sims": sims, "tgt": tgt, "dvcheck": dvcheck, "defects": defects,
            "used": used, "scores": s}


# ------------------------------------------------------------------------------------------------ records
def read_jsonl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def append_records(path, recs, header=None):
    """Append the records whose (date, construction) is not in the file; never rewrite. Returns (appended, drift)."""
    old = {(r["date"], r["construction"]): r for r in read_jsonl(path) if "date" in r}
    new, drift = [], []
    for r in recs:
        k = (r["date"], r["construction"])
        if k not in old:
            new.append(r)
            continue
        for f in NUMERIC:
            if abs(float(old[k][f]) - float(r[f])) > 1e-9:
                drift.append({"date": k[0], "construction": k[1], "field": f})
    if new or (header and not os.path.exists(path)):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        first = not os.path.exists(path)
        with open(path, "a") as fh:
            if first and header:
                fh.write(json.dumps(header) + "\n")
            for r in new:
                fh.write(json.dumps(r) + "\n")
    return len(new), drift


def cmd_books(args):
    B = build_all(args.through)
    D, rows, S = B["D"], B["rows"], B["D"]["S"]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fwd, back, wts = [], [], []
    names = np.array(D["names"])
    for j, t in enumerate(rows):
        date = S[t]
        forward = date > FORWARD_AFTER
        for c in CONSTRUCTIONS:
            r = {"date": str(date.date()), "construction": c}
            r.update(B["sims"][c][j])
            r.update({"cost_model": "flat 14 bp" if c == "F0_flat14" else "tercile half-spread + sqrt impact (K 0.5, $10M)",
                      "phase": "forward" if forward else "backfill: not forward; code check only", "written": stamp})
            (fwd if forward else back).append(r)
        if forward:
            for c in ("F0", "F1", "F2"):
                w = B["W"][c][j]
                nz = np.where(w != 0)[0]
                wts.append({"date": str(date.date()), "construction": c, "names": names[nz].tolist(),
                            "w": [float(x) for x in w[nz]]})
    os.makedirs(FDIR, exist_ok=True)
    nb, db = (0, []) if args.no_backfill else append_records(BACKFILL, back, BACKFILL_HEADER)
    nf, df = append_records(RECORDS, fwd)
    have = {(r["date"], r["construction"]) for r in read_jsonl(WEIGHTS)}
    wnew = [w for w in wts if (w["date"], w["construction"]) not in have]
    if wnew:
        with open(WEIGHTS, "a") as fh:
            for w in wnew:
                fh.write(json.dumps(w) + "\n")
    # ---- mechanical checks (no return of any construction is printed or compared)
    sims, tgt = B["sims"], B["tgt"]

    def mx(c, f):
        return float(np.max(np.abs([r[f] for r in sims[c]])))
    chk = {"run": stamp, "through": args.through, "weeks_simulated": int(len(rows)),
           "first_week": str(S[rows[0]].date()), "last_week": str(S[rows[-1]].date()),
           "forward_weeks": int(sum(S[t] > FORWARD_AFTER for t in rows)),
           "dv_reproduction": B["dvcheck"],
           "dollar_neutral_max_abs_net_weight": {c: mx(c, "net_weight") for c in ("F0", "F1", "F2")},
           "beta_exposure_max_abs": {c: mx(c, "beta_exposure") for c in ("F0", "F1", "F2")},
           "gross_weight_min_max": {c: [float(min(r["gross_weight"] for r in sims[c])),
                                        float(max(r["gross_weight"] for r in sims[c]))] for c in ("F0", "F1", "F2")},
           "F2_target_max_abs_net_weight": float(np.abs(tgt[:, 0]).max()),
           "F2_target_max_abs_beta_exposure": float(np.abs(tgt[:, 1]).max()),
           "F2_target_gross_min_max": [float(tgt[:, 2].min()), float(tgt[:, 2].max())],
           "adv_fallback_share_of_traded_names": {
               c: float(sum(r["adv_fallback_traded"] for r in sims[c]) / max(1, sum(r["names_traded"] for r in sims[c])))
               for c in ("F0", "F1", "F2")},
           "appended": {"forward_records": nf, "backfill_records": nb, "forward_weight_lines": len(wnew)},
           "drift_vs_recorded": {"forward": df[:20], "backfill": db[:20], "n_forward": len(df), "n_backfill": len(db)},
           "input_defects": B["defects"]}
    tol = 1e-9
    chk["pass"] = {"dv_reproduction": chk["dv_reproduction"]["pass"],
                   "F0_dollar_neutral": chk["dollar_neutral_max_abs_net_weight"]["F0"] < tol,
                   "F1_dollar_neutral": chk["dollar_neutral_max_abs_net_weight"]["F1"] < tol,
                   "F2_target_dollar_neutral": chk["F2_target_max_abs_net_weight"] < tol,
                   "F2_target_beta_neutral": chk["F2_target_max_abs_beta_exposure"] < tol,
                   "F2_gross_1": abs(chk["gross_weight_min_max"]["F2"][0] - 1) < tol and abs(chk["gross_weight_min_max"]["F2"][1] - 1) < tol,
                   "adv_fallback_under_2pct": all(v < 0.02 for v in chk["adv_fallback_share_of_traded_names"].values()),
                   "no_drift": not df and not db, "no_input_defect": not B["defects"]}
    if args.h7check:
        chk["h7_reproduction"] = h7_check(B)
        chk["pass"]["h7_reproduction"] = chk["h7_reproduction"]["pass"]
    json.dump(chk, open(CHECKS, "w"), indent=1)
    print(json.dumps(chk, indent=1))
    if read_jsonl(RECORDS):
        mechanical(read_jsonl(RECORDS), "forward (RECORDS.jsonl)")
    else:
        mechanical(read_jsonl(BACKFILL), "backfill, not forward")
    bad = [k for k, v in chk["pass"].items() if not v]
    if bad:                                                    # quality gate: after saving (rule 9)
        sys.exit("QUALITY GATE FAILED (records were saved first): " + ", ".join(bad))


def h7_check(B):
    """F0 at flat 14 bp against h7_read.broad_books() arm H7a, 2026 weeks: equality of the weekly net series to 1e-10.
    Only the equality is reported; no return is printed."""
    import h7_read as H7
    out, _ = H7.broad_books()
    ref = out["H7a"]
    S, rows = B["D"]["S"], B["rows"]
    mine = pd.Series([r["net"] for r in B["sims"]["F0_flat14"]], index=S[rows])
    mine = mine[(mine.index.year == 2026) & (mine.index <= ref.index.max())]
    same_dates = bool(len(mine) == len(ref) and (mine.index == ref.index).all())
    d = float(np.abs(mine.values - ref.net.values).max()) if same_dates else None
    tr = pd.Series([r["turnover"] for r in B["sims"]["F0_flat14"]], index=S[rows]).reindex(ref.index)
    return {"weeks_compared": int(len(ref)), "same_dates": same_dates, "max_abs_diff_weekly_net": d,
            "max_abs_diff_weekly_turnover": float(np.abs(tr.values - ref.turn.values).max()) if same_dates else None,
            "pass": bool(same_dates and d is not None and d < 1e-10)}


# ------------------------------------------------------------------------------------------------ status
def mechanical(recs, label):
    """Turnover, realised cost and holdings counts per construction. No gross or net return is shown."""
    recs = [r for r in recs if "date" in r]
    if not recs:
        print("no records (%s)" % label)
        return
    df = pd.DataFrame(recs)
    print("\nMechanical quantities, %s: %d weeks, %s .. %s. Turnover is one-way (sum|dw| / 2) per week. Costs in bp of AUM "
          "per week and %% per year. The first week of a file that starts at the book's first week includes the entry."
          % (label, df.date.nunique(), df.date.min(), df.date.max()))
    rows = []
    for c in CONSTRUCTIONS:
        g = df[df.construction == c]
        if not len(g):
            continue
        cost = g.cost_spread + g.cost_impact
        rows.append({"construction": c, "weeks": len(g), "turnover_wk": round(g.turnover.mean(), 4),
                     "spread_bp_wk": round(1e4 * g.cost_spread.mean(), 3), "impact_bp_wk": round(1e4 * g.cost_impact.mean(), 3),
                     "cost_bp_wk": round(1e4 * cost.mean(), 3), "cost_pct_yr": round(52 * 100 * cost.mean(), 2),
                     "cost_bp_per_unit_traded": round(1e4 * cost.sum() / (2 * g.turnover.sum()), 2),
                     "n_long": round(g.n_long.mean(), 1), "n_short": round(g.n_short.mean(), 1),
                     "gross_weight": round(g.gross_weight.mean(), 4)})
    print(pd.DataFrame(rows).to_string(index=False))


def cmd_status(args):
    mechanical(read_jsonl(RECORDS), "forward (RECORDS.jsonl)")
    if args.backfill:
        b = read_jsonl(BACKFILL)
        mechanical(b, "backfill, not forward (all weeks)")
        mechanical([r for r in b if r.get("date", "") >= "2025-01-16"], "backfill, not forward (entry week dropped)")


# ------------------------------------------------------------------------------------------------ unit tests
def cmd_selftest(args):
    import tempfile
    res = {}
    rng = np.random.default_rng(0)
    n = 40
    sig, adv, hs = rng.uniform(.01, .04, n), rng.uniform(1e6, 1e8, n), np.full(n, 6.2e-4)
    # 1. zero trade -> zero cost
    sp, im = trade_cost(np.zeros(n), sig, adv, hs)
    res["zero_trade_zero_cost"] = bool(sp.sum() == 0 and im.sum() == 0)
    # 2. 4x the trade -> 2x the impact per unit traded, 8x in total; spread per unit unchanged
    dw = rng.normal(0, .01, n)
    sp1, im1 = trade_cost(dw, sig, adv, hs)
    sp4, im4 = trade_cost(4 * dw, sig, adv, hs)
    res["4x_trade_2x_impact_per_unit"] = bool(np.allclose((im4 / np.abs(4 * dw)) / (im1 / np.abs(dw)), 2.0, rtol=1e-12))
    res["4x_trade_8x_impact_total"] = bool(np.isclose(im4.sum() / im1.sum(), 8.0, rtol=1e-12))
    res["spread_linear"] = bool(np.allclose(sp4, 4 * sp1, rtol=1e-12) and np.allclose(sp1, np.abs(dw) * hs))
    # 3. a known value: 1% of AUM, sigma 2%, ADV $10M -> trade = 1% of ADV, impact per unit = 0.5 x 0.02 x 0.1 = 10 bp
    s_, i_ = trade_cost(np.array([0.01]), np.array([0.02]), np.array([1e7]), np.array([4.2e-4]))
    res["known_value"] = bool(np.isclose(i_[0], 0.01 * 10e-4) and np.isclose(s_[0], 0.01 * 4.2e-4))
    # 4. half-spread terciles: 9 eligible names, one ineligible low, one ineligible high, one without dv
    dv = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0.5, 100, np.nan], float)
    el = np.array([True] * 9 + [False] * 3)
    h = half_spread(dv, el) * 1e4
    res["half_spread_terciles"] = bool(np.allclose(h, [9.4] * 3 + [6.2] * 3 + [4.2] * 3 + [9.4, 4.2, 9.4]))
    pct = pd.Series(dv[:9]).rank(pct=True).to_numpy()
    res["terciles_equal_cost_study_rule"] = bool((np.ceil(pct * 3).clip(1, 3) == np.array([1, 1, 1, 2, 2, 2, 3, 3, 3])).all())
    # 5. simulator: holding the same weights two weeks costs nothing in week 2; flat cost = M1.simulate
    q6, q4, m1 = libs()
    T, N = 420, 60
    D = {"y5": rng.normal(0, .03, (T, N)).astype(np.float32), "elig": np.ones((T, N), bool),
         "e": rng.normal(0, .02, (T, N)).astype(np.float32), "beta": rng.uniform(.5, 1.5, (T, N)).astype(np.float32)}
    D["elig"][:, -5:] = rng.random((T, 5)) > 0.3
    rows = np.arange(300, 400, 5)
    sc = np.full((T, N), np.nan)
    sc[rows] = rng.normal(size=(len(rows), N))
    ones = np.ones((len(rows), N))
    W0 = m1.build("decile", sc, D, rows)
    Wh = np.repeat(W0[:1], len(rows), 0)
    sim = simulate(Wh, D, rows, ones * .02, ones * 1e7, ones * 6.2e-4)
    res["held_book_costs_nothing"] = bool(all(r["cost_spread"] == 0 and r["cost_impact"] == 0 and r["turnover"] == 0 for r in sim[1:])
                                          and sim[0]["cost_spread"] > 0)
    m1.COST = FLAT
    ref = m1.simulate(W0, D, rows)
    mine = simulate(W0, D, rows, None, None, None, flat=FLAT)
    res["flat14_equals_M1_simulate"] = bool(np.array_equal(ref["net"], [r["net"] for r in mine])
                                            and np.array_equal(ref["turn"], [r["turnover"] for r in mine]))
    # 6. F2 loop == Q4 lib.build mvnl_nt (the registered construction), exactly; neutral target
    Wq = q4.build({"target": "mvnl", "nt": NT_K}, sc, D, rows)[0]
    q4._COV.clear()
    W2, tgt = build_f2(sc, D, rows, q4, m1)
    res["F2_equals_q4_build_mvnl_nt"] = bool(np.array_equal(Wq, W2))
    res["F2_target_neutral"] = bool(np.abs(tgt[:, :2]).max() < 1e-10 and np.allclose(tgt[:, 2], 1))
    res["F2_gross_1"] = bool(np.allclose(np.abs(W2).sum(1), 1))
    # 7. F1 hysteresis: dollar-neutral, sides 0.5; a name that entered stays while inside 30%, leaves outside
    W1 = q6.build("T1", sc, D, rows)
    res["F1_sides_half"] = bool(np.allclose(W1[W1 > 0].reshape(-1).sum() / len(rows), .5) and np.abs(W1.sum(1)).max() < 1e-12)
    ok = True
    for j in range(1, len(rows)):
        m = m1.mask(sc, D, rows[j])
        pr = q6.pct_rank(sc[rows[j]], m)
        was, now = W1[j - 1] > 0, W1[j] > 0
        ok &= bool((now == (m & ((pr > .9) | (was & (pr > .7))))).all())
    res["F1_enter10_exit30_rule"] = ok
    # 8. records: append-only and idempotent; a changed value is reported as drift and not written
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "r.jsonl")
        recs = [dict(date="2026-11-19", construction=c, gross=.1, cost_spread=.01, cost_impact=.02, net=.07, turnover=.4,
                     n_long=3, n_short=3) for c in CONSTRUCTIONS]
        a1 = append_records(f, recs, {"_header": "x"})
        h1 = hashlib.sha256(open(f, "rb").read()).hexdigest()
        a2 = append_records(f, recs, {"_header": "x"})
        ch = [dict(r, net=.08) for r in recs] + [dict(recs[0], date="2026-12-03")]
        a3 = append_records(f, ch)
        lines = read_jsonl(f)
        res["append_idempotent"] = bool(a1 == (4, []) and a2 == (0, []) and h1 == hashlib.sha256(
            "\n".join(open(f).read().split("\n")[:5]).encode() + b"\n").hexdigest())
        res["drift_reported_not_overwritten"] = bool(a3[0] == 1 and len(a3[1]) == 4 and len(lines) == 6
                                                     and all(l["net"] == .07 for l in lines[1:5]))
    print(json.dumps(res, indent=1))
    if not all(res.values()):
        sys.exit("SELFTEST FAILED: " + ", ".join(k for k, v in res.items() if not v))
    print("selftest: %d of %d passed" % (sum(res.values()), len(res)))


# ------------------------------------------------------------------------------------------------ frozen-field checks
FROZEN_FIELDS = ("elig", "Z", "valid", "r", "e", "beta", "rm", "spy", "dv")


def panel_equal(old_path, new_path):
    """Every frozen field of the new panel equals the old one on the old panel's sessions and names (by name, not by
    position: a name first eligible in a new week can change the column order). y5 must equal wherever the old one is
    finite (cells whose 5-session window ran past the old end become finite; counted). y5_delist is reported only."""
    zo, zn = np.load(old_path, allow_pickle=False), np.load(new_path, allow_pickle=False)
    So, Sn = pd.DatetimeIndex(zo["S"]), pd.DatetimeIndex(zn["S"])
    no, nn = [str(x) for x in zo["names"]], [str(x) for x in zn["names"]]
    out = {"old_sessions": [str(So[0].date()), str(So[-1].date()), len(So)],
           "new_sessions": [str(Sn[0].date()), str(Sn[-1].date()), len(Sn)],
           "sessions_prefix_equal": bool(len(Sn) >= len(So) and (Sn[:len(So)] == So).all()),
           "old_names_missing_in_new": sorted(set(no) - set(nn))[:20], "new_names": len(set(nn) - set(no))}
    ok = out["sessions_prefix_equal"] and not out["old_names_missing_in_new"]
    j = pd.Index(nn).get_indexer(no)
    T = len(So)
    out["isb_equal"] = bool(np.array_equal(zo["isb"], zn["isb"][j]))
    ok &= out["isb_equal"]
    for k in FROZEN_FIELDS + ("y5", "y5_delist"):
        a = zo[k]
        b = zn[k][:T] if a.ndim == 1 else zn[k][:T][:, j]
        if k in ("y5", "y5_delist"):
            f = np.isfinite(a)
            r = {"equal_where_old_finite": bool(np.array_equal(a[f], b[f])),
                 "old_finite_now_nan": int((f & ~np.isfinite(b)).sum()),
                 "newly_finite_cells": int((~f & np.isfinite(b)).sum())}
            if k == "y5":
                ok &= r["equal_where_old_finite"] and r["old_finite_now_nan"] == 0
        else:
            r = {"equal": bool(np.array_equal(a, b, equal_nan=a.dtype.kind == "f"))}
            ok &= r["equal"]
        out[k] = r
    out["pass"] = bool(ok)
    return out


def cmd_panelcheck(args):
    r = panel_equal(args.old, args.new)
    print(json.dumps(r, indent=1))
    if not r["pass"]:
        sys.exit("PANEL CHECK FAILED: a frozen field changed")


def trees_equal(old, new, old_panel, new_panel, tol=1e-6):
    """Scores of the refit on the extended panel equal the previous file on every row it had scores for, by name."""
    zo, zn = np.load(old_panel, allow_pickle=False), np.load(new_panel, allow_pickle=False)
    no, nn = [str(x) for x in zo["names"]], [str(x) for x in zn["names"]]
    a, b = np.load(old), np.load(new)
    j = pd.Index(nn).get_indexer(no)
    rows = np.where(np.isfinite(a).any(1))[0]
    A, B = a[rows].astype(np.float64), b[rows][:, j].astype(np.float64)
    fa, fb = np.isfinite(A), np.isfinite(B)
    both = fa & fb
    d = float(np.abs(A[both] - B[both]).max()) if both.any() else None
    newrows = int(np.isfinite(b).any(1).sum()) - len(rows)
    r = {"rows_compared": int(len(rows)), "nan_pattern_mismatch_cells": int((fa != fb).sum()), "max_abs_diff": d,
         "new_scored_rows": newrows, "tolerance": tol,
         "pass": bool(len(rows) > 0 and (fa != fb).sum() == 0 and d is not None and d <= tol)}
    return r


def cmd_treescheck(args):
    r = trees_equal(args.old, args.new, args.old_panel, args.new_panel)
    print(json.dumps(r, indent=1))
    if not r["pass"]:
        sys.exit("TREES CHECK FAILED: the refit does not reproduce the previous scores")


def cmd_fwdtest(args):
    """End to end on SYNTHETIC bars, in $H9_SCRATCH only (never the data cache): a scratch y2026 folder links the
    frozen chunks and holds one fake forward window fwd_2026-11-13 (overlap session 2026-11-12, then 2026-11-13):
    adjusted closes = the frozen 2026-11-12 closes x 0.5 on the overlap, x 0.5 x 1.01 on 2026-11-13 (a different
    adjustment scale, as a dividend inside the window would give); raw bars = the frozen 2026-11-12 raw bars on both.
    Then sp_panel, broad_panel and trees 2026 are run into the scratch folder, and it checks:
      * fetch windows chain; the panel gains exactly 2026-11-13;
      * every frozen field of the new panel equals the current panel on 2009-01-02 .. 2026-11-12 (panelcheck);
      * chain-linking: every broad name's 2026-11-13 return r is 1% (the fake 0.5 scale is removed);
      * the trees refit reproduces trees_2026.npy on every scored row (treescheck).
    No book is simulated on the synthetic window."""
    import shutil
    import subprocess
    scr = os.environ.get("H9_SCRATCH")
    if not scr:
        sys.exit("set H9_SCRATCH to an empty scratch folder")
    real = Y
    y = os.path.join(scr, "y2026")
    if os.path.exists(y):
        shutil.rmtree(y)
    os.makedirs(y)
    for f in ("chunks", "chunks_raw", "_fetch_all.json", "_fetch_raw.json", "trees_2025_refit.npy",
              "master_h5_2026.npy"):
        os.symlink(os.path.join(real, f), os.path.join(y, f))
    d0, d1 = pd.Timestamp("2026-11-12"), pd.Timestamp("2026-11-13")
    w = os.path.join(y, "fwd_2026-11-13")
    for sub, adj in (("chunks", "all"), ("chunks_raw", "raw")):
        os.makedirs(os.path.join(w, sub))
        for f in sorted(glob.glob(os.path.join(real, sub, "*.parquet"))):
            b = pd.read_parquet(f)
            b = b[b.date.astype(str) == str(d0.date())]
            if not len(b):
                continue
            b0, b1 = b.copy(), b.copy()
            b1["date"] = str(d1.date())
            if sub == "chunks":
                b0["close"] = b0["close"] * 0.5
                b1["close"] = b1["close"] * 0.5 * 1.01
            pd.concat([b0, b1]).to_parquet(os.path.join(w, sub, os.path.basename(f)))
        json.dump({"end": str(d1.date()), "start": str(d0.date()), "adj": adj, "complete": True, "synthetic": True},
                  open(os.path.join(w, "_fetch_%s.json" % adj), "w"))
    env = dict(os.environ, H7_Y26=y, H9_Y=y, H7_OUTD=os.path.join(scr, "h7_checks"), OMP_NUM_THREADS="3")
    os.makedirs(env["H7_OUTD"], exist_ok=True)
    qt = os.path.expanduser("~/.cache/quant-tf-venv/bin/python")
    hb = os.path.join(HERE, "h7_build.py")
    res = {}
    for name, cmd in (("sp_panel", [qt, hb, "sp_panel"]), ("broad_panel", [sys.executable, hb, "broad_panel"]),
                      ("trees_2026", [sys.executable, hb, "trees", "2026"])):
        log("fwdtest:", name)
        p = subprocess.run(cmd, env=env, capture_output=True, text=True)
        open(os.path.join(scr, name + ".log"), "w").write(p.stdout + p.stderr)
        res[name + "_exit"] = p.returncode
        if p.returncode:
            print(json.dumps(res, indent=1))
            sys.exit("fwdtest: %s failed, see %s" % (name, os.path.join(scr, name + ".log")))
    pe = panel_equal(os.path.join(real, "broad_panel.npz"), os.path.join(y, "broad_panel.npz"))
    res["panelcheck"] = {k: pe[k] for k in ("old_sessions", "new_sessions", "sessions_prefix_equal", "pass")}
    res["panelcheck"]["fields_equal"] = {k: pe[k].get("equal", pe[k].get("equal_where_old_finite")) for k in FROZEN_FIELDS + ("y5",)}
    z = np.load(os.path.join(y, "broad_panel.npz"), allow_pickle=False)
    S = pd.DatetimeIndex(z["S"])
    isb = z["isb"]
    t1 = int(np.where(S == d1)[0][0]) if (S == d1).any() else None
    res["panel_gains_exactly_2026_11_13"] = bool(t1 == len(S) - 1 and len(S) == pe["old_sessions"][2] + 1)
    if t1 is not None:
        r1 = z["r"][t1].astype(np.float64)
        m = isb & np.isfinite(r1) & np.isfinite(z["r"][t1 - 1])
        dev = np.abs(r1[m] - 0.01)
        res["chain_link_r_2026_11_13"] = {"broad_names": int(m.sum()), "max_abs_dev_from_1pct": float(dev.max()),
                                          "pass": bool(m.sum() > 1000 and dev.max() < 1e-5)}
    tc = trees_equal(os.path.join(real, "trees_2026.npy"), os.path.join(y, "trees_2026.npy"),
                     os.path.join(real, "broad_panel.npz"), os.path.join(y, "broad_panel.npz"))
    res["treescheck"] = tc
    sc = json.load(open(os.path.join(env["H7_OUTD"], "CHECKS.json"))).get("step3_forward_windows")
    res["forward_window_link_counts"] = sc
    ok = (pe["pass"] and res["panel_gains_exactly_2026_11_13"] and res.get("chain_link_r_2026_11_13", {}).get("pass")
          and tc["pass"])
    res["pass"] = bool(ok)
    json.dump(res, open(os.path.join(scr, "FWDTEST.json"), "w"), indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
    if not ok:
        sys.exit("FWDTEST FAILED")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("books")
    b.add_argument("--through", required=True, help="last Thursday (YYYY-MM-DD) to simulate and record")
    b.add_argument("--h7check", action="store_true", help="also check F0 at flat 14 bp against h7_read.broad_books()")
    b.add_argument("--no-backfill", action="store_true", help="do not touch BACKFILL_2025_2026.jsonl (the weekly job)")
    pc = sub.add_parser("panelcheck", help="frozen fields of NEW equal OLD on OLD's sessions and names")
    pc.add_argument("--old", required=True)
    pc.add_argument("--new", required=True)
    tc = sub.add_parser("treescheck", help="trees scores of NEW equal OLD on OLD's rows, aligned by name")
    tc.add_argument("--old", required=True)
    tc.add_argument("--new", required=True)
    tc.add_argument("--old-panel", required=True)
    tc.add_argument("--new-panel", required=True)
    sub.add_parser("fwdtest", help="end-to-end test of a forward window on synthetic bars, in the scratch folder $H9_SCRATCH")
    s = sub.add_parser("status")
    s.add_argument("--backfill", action="store_true", help="also show the pre-forward code-check weeks")
    sub.add_parser("selftest")
    a = ap.parse_args()
    {"books": cmd_books, "status": cmd_status, "selftest": cmd_selftest, "panelcheck": cmd_panelcheck,
     "treescheck": cmd_treescheck, "fwdtest": cmd_fwdtest}[a.cmd](a)


if __name__ == "__main__":
    main()
