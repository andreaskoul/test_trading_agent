"""Pre-registered S&P 500 read of three off-the-shelf transformers (PREREG_quant_transformers.md).

    python sp500_transformers.py smoke    # first refit (training through 2012) for M1/M2, M3 on 10 Thursdays of 2012;
                                          # runtimes and shapes, no test-year score (allowed before sign-off)
    python sp500_transformers.py run PART # one part (ridge, chronos2, chronos2_ft, master_h5 ... tft_h20); parts run
                                          # in parallel; each refuses unless the pre-registration is signed off,
                                          # committed and pushed
    python sp500_transformers.py score    # once every part is saved: the one read -> SP500_TRANSFORMERS.md

Data and target are sp500_test.build()'s (PREREG_quant_sp500.md): point-in-time membership, five z-scored signals,
residual targets from close(d+1); nothing after 2025-12-31. A score at d uses closes <= d only.
"""

import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from scipy import stats

import features as F
import panel as P
import sp500_test as T

ROOT = P.ROOT
PREREG = os.path.join(ROOT, "reports", "research", "PREREG_quant_transformers.md")
OUT = os.path.join(P.REPORT, "SP500_TRANSFORMERS.md")
HS, YEARS, TRAIN0 = (5, 10, 20), range(2013, 2026), pd.Timestamp("2010-01-04")
LOOK, CTX, PRED = 8, 512, 21                      # MASTER lookback, Chronos-2 context, Chronos-2 prediction length
GRID = {"master": [{"d_model": m, "beta": b} for m in (64, 256) for b in (2, 5)],
        "tft": [{"hidden": hs, "epochs": ep} for hs in (16, 64) for ep in (5, 15, 30)]}
SEEDS = {"master": (0, 1, 2, 3, 4), "tft": (0, 1, 2)}       # MASTER: the paper's five seeds (main.py)
MAX_EPOCHS, PATIENCE = 100, 15                             # MASTER: best validation rank IC, patience 15
FT_STEPS = 2000                                            # Chronos-2 fine-tuning steps per refit


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def device():
    import torch
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def thursdays(S, idx):
    return idx[S[idx].weekday == 3]


def windows(S, year, h):
    """Training sessions (target ends before 1 January of `year`, h-session embargo) and its last-20% validation."""
    q = int(np.searchsorted(S, pd.Timestamp(f"{year}-01-01")))
    t0 = int(np.searchsorted(S, TRAIN0))
    train = np.arange(t0, q)
    train = train[train + 1 + h < q]
    cut = int(len(train) * 0.8)
    return train[: cut - h - 1], train[cut:], train, q


def val_ic(pred, y, idx):
    return float(np.nanmean(F.weekly_ic(pred, y, idx)))


# ------------------------------------------------------------------------------------------------ M1 MASTER
def market(d):
    """15 market values per session from SPY: mean and std of daily returns over 5/10/20/30/60 sessions, and close
    over its 5/10/20/30/60-session average - 1 (the paper's index features without volume)."""
    spy, rm = pd.Series(d["spy"]), pd.Series(d["rm"])
    cols = []
    for w in (5, 10, 20, 30, 60):
        cols += [rm.rolling(w).mean(), rm.rolling(w).std(), spy / spy.rolling(w).mean() - 1]
    return np.stack([c.values for c in cols], -1).astype(np.float32)    # standardised per refit, on training rows


def master_day(d, M, day):
    """(names, x[N, LOOK, 5 + 15]) for one session: eligible names with all LOOK signal rows finite."""
    Z = d["Z"][day - LOOK + 1: day + 1]                                  # (LOOK, N, 5): closes <= day only
    ok = d["elig"][day] & np.isfinite(Z).all((0, 2))
    ix = np.where(ok)[0]
    x = np.concatenate([Z[:, ix].transpose(1, 0, 2), np.repeat(M[day - LOOK + 1: day + 1][None], len(ix), 0)], -1)
    return ix, x


