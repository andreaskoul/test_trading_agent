"""Timestral (Mistral, zero-shot) on the S&P 500 read and the 31-name news panel (PREREG_quant_transformers.md
Amendment 3).

    python timestral_sp500.py smoke     # 10 Thursdays of 2012 (a training-period year) on the S&P harness and 5 of
                                        # 2017 on the panel: coverage, sample inputs/outputs, reproducibility
    python timestral_sp500.py devcheck  # MPS vs CPU scores on 4 Thursdays of 2012 (must agree before MPS is used)
    python timestral_sp500.py run       # T1: every Thursday 2013-25 (refuses unless Amendment 3 is signed + pushed)
    python timestral_sp500.py score     # T1: the one read -> SP500_TIMESTRAL.md (Holm over 3), strategies table
    python timestral_sp500.py news      # T2: +/- news on the panel, 2018-25 (descriptive) -> TIMESTRAL_NEWS.md

The input mirrors zero-shot Chronos-2 in sp500_transformers.chronos_scores: per name the daily residual series as
target, the five z-scored signals as past covariates, context 512, the score at h is the sum of median steps 1..h
(step 0 is session d+1, skipped: the target runs d+2..d+1+h).
Library defaults (symmetric averaging on); clip_nonnegative off (residuals are signed, so it never binds anyway).
"""

import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import features as F
import panel as P
import sp500_test as T
import sp500_transformers as X

REPO, REV = "mistralai/Timestral-209M", None            # weights: the hub's current revision, recorded in each part
CODE = "a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff"     # github.com/mistralai/timestral, pinned (requirements-quant.txt)
OUT = os.path.join(P.REPORT, "SP500_TIMESTRAL.md")
PART = os.path.join(P.CACHE, "sp500_tf_timestral.npz")
NEWS_OUT = os.path.join(P.REPORT, "TIMESTRAL_NEWS.md")
CHUNK = 128
_M = None


DEVICE = os.environ.get("TIMESTRAL_DEVICE", "mps")     # verified against CPU in `devcheck` before use


def _mps_safe():
    """MPS has no float64. Timestral uses it only in its scaler bookkeeping (causal Welford mean/std per patch, and
    the multi-patch refine, which a 21-step forecast never reaches). Run exactly those on CPU, in float64 as the
    library does, and move the float32 results back; the network itself stays on the GPU."""
    import timestral.forecaster as tf
    import timestral.model as tm
    import timestral.scaler as ts
    if getattr(ts, "_mps_safe", False):
        return
    orig = ts.causal_patch_loc_scale

    def cpls(data, mask, *a, **k):
        loc, scale = orig(data.cpu(), mask.cpu(), *a, **k)
        return loc.to(data.device), scale.to(data.device)
    tm.causal_patch_loc_scale = tf.causal_patch_loc_scale = cpls
    refine = tf.TimestralForecaster._refine_block

    def refine_cpu(self, quantiles, context, mask, target_rows):
        if quantiles.shape[1] // self.patch_size <= 1:
            return quantiles                                             # the library's own early return
        raise NotImplementedError("multi-patch refine on MPS: not needed for PRED = 21")
    tf.TimestralForecaster._refine_block = refine_cpu
    ts._mps_safe = True


def model():
    global _M
    if _M is None:
        from timestral import TimestralForecaster
        if DEVICE == "mps":
            _mps_safe()
        _M = TimestralForecaster.from_pretrained(REPO, device=DEVICE, revision=REV)
        _M.model.eval()
    return _M


def weights_rev():
    from huggingface_hub import HfApi
    return HfApi().model_info(REPO).sha