def master_fit_predict(d, y, train, va, pred_days, cfg, seed, M, max_epochs=MAX_EPOCHS):
    import torch
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "vendor", "master"))
    from master import MASTER                                           # vendored unchanged (SOURCE)
    from base_model import drop_extreme, zscore
    dev = device()
    mu, sd = np.nanmean(M[train], 0), np.nanstd(M[train], 0)             # training rows only: no future scale
    M = np.nan_to_num((M - mu) / np.where(sd > 0, sd, 1.0)).astype(np.float32)
    torch.manual_seed(seed)
    np.random.seed(seed)
    net = MASTER(d_feat=5, d_model=cfg["d_model"], t_nhead=4, s_nhead=2, T_dropout_rate=0.5, S_dropout_rate=0.5,
                 gate_input_start_index=5, gate_input_end_index=20, beta=cfg["beta"]).to(dev)
    opt = torch.optim.Adam(net.parameters(), 1e-5)
    cache = {}

    def batch(day):
        if day not in cache:
            ix, x = master_day(d, M, day)
            cache[day] = (ix, torch.tensor(x, device=dev))
        return cache[day]

    def scores(days):
        net.eval()
        out = np.full((len(d["S"]), len(d["names"])), np.nan)
        with torch.no_grad():
            for day in days:
                ix, x = batch(day)
                if len(ix) >= 10:
                    out[day, ix] = net(x).float().cpu().numpy()
        return out
    vth = thursdays(d["S"], va)
    labels = {}                     # per training day, computed once: inputs with a label, drop-extreme mask, z-label
    for day in train:
        if day < LOOK:
            continue
        ix, x = batch(day)
        fin = np.isfinite(y[day, ix])
        if fin.sum() < 50:
            continue
        lab = torch.tensor(y[day, ix][fin], device=dev, dtype=torch.float32)
        keep, lab = drop_extreme(lab)                                    # base_model.py train_epoch
        labels[day] = (x[torch.tensor(fin, device=dev)], keep, zscore(lab))
    best, best_ic, best_state = -1, -np.inf, None
    for ep in range(max_epochs):
        net.train()
        losses = []
        for day in np.random.permutation(list(labels)):                 # no host-device sync inside the loop
            x_, keep, lab = labels[day]
            loss = torch.mean((net(x_)[keep] - lab) ** 2)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_value_(net.parameters(), 3.0)       # base_model.py
            opt.step()
            losses.append(loss.detach())
        losses = torch.stack(losses).float().cpu().numpy()
        s = val_ic(scores(vth), y, vth)
        if np.isfinite(s) and s > best_ic:
            best, best_ic = ep, s
            best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        if np.mean(losses) < 0.95 or ep - best >= PATIENCE:              # the paper's stop rule, or no gain in 15
            break
    if best_state is not None:
        net.load_state_dict(best_state)
    return scores(pred_days), {"epochs": ep + 1, "best_epoch": best, "val_ic": best_ic}


# ------------------------------------------------------------------------------------------------ M2 TFT (darts)
def tft_fit_predict(d, h, train, va, pred_days, cfg, seed, sector):
    import torch
    from darts import TimeSeries
    from darts.models import TFTModel
    S, names = d["S"], d["names"]
    end = train[-1] + 1                                                  # rows strictly before the refit point
    idx = pd.RangeIndex(0, len(S))
    span = {}
    for j, t in enumerate(names):                                        # each name from its first valid close
        v = np.where(d["valid"][:, j])[0]
        if len(v) and v[0] < end - 120:
            span[j] = v[0]
    cats = sorted(set(sector))

    def series(j, upto):
        a = span[j]
        tgt = np.nan_to_num(d["e"][a:upto, j]).astype(np.float32)
        cov = np.nan_to_num(d["Z"][a:upto, j]).astype(np.float32)
        w = (d["elig"][a:upto, j] & np.isfinite(d["e"][a:upto, j])).astype(np.float32)
        ts = TimeSeries.from_times_and_values(idx[a:upto], tgt[:, None], columns=["e"],
                                              static_covariates=pd.DataFrame({c: [float(sector[j] == c)] for c in cats}))
        return ts, TimeSeries.from_times_and_values(idx[a:upto], cov), \
            TimeSeries.from_times_and_values(idx[a:upto], w[:, None])
    js = [j for j in span if end - span[j] > 60 + h + 1]
    S_, C_, W_ = zip(*[series(j, end) for j in js])
    acc = "mps" if torch.backends.mps.is_available() else "cpu"
    model = TFTModel(input_chunk_length=60, output_chunk_length=h + 1, hidden_size=cfg["hidden"], lstm_layers=1,
                     num_attention_heads=4, dropout=0.1, batch_size=1024, n_epochs=cfg["epochs"],
                     add_relative_index=True, random_state=seed, use_static_covariates=True,
                     pl_trainer_kwargs={"accelerator": acc, "enable_progress_bar": False,
                                        "enable_model_summary": False})
    model.fit(list(S_), past_covariates=list(C_), sample_weight=list(W_), stride=5, verbose=False)
    out = np.full((len(S), len(names)), np.nan)
    for day in pred_days:
        live = [j for j in span if d["elig"][day, j] and day - span[j] >= 60]
        if len(live) < 10:
            continue
        ser, cov = zip(*[series(j, day + 1)[:2] for j in live])
        fc = model.predict(n=h + 1, series=list(ser), past_covariates=list(cov), num_samples=1,
                           predict_likelihood_parameters=True, verbose=False, show_warnings=False)
        for j, f in zip(live, fc):
            comp = [c for c in f.components if c.endswith("q0.50")] or list(f.components)[:1]
            med = f[comp[0]].values()[:, 0]                              # the median forecast path
            out[day, j] = float(med[1: h + 1].sum())                     # steps 2 .. h+1: the target window
    return out, {"series": len(js)}


# ------------------------------------------------------------------------------------------------ M3 Chronos-2
_PIPE = None


def chronos_pipe():
    from chronos import Chronos2Pipeline
    global _PIPE
    if _PIPE is None:
        _PIPE = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=str(device()))
    return _PIPE


def chronos_finetune(d, train_end, year):
    """M3-ft: Chronos-2 fully fine-tuned on every name's residual-return series (and its five signals) up to the
    refit point; library defaults (lr 1e-6), FT_STEPS steps, context 512, prediction length 21. Non-member days
    are given as missing targets, so the loss never sees them."""
    inputs = []
    for j in range(len(d["names"])):
        v = np.where(d["valid"][:train_end, j])[0]
        if len(v) < 300:
            continue
        a = v[0]
        tgt = np.where(d["elig"][a:train_end, j], d["e"][a:train_end, j], np.nan).astype(np.float32)
        inputs.append({"target": tgt, "past_covariates": {f"z{k}": d["Z"][a:train_end, j, k].astype(np.float32)
                                                          for k in range(5)}})
    from chronos import Chronos2Pipeline                                  # a fresh copy: the zero-shot one stays untouched
    base = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=str(device()))
    ft = base.fit(inputs, prediction_length=PRED, num_steps=FT_STEPS, batch_size=64, context_length=CTX,
                            output_dir=os.path.join(P.CACHE, f"chronos2_ft_{year}"))
    ft.model.eval()
    return ft


def chronos_scores(d, days, sector, pipe=None):
    """{h: (D, N) scores} for every h at once; cross-learning in sector-ordered groups of ~100 names. Zero-shot
    unless a fine-tuned pipeline is given."""
    import torch
    _PIPE_ = pipe or chronos_pipe()
    q = list(_PIPE_.quantiles)
    mi = q.index(0.5)
    out = {h: np.full((len(d["S"]), len(d["names"])), np.nan) for h in HS}
    order = np.lexsort((np.array(d["names"]), np.array(sector)))
    for day in days:
        live = [j for j in order if d["elig"][day, j] and np.isfinite(d["e"][max(0, day - 59): day + 1, j]).all()]
        inputs = []
        for j in live:
            a = max(0, day - CTX + 1)
            tgt = d["e"][a: day + 1, j].astype(np.float32)
            inputs.append({"target": tgt, "past_covariates": {f"z{k}": d["Z"][a: day + 1, j, k].astype(np.float32)
                                                              for k in range(5)}})
        fc = _PIPE_.predict(inputs, prediction_length=PRED, batch_size=600, cross_learning=True)
        for j, f in zip(live, fc):
            med = f[0, mi].float().cpu().numpy() if isinstance(f, torch.Tensor) else np.asarray(f)[0, mi]
            for h in HS:
                out[h][day, j] = float(med[1: h + 1].sum())
    return out