def forecast(ctx, cov, widths=False):
    """ctx (B, T) residuals, cov (B, C, T) -> median (B, PRED) [and q10, q90]."""
    m = model()
    lv = [round(float(x), 4) for x in m.quantile_levels]
    med, lo, hi = [], [], []
    for a in range(0, len(ctx), CHUNK):
        fc = m.forecast(ctx[a:a + CHUNK], prediction_length=X.PRED, past_covariates=cov[a:a + CHUNK],
                        clip_nonnegative=False)
        qs = fc.quantiles[:, 0].float().cpu().numpy()                    # (b, PRED, Q)
        med.append(qs[..., lv.index(0.5)])
        lo.append(qs[..., lv.index(0.1)])
        hi.append(qs[..., lv.index(0.9)])
    return np.concatenate(med), np.concatenate(lo), np.concatenate(hi)


def timestral_scores(d, days, sector, widths=None):
    """{h: (D, N) scores}; same eligibility as chronos_scores (eligible, 60 finite residual days), names in sector
    order (irrelevant here: series are independent)."""
    out = {h: np.full((len(d["S"]), len(d["names"])), np.nan) for h in X.HS}
    order = np.lexsort((np.array(d["names"]), np.array(sector)))
    for day in days:
        live = [j for j in order if d["elig"][day, j] and np.isfinite(d["e"][max(0, day - 59): day + 1, j]).all()]
        a = max(0, day - X.CTX + 1)
        ctx = d["e"][a: day + 1, live].T.astype(np.float32)               # NaN before a name's first close: missing
        cov = np.moveaxis(d["Z"][a: day + 1, live], 0, -1).astype(np.float32)   # (B, 5, T)
        med, lo, hi = forecast(ctx, cov)
        for h in X.HS:
            out[h][day, live] = med[:, 1:h + 1].sum(1)                   # step 0 is session d+1 (the embargo day);
            if widths is not None:                                       # the target is d+2..d+1+h, as chronos_scores
                widths.setdefault(h, np.full_like(out[h], np.nan))[day, live] = \
                    hi[:, 1:h + 1].sum(1) - lo[:, 1:h + 1].sum(1)
    return out


# ------------------------------------------------------------------------------------------------------ gates
def signed_off():
    txt = open(X.PREREG).read()
    if "## Amendment 3" not in txt or "Owner sign-off (Amendment 3):** _pending_" in txt:
        sys.exit("Amendment 3 not signed off")
    rel = os.path.relpath(X.PREREG, X.ROOT)
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=X.ROOT).returncode:
        sys.exit("pre-registration has uncommitted changes")
    sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", rel], cwd=X.ROOT, text=True).strip()
    if not subprocess.check_output(["git", "branch", "-r", "--contains", sha], cwd=X.ROOT, text=True).strip():
        sys.exit("pre-registration commit is not pushed")
    return sha


# ------------------------------------------------------------------------------------------------------ commands
def smoke():
    d = T.build()
    S, sector = d["S"], X.sectors(d)
    days = X.thursdays(S, np.where(S.year == 2012)[0])[:10]
    t = time.time()
    w = {}
    cs = timestral_scores(d, days, sector, widths=w)
    sec = time.time() - t
    again = timestral_scores(d, days[:2], sector)
    expected = [int(sum(d["elig"][dd, j] and np.isfinite(d["e"][max(0, dd - 59): dd + 1, j]).all()
                        for j in range(len(d["names"])))) for dd in days]
    rep = {"weights_rev": weights_rev(), "code": CODE, "device": DEVICE, "sec_10_thursdays": round(sec, 1),
           "names_scored": [int(np.isfinite(cs[20][dd]).sum()) for dd in days], "names_expected": expected,
           "reproducible": bool(all(np.array_equal(cs[h][days[:2]], again[h][days[:2]], equal_nan=True) for h in X.HS)),
           **{f"ic_h{h}_2012": X.val_ic(cs[h], d[f"y{h}"], days) for h in X.HS},
           "score_sd_h5": float(np.nanstd(cs[5][days])), "width_median_h5": float(np.nanmedian(w[5][days]))}
    # the Chronos-2 zero-shot on the same days, for comparison of the 2012 (training-period) ICs
    c2 = X.chronos_scores(d, days, sector)
    rep.update({f"chronos2_ic_h{h}_2012": X.val_ic(c2[h], d[f"y{h}"], days) for h in X.HS})
    rep["corr_with_chronos2_h5"] = float(pd.Series(cs[5][days].ravel()).corr(pd.Series(c2[5][days].ravel())))
    j = int(np.where(np.isfinite(cs[5][days[0]]))[0][0])
    rep["sample"] = {"name": d["names"][j], "day": str(S[days[0]].date()),
                     "last5_resid": d["e"][days[0] - 4: days[0] + 1, j].round(5).tolist(),
                     "next5_resid_actual": d["e"][days[0] + 1: days[0] + 6, j].round(5).tolist(),
                     "score_h5": cs[5][days[0], j], "score_h20": cs[20][days[0], j],
                     "z_today": d["Z"][days[0], j].round(3).tolist()}
    rep["panel"] = news_smoke()
    path = os.path.join(P.REPORT, "timestral_smoke.json")
    json.dump(rep, open(path, "w"), indent=1, default=float)
    print(json.dumps(rep, indent=1, default=float))


def run():
    sha = signed_off()
    if os.path.exists(OUT):
        sys.exit("SP500_TIMESTRAL.md exists: the read has been made")
    d = T.build()
    S, sector = d["S"], X.sectors(d)
    preds = {h: np.full(d["y20"].shape, np.nan) for h in X.HS}
    w = {}
    for yr in X.YEARS:
        days = X.thursdays(S, np.where(S.year == yr)[0])
        cs = timestral_scores(d, days, sector, widths=w)
        for h in X.HS:
            preds[h][days] = cs[h][days]
        X.log("timestral", yr)
    np.savez_compressed(PART, **{f"h{h}": v for h, v in preds.items()}, **{f"w{h}": v for h, v in w.items()},
                        meta=json.dumps({"sha": sha, "weights_rev": weights_rev(), "code": CODE, "device": DEVICE}))
    X.log("saved", PART)


def score():
    sha = signed_off()
    if os.path.exists(OUT):
        sys.exit("SP500_TIMESTRAL.md exists: the read has been made")
    z = np.load(PART)
    meta = json.loads(str(z["meta"]))
    assert subprocess.run(["git", "merge-base", "--is-ancestor", meta["sha"], sha], cwd=X.ROOT).returncode == 0
    d = T.build()
    sector = X.sectors(d)
    preds = {("timestral", h): z[f"h{h}"] for h in X.HS}
    preds.update({("ridge", h): np.load(X.part_path("ridge"))[f"h{h}"] for h in X.HS})
    X.score(d, preds, {}, sha, sector, models=("timestral",), out=OUT, years_csv="sp500_timestral_years.csv",
            title=f"S&P 500 read of Timestral-209M, zero-shot (Amendment 3; weights {meta['weights_rev']})")
    strategies(d, z)


def strategies(d, z):
    """Descriptive: Timestral on S0-S4 and S5 (median / (q90 - q10), then S3), next to the earlier models."""
    import strategies as ST
    preds = {}
    for p_ in X.PARTS:                                                   # every saved part of the signed read
        zz = np.load(X.part_path(p_))
        for k in zz.files:
            if k.startswith("h"):
                preds[(p_.split("_h")[0], int(k[1:]))] = zz[k]
    for h in X.HS:
        preds[("timestral", h)] = z[f"h{h}"]
        with np.errstate(invalid="ignore", divide="ignore"):
            preds[("timestral_unc", h)] = z[f"h{h}"] / np.where(z[f"w{h}"] > 0, z[f"w{h}"], np.nan)
    path = os.path.join(P.REPORT, "SP500_STRATEGIES_TIMESTRAL.md")
    hdr = ("# Timestral on every literature strategy, S&P 500 2013-2025 (descriptive; Amendment 3)\n\n"
           "All returns in % per year; same books, sleeve and broker costs as SP500_STRATEGIES.md. Model "
           "`timestral_unc` is the uncertainty-adjusted score (median / (q90 - q10)); its **S3 row is S5**. Rows for "
           "ridge, Chronos-2 and MASTER repeat the earlier table for comparison.\n\n")
    tab = ST.run_all(d, preds, X.YEARS, ("ridge",) + X.MODELS + ("timestral", "timestral_unc"),
                     path, header=hdr)
    print(tab[(tab.span == "2013-25") & tab.model.str.startswith("timestral")].round(2).to_string(index=False))