# ------------------------------------------------------------------------------------------------ ridge comparator
def ridge_fit_predict(d, y, tr, va, train, pred_days):
    from sklearn.linear_model import Ridge
    Z = d["Z"]

    def rows(idx):
        X, yy = Z[idx].reshape(-1, 5), y[idx].reshape(-1)
        k = np.isfinite(yy) & np.isfinite(X).all(1)
        return X[k], yy[k]
    vth = thursdays(d["S"], va)
    best, bs = None, -np.inf
    Xt, yt = rows(tr)
    for a in T.ALPHAS:
        m = Ridge(alpha=a).fit(Xt, yt)
        pv = np.full(y.shape, np.nan)
        pv[vth] = np.where(np.isfinite(Z[vth]).all(-1), m.predict(np.nan_to_num(Z[vth]).reshape(-1, 5))
                           .reshape(len(vth), -1), np.nan)
        s = val_ic(pv, y, vth)
        if s > bs:
            best, bs = a, s
    m = Ridge(alpha=best).fit(*rows(train))
    out = np.full(y.shape, np.nan)
    pd_ = np.asarray(pred_days)
    out[pd_] = np.where(np.isfinite(Z[pd_]).all(-1), m.predict(np.nan_to_num(Z[pd_]).reshape(-1, 5))
                        .reshape(len(pd_), -1), np.nan)
    out[~d["elig"]] = np.nan
    return out, {"alpha": best, "val_ic": bs}


# ------------------------------------------------------------------------------------------------ commands
def sectors(d):
    meta = pd.read_csv(os.path.join(ROOT, "data", "raw", "stocks", "sp500_current.csv")).set_index("Symbol")
    return np.array([meta["GICS Sector"].get(t, "unknown") if isinstance(meta["GICS Sector"].get(t, None), str)
                     else "unknown" for t in d["names"]])


def smoke():
    """First refit only (test year 2013 is never predicted): grids, validation ICs inside the training window,
    runtimes; Chronos-2 on 10 Thursdays of 2012 (a training-period year)."""
    d = T.build()
    S, sector, M = d["S"], sectors(d), market(d)
    rep = {"names": len(d["names"]), "sessions": len(S)}
    for h in HS:
        y = d[f"y{h}"]
        tr, va, train, q = windows(S, 2013, h)
        vth = thursdays(S, va)
        t = time.time()
        _, info = ridge_fit_predict(d, y, tr, va, train, vth)
        rep[f"ridge_h{h}"] = {**info, "sec": round(time.time() - t, 1)}
        for cfg in GRID["master"]:
            t = time.time()
            _, info = master_fit_predict(d, y, tr, va, [], cfg, 0, M)
            rep[f"master_h{h}_{cfg['d_model']}_{cfg['beta']}"] = {**info, "sec": round(time.time() - t, 1)}
            log(f"master h{h}", cfg, rep[f"master_h{h}_{cfg['d_model']}_{cfg['beta']}"])
        for cfg in GRID["tft"]:
            t = time.time()
            sc, info = tft_fit_predict(d, h, tr, va, vth, cfg, 0, sector)
            rep[f"tft_h{h}_{cfg['hidden']}_{cfg['epochs']}"] = {**info, "val_ic": val_ic(sc, y, vth),
                                                                "sec": round(time.time() - t, 1)}
            log(f"tft h{h}", cfg, rep[f"tft_h{h}_{cfg['hidden']}_{cfg['epochs']}"])
    days = thursdays(S, np.where(S.year == 2012)[0])[:10]
    t = time.time()
    cs = chronos_scores(d, days, sector)
    rep["chronos_10_thursdays_2012"] = {"sec": round(time.time() - t, 1),
                                        "names_scored": int(np.isfinite(cs[20][days]).sum(1).mean()),
                                        **{f"ic_h{h}": val_ic(cs[h], d[f"y{h}"], days) for h in HS}}
    j = int(np.where(np.isfinite(cs[20][days[0]]))[0][0])
    rep["sample"] = {"name": d["names"][j], "day": str(S[days[0]].date()),
                     "last5_resid": d["e"][days[0] - 4: days[0] + 1, j].round(5).tolist(),
                     "score_h5": cs[5][days[0], j], "score_h20": cs[20][days[0], j]}
    path = os.path.join(P.REPORT, "sp500_transformers_smoke.json")
    json.dump(rep, open(path, "w"), indent=1, default=float)
    log("smoke report", path)
    print(json.dumps(rep, indent=1, default=float))