# ------------------------------------------------------------------------------------------------ T2: news panel
NEWS_YEARS, PCA_K, NEWS_HL = range(2018, 2026), 8, 5


def panel_inputs():
    """Panel residuals, the five signals and the news covariates: 3 intensity columns + PCA-8 of the decayed
    (half-life 5) headline state, the PCA fit on 2016-17 sessions only (before any scored year)."""
    p = F.Panel()
    st = p.state(NEWS_HL)                                                # (D, N, 3072)
    fit = (p.S >= F.FIT_START) & (p.S < pd.Timestamp("2018-01-01"))
    X_ = st[fit].reshape(-1, st.shape[-1])
    X_ = X_[np.abs(X_).sum(1) > 0]
    mu = X_.mean(0)
    _, _, vt = np.linalg.svd(X_ - mu, full_matrices=False)
    pcs = np.where((np.abs(st).sum(-1) > 0)[..., None], (st - mu) @ vt[:PCA_K].T, 0.0).astype(np.float32)
    news = np.concatenate([p.intensity, pcs], -1)                        # (D, N, 11)
    return p, news


def panel_scores(p, news, days, with_news):
    out = {h: np.full((len(p.S), p.N), np.nan) for h in X.HS}
    for day in days:
        live = [j for j in range(p.N) if np.isfinite(p.e[max(0, day - 59): day + 1, j]).all()
                and np.isfinite(p.quant[day, j]).all()]
        a = max(0, day - X.CTX + 1)
        ctx = p.e[a: day + 1, live].T.astype(np.float32)
        cov = np.moveaxis(p.quant[a: day + 1, live], 0, -1)
        if with_news:
            cov = np.concatenate([cov, np.moveaxis(news[a: day + 1, live], 0, -1)], 1)
        med, _, _ = forecast(ctx, cov.astype(np.float32))       # NaN = missing (library masks it)
        for h in X.HS:
            out[h][day, live] = med[:, 1:h + 1].sum(1)                   # sessions d+2..d+1+h (Panel.target)
    return out


def news_smoke():
    p, news = panel_inputs()
    days = F.thursdays(p, np.where(p.S.year == 2017)[0])[:5]
    a, b = panel_scores(p, news, days, False), panel_scores(p, news, days, True)
    return {"names": p.N, "scored": [int(np.isfinite(a[5][dd]).sum()) for dd in days],
            "corr_news_vs_none_h5": float(pd.Series(a[5][days].ravel()).corr(pd.Series(b[5][days].ravel()))),
            "news_cov_sd": np.nanstd(news[days], (0, 1)).round(3).tolist()}