def signed_off():
    rel = os.path.relpath(PREREG, ROOT)
    if "Owner sign-off:** _pending_" in open(PREREG).read():
        sys.exit("pre-registration not signed off")
    if subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=ROOT).returncode:
        sys.exit("pre-registration has uncommitted changes")
    sha = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", rel], cwd=ROOT, text=True).strip()
    if not subprocess.check_output(["git", "branch", "-r", "--contains", sha], cwd=ROOT, text=True).strip():
        sys.exit("pre-registration commit is not pushed")
    if os.path.exists(OUT):
        sys.exit("SP500_TRANSFORMERS.md exists: the read has been made")
    return sha


MODELS = ("master", "tft", "chronos2", "chronos2_ft")
PARTS = ["ridge", "chronos2", "chronos2_ft"] + [f"{m}_h{h}" for m in ("master", "tft") for h in HS]


def part_path(part):
    return os.path.join(P.CACHE, f"sp500_tf_{part}.npz")


def run(part):
    """One part of the read (parts run as separate processes, in parallel); `score` combines them once all exist."""
    sha = signed_off()
    d = T.build()
    S, sector, M = d["S"], sectors(d), market(d)
    preds, chosen = {}, {}
    if part == "ridge":
        for h in HS:
            preds[h] = np.full(d["y20"].shape, np.nan)
            for yr in YEARS:
                tr, va, train, _ = windows(S, yr, h)
                days = thursdays(S, np.where(S.year == yr)[0])
                preds[h][days] = ridge_fit_predict(d, y=d[f"y{h}"], tr=tr, va=va, train=train, pred_days=days)[0][days]
    elif part in ("chronos2", "chronos2_ft"):
        for h in HS:
            preds[h] = np.full(d["y20"].shape, np.nan)
        for yr in YEARS:
            days = thursdays(S, np.where(S.year == yr)[0])
            q = int(np.searchsorted(S, pd.Timestamp(f"{yr}-01-01")))
            pipe = chronos_finetune(d, q - 1 - max(HS), yr) if part == "chronos2_ft" else None
            cs = chronos_scores(d, days, sector, pipe)
            for h in HS:
                preds[h][days] = cs[h][days]
            log(part, yr)
    else:
        m, h = part.split("_h")
        h = int(h)
        y = d[f"y{h}"]
        tr, va, train, _ = windows(S, 2013, h)                           # settings: first refit only, then frozen
        best, bs = None, -np.inf
        for cfg in GRID[m]:
            vth = thursdays(S, va)
            sc = master_fit_predict(d, y, tr, va, vth, cfg, 0, M)[0] if m == "master" else \
                tft_fit_predict(d, h, tr, va, vth, cfg, 0, sector)[0]
            s_ = val_ic(sc, y, vth)
            log(part, cfg, s_)
            if s_ > bs:
                best, bs = cfg, s_
        chosen = {"settings": best, "val_ic": bs}
        preds[h] = np.full(y.shape, np.nan)
        for yr in YEARS:
            tr, va, train, _ = windows(S, yr, h)
            days = thursdays(S, np.where(S.year == yr)[0])
            runs = [master_fit_predict(d, y, tr, va, days, best, s_, M)[0][days] if m == "master" else
                    tft_fit_predict(d, h, tr, va, days, best, s_, sector)[0][days] for s_ in SEEDS[m]]
            preds[h][days] = np.nanmean(runs, 0)                         # seed-averaged scores
            log(part, yr)
    np.savez_compressed(part_path(part), **{f"h{h}": v for h, v in preds.items()},
                        meta=json.dumps({"sha": sha, "chosen": chosen}))
    log("saved", part_path(part))