def news():
    signed_off()
    if os.path.exists(NEWS_OUT):
        sys.exit("TIMESTRAL_NEWS.md exists")
    p, nw = panel_inputs()
    sec = F.sector_ids(p.names)
    rows, years = [], []
    allsc = {}                                                           # each arm forecast once, all horizons
    for arm in (False, True):
        allsc[arm] = {h_: np.full((len(p.S), p.N), np.nan) for h_ in X.HS}
        for yr in NEWS_YEARS:
            days = F.thursdays(p, np.where(p.S.year == yr)[0])
            s = panel_scores(p, nw, days, arm)
            for h_ in X.HS:
                allsc[arm][h_][days] = s[h_][days]
            X.log("panel", "news" if arm else "no news", yr)
    for h in X.HS:
        y = p.target(h)
        arms = {arm: allsc[arm][h] for arm in allsc}
        per = {}
        for yr in NEWS_YEARS:
            wk = F.thursdays(p, np.where(p.S.year == yr)[0])
            per[yr] = {arm: F.weekly_ic(arms[arm], y, wk) for arm in arms}
            per[yr]["neu"] = F.weekly_ic(F.neutralise(arms[True], sec), F.neutralise(y, sec), wk) - \
                F.weekly_ic(F.neutralise(arms[False], sec), F.neutralise(y, sec), wk)
            years.append({"h": h, "year": yr, "ic_no_news": np.nanmean(per[yr][False]),
                          "ic_news": np.nanmean(per[yr][True])})
        for name, ys in (("2018-25", NEWS_YEARS), ("2022-25", range(2022, 2026))):
            a = np.concatenate([per[y_][False] for y_ in ys])
            b = np.concatenate([per[y_][True] for y_ in ys])
            n = np.concatenate([per[y_]["neu"] for y_ in ys])
            rows.append({"h": h, "span": name, "ic_no_news": np.nanmean(a), "t_no_news": F.nw_t(a, F.nw_lag(h)),
                         "ic_news": np.nanmean(b), "t_news": F.nw_t(b, F.nw_lag(h)),
                         "delta_ic": np.nanmean(b - a), "t_delta": F.nw_t(b - a, F.nw_lag(h)),
                         "delta_ic_sector_neutral": np.nanmean(n)})
    tab, yt = pd.DataFrame(rows), pd.DataFrame(years)
    yt.to_csv(os.path.join(P.REPORT, "timestral_news_years.csv"), index=False)
    with open(NEWS_OUT, "w") as f:
        f.write("# Timestral-209M +/- news on the 31-name panel (descriptive; Amendment 3 T2)\n\n"
                "News covariates: 3 intensity columns + PCA-8 of the half-life-5 headline state (PCA fit 2016-17). "
                "Weekly Thursday IC vs the residual target; NW t. Compare: CONFIRM.md (ridge/trees, 2022-25).\n\n"
                + tab.round(4).to_markdown(index=False) + "\n\n## By year\n\n" + yt.round(4).to_markdown(index=False)
                + "\n")
    print(tab.round(4).to_string(index=False))


def devcheck():
    """MPS vs CPU on 4 Thursdays of 2012 (training period): scores must agree to float32 noise before MPS is used."""
    global _M, DEVICE
    d = T.build()
    S, sector = d["S"], X.sectors(d)
    days = X.thursdays(S, np.where(S.year == 2012)[0])[:4]
    res = {}
    for dev in ("cpu", "mps"):
        DEVICE, _M = dev, None
        t = time.time()
        res[dev] = (timestral_scores(d, days, sector), time.time() - t)
    rep = {"sec_cpu": round(res["cpu"][1], 1), "sec_mps": round(res["mps"][1], 1)}
    for h in X.HS:
        a, b = res["cpu"][0][h][days], res["mps"][0][h][days]
        ok = np.isfinite(a) & np.isfinite(b)
        rep[f"h{h}"] = {"same_names": bool((np.isfinite(a) == np.isfinite(b)).all()),
                        "max_abs_diff": float(np.abs(a - b)[ok].max()), "score_sd": float(a[ok].std()),
                        "rank_corr": float(pd.Series(a[ok]).rank().corr(pd.Series(b[ok]).rank()))}
    rep["agree"] = all(rep[f"h{h}"]["same_names"] and rep[f"h{h}"]["rank_corr"] > 0.9999
                       and rep[f"h{h}"]["max_abs_diff"] < 1e-3 * rep[f"h{h}"]["score_sd"] for h in X.HS)
    json.dump(rep, open(os.path.join(P.REPORT, "timestral_devcheck.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


def strategies_only():
    """Re-run the descriptive strategy table after `score` (the read itself is never re-scored)."""
    if not os.path.exists(OUT):
        sys.exit("run `score` first")
    strategies(T.build(), np.load(PART))


if __name__ == "__main__":
    {"smoke": smoke, "devcheck": devcheck, "strategies": strategies_only, "run": run, "score": score, "news": news}[sys.argv[1]]()