def score_all():
    sha = signed_off()
    missing = [p_ for p_ in PARTS if not os.path.exists(part_path(p_))]
    if missing:
        sys.exit(f"parts not finished: {missing}")
    d = T.build()
    preds, chosen = {}, {}
    for p_ in PARTS:
        z = np.load(part_path(p_))
        meta = json.loads(str(z["meta"]))
        assert meta["sha"] == sha, f"{p_} was run under another pre-registration commit"
        model = p_.split("_h")[0]
        for k in z.files:
            if k.startswith("h"):
                preds[(model, int(k[1:]))] = z[k]
        if meta["chosen"]:
            chosen[(model, int(p_.split("_h")[1]))] = meta["chosen"]
    score(d, preds, chosen, sha, sectors(d))


def score(d, preds, chosen, sha, sector):
    S = d["S"]
    res, years = {}, []
    for h in HS:
        def per_year(pred):
            out, nets, neu = {}, {}, {}
            for fy in YEARS:
                yrs = np.where(S.year == fy)[0]
                yrs = yrs[yrs + 1 + h <= yrs[-1]]
                wk = thursdays(S, yrs)
                y = d[f"y{h}"].copy()
                y[yrs[-1] + 1:] = np.nan                                 # target windows inside the year
                out[fy] = F.weekly_ic(pred, y, wk)
                nets[fy] = T.decile_net(pred, d["y5"], wk)
                neu[fy] = F.weekly_ic(F.neutralise(pred, sector), F.neutralise(y, sector), wk)
            return out, nets, neu
        r_ic, _, _ = per_year(preds[("ridge", h)])
        for m in MODELS:
            ic, nets, neu = per_year(preds[(m, h)])
            cat = lambda dct, ys: np.concatenate([dct[y_] for y_ in ys if y_ in dct] or [np.full(1, np.nan)])
            allic = cat(ic, YEARS)
            t = F.nw_t(allic, 4)
            res[(m, h)] = {"ic": np.nanmean(allic), "t": t, "p": float(stats.norm.sf(t)),
                           "ridge_ic": np.nanmean(cat(r_ic, YEARS)),
                           "ic_2013_19": np.nanmean(cat(ic, range(2013, 2020))),
                           "ic_2020_25": np.nanmean(cat(ic, range(2020, 2026))), "ic_2022": np.nanmean(ic.get(2022, np.full(1, np.nan))),
                           "net_decile_bp_wk": np.nanmean(cat(nets, YEARS)) * 1e4,
                           "sector_neutral_ic": np.nanmean(cat(neu, YEARS)),
                           "ic_2022_25": np.nanmean(cat(ic, range(2022, 2026))), "settings": chosen.get((m, h))}
            years += [{"model": m, "h": h, "year": fy, "ic": np.nanmean(ic[fy]), "ridge_ic": np.nanmean(r_ic[fy])}
                      for fy in YEARS]
    keys = sorted(res, key=lambda k: res[k]["p"])                        # Holm over the 12
    for i, k in enumerate(keys):
        res[k]["p_holm"] = min(1.0, max(res[kk]["p"] * (len(keys) - j) for j, kk in enumerate(keys[: i + 1])))
    for k, r in res.items():
        r["pass"] = bool(r["p_holm"] < 0.05 and r["ic"] > r["ridge_ic"] and r["ic_2013_19"] > 0
                         and r["ic_2020_25"] > 0 and r["ic_2022"] >= 0 and r["net_decile_bp_wk"] > 0)
    tab = pd.DataFrame([{"model": m, "h": h, **{k: v for k, v in r.items() if k != "settings"}}
                        for (m, h), r in res.items()])
    pd.DataFrame(years).to_csv(os.path.join(P.REPORT, "sp500_transformers_years.csv"), index=False)
    with open(OUT, "w") as f:
        f.write(f"# S&P 500 read of three transformers (pre-registration `{sha}`)\n\n")
        f.write(tab.round(4).to_markdown(index=False) + "\n\n")
        f.write("Settings chosen at the first refit: " + json.dumps({f"{m}_h{h}": c for (m, h), c in chosen.items()})
                + "\n")
    print(tab.round(4).to_string(index=False))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "run":
        assert sys.argv[2] in PARTS, f"part must be one of {PARTS}"
        run(sys.argv[2])
    else:
        {"smoke": smoke, "score": score_all}[cmd]()
