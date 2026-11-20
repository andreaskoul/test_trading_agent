"""Layer 5 E: MASTER ensembling over the full grid (research/tree/PREREG.md, "Layer 5", exploitation branch E).

Copied from research/tree/L4_arch/arch.py (unedited there). Changes: CACHE is .cache/tree/l5ens; the base
architecture only; make_net/fit take the grid configuration (d_model, beta) instead of the frozen CFG.

Original L4_arch docstring follows.

Copied from quant-tf research/quant_trials/sp500_transformers.py (master_day, market, master_net, master_fit_predict)
and sp500_test.build(); the quant-tf files are imported read-only and never edited. Changes here:

* build(cap): the same data build, but the price file is read with a row filter Date <= cap (stage 1: 2019-12-31), so
  nothing later is loaded; membership rows after cap are dropped as well.
* one change per variant (VARIANTS); every variant keeps the as-run settings d_model 256, beta 5 (the grid selection
  made at the as-run first refit for the 5-day horizon and frozen for every later refit).
* fit(): master_fit_predict with an epoch-level checkpoint (resumable after a kill) and a stop at the fund's trading
  window (weekdays 15:30-21:15 UTC): the fit saves its state and returns "paused".
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

QT = "/Users/apollogodofthesun/test_trading_agent/.claude/worktrees/quant-tf"
QTR = os.path.join(QT, "research", "quant_trials")
sys.path.insert(0, QTR)
import features as F  # noqa: E402  (read-only import)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CACHE = os.path.join(ROOT, ".cache", "tree", "l5ens")
L4CACHE = os.path.join(ROOT, ".cache", "tree", "l4arch")
PX = os.path.join(QT, ".cache", "quant_trials", "sp500_close.parquet")
TRAIN0 = pd.Timestamp("2010-01-04")
CFG = {"d_model": 256, "beta": 5}                     # as-run MASTER h5 settings (sp500_transformers.FINAL)
MAX_EPOCHS, PATIENCE = 100, 15
SEEDS = (0, 1, 2, 3, 4)
GRID = [(m, b) for m in (64, 256) for b in (2, 5)]       # sp500_transformers.GRID["master"] order
VARIANTS = {
    "base": {"look": 8, "gate": "base", "loss": "mse", "heads": (5,)},
    "A1": {"look": 20, "gate": "base", "loss": "mse", "heads": (5,)},
    "A2": {"look": 8, "gate": "rich", "loss": "mse", "heads": (5,)},
    "A3": {"look": 8, "gate": "base", "loss": "rankcorr", "heads": (5,)},
    "A4": {"look": 8, "gate": "base", "loss": "mse", "heads": (5, 10, 20)},
}


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), *a, flush=True)


def in_trading_window(t=None):
    t = pd.Timestamp.now("UTC") if t is None else t
    if t.weekday() >= 5:
        return False
    m = t.hour * 60 + t.minute
    return 15 * 60 + 30 <= m < 21 * 60 + 15


def seconds_to_window_end(t=None):
    t = pd.Timestamp.now("UTC") if t is None else t
    end = t.normalize() + pd.Timedelta(hours=21, minutes=15)
    return max(0.0, (end - t).total_seconds())


def disk_free_gb():
    st = os.statvfs("/System/Volumes/Data")
    return st.f_bavail * st.f_frsize / 1e9


# ------------------------------------------------------------------------------------------------ data
def build(cap="2025-12-31"):
    """sp500_test.build() with every input row after `cap` left unread."""
    cap = pd.Timestamp(cap)
    px = pd.read_parquet(PX, filters=[("Date", "<=", cap)])
    px.index = pd.to_datetime(px.index).tz_localize(None).normalize()
    px = px[px.index <= cap]
    assert px.index.max() <= cap
    spy = px.pop("SPY")
    S = px.index
    m = pd.read_csv(os.path.join(QT, "data", "raw", "stocks", "sp500_membership.csv"), parse_dates=["date"])
    mem = m[m.date <= cap].set_index("date")["tickers"].map(lambda s: set(s.split(","))).reindex(S, method="ffill")
    names = list(px.columns)
    elig = np.array([[t in s for t in names] for s in mem.values])
    close = px.values
    lp = np.log(px)
    r = px.pct_change().values
    rm = spy.pct_change().values
    sig = {"mom12_1": (lp.shift(20) - lp.shift(252)).values, "rev1m": -(lp - lp.shift(20)).values,
           "rev1w": -(lp - lp.shift(5)).values,
           "lowvol": -np.log(px).diff().rolling(60, min_periods=50).std().values,
           "high52": (px / px.rolling(252, min_periods=200).max()).values}
    spec = json.load(open(os.path.join(QT, "artefacts", "llm", "ridge_stocks.json")))
    Z = np.stack([sig[c] for c in spec["features"]], -1)
    Z[~elig] = np.nan
    with np.errstate(all="ignore"):
        Z = (Z - np.nanmean(Z, 1, keepdims=True)) / np.nanstd(Z, 1, keepdims=True)
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi), index=S)
    mk = pd.Series(rm, index=S)
    beta = (2 / 3) * w.rolling(252, min_periods=200).cov(mk).div(mk.rolling(252, min_periods=200).var(), axis=0) \
        .fillna(1.0).values + 1 / 3
    cr = np.vstack([np.zeros((1, r.shape[1])), np.cumsum(np.nan_to_num(r), 0)])
    cm = np.concatenate([[0], np.cumsum(np.nan_to_num(rm))])

    def resid(h):
        y = np.full(r.shape, np.nan)
        for d in range(len(S) - 1 - h):
            a, b = d + 2, d + 2 + h
            y[d] = (cr[b] - cr[a]) - beta[d] * (cm[b] - cm[a])
        valid = np.isfinite(close)
        ok = np.zeros_like(valid)
        ok[: len(S) - 1 - h] = valid[1 + h:] & valid[: len(S) - 1 - h]
        y[~(ok & elig)] = np.nan
        with np.errstate(all="ignore"):
            return y - np.nanmean(y, 1, keepdims=True)
    return {"S": S, "names": names, "Z": Z.astype(np.float32), "y5": resid(5), "y10": resid(10), "y20": resid(20),
            "elig": elig, "spy": spy.values, "rm": rm, "r": r}


def market(d, gate="base"):
    """sp500_transformers.market (15 values). gate 'rich' (A2) appends SPY return over 5/21/63 sessions, SPY
    21-session volatility of daily returns, and cross-sectional dispersion (std of eligible names' daily returns,
    21-session mean): 20 values. Every value uses closes <= the session."""
    spy, rm = pd.Series(d["spy"]), pd.Series(d["rm"])
    cols = []
    for w in (5, 10, 20, 30, 60):
        cols += [rm.rolling(w).mean(), rm.rolling(w).std(), spy / spy.rolling(w).mean() - 1]
    if gate == "rich":
        for w in (5, 21, 63):
            cols.append(spy / spy.shift(w) - 1)
        cols.append(rm.rolling(21).std())
        rr = np.where(d["elig"], d["r"], np.nan)
        with np.errstate(all="ignore"):
            disp = pd.Series(np.nanstd(rr, 1))
        cols.append(disp.rolling(21, min_periods=15).mean())
    return np.stack([c.values for c in cols], -1).astype(np.float32)


def windows(S, year, h):
    """sp500_transformers.windows: training sessions whose h-target ends before 1 January of `year`, last 20% for
    early-stopping validation."""
    q = int(np.searchsorted(S, pd.Timestamp(f"{year}-01-01")))
    t0 = int(np.searchsorted(S, TRAIN0))
    train = np.arange(t0, q)
    train = train[train + 1 + h < q]
    cut = int(len(train) * 0.8)
    return train[: cut - h - 1], train[cut:], train, q


def thursdays(S, idx):
    return idx[S[idx].weekday == 3]


def master_day(d, M, day, look):
    Z = d["Z"][day - look + 1: day + 1]
    ok = d["elig"][day] & np.isfinite(Z).all((0, 2))
    ix = np.where(ok)[0]
    x = np.concatenate([Z[:, ix].transpose(1, 0, 2), np.repeat(M[day - look + 1: day + 1][None], len(ix), 0)], -1)
    return ix, x


def device():
    import torch
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def make_net(v, n_market, cfg):
    import torch
    sys.path.insert(0, os.path.join(QTR, "vendor", "master"))
    from master import MASTER                                           # vendored unchanged (quant-tf)
    net = MASTER(d_feat=5, d_model=cfg["d_model"], t_nhead=4, s_nhead=2, T_dropout_rate=0.5, S_dropout_rate=0.5,
                 gate_input_start_index=5, gate_input_end_index=5 + n_market, beta=cfg["beta"])
    if len(v["heads"]) > 1:                                             # A4: shared encoder, one linear head each
        net.layers[-1] = torch.nn.Linear(cfg["d_model"], len(v["heads"]))
    return net.to(device())


# ------------------------------------------------------------------------------------------------ fit
def fit(d, variant, seed, year, pred_days, ckpt, max_epochs=MAX_EPOCHS, deadline=None, cfg=None):
    """One fit of `variant` for the refit before `year`; returns ("done", scores[len(pred_days), N], info) or
    ("paused", None, info). Checkpoint after every epoch at `ckpt`."""
    import torch
    sys.path.insert(0, os.path.join(QTR, "vendor", "master"))
    from base_model import drop_extreme, zscore
    v = VARIANTS[variant]
    look, hs = v["look"], v["heads"]
    dev = device()
    S = d["S"]
    tr, va, train, _ = windows(S, year, max(hs))                        # A4: every head's target ends before year
    M = market(d, v["gate"])
    mu, sd = np.nanmean(M[train], 0), np.nanstd(M[train], 0)
    M = np.nan_to_num((M - mu) / np.where(sd > 0, sd, 1.0)).astype(np.float32)
    torch.manual_seed(seed)
    np.random.seed(seed)
    net = make_net(v, M.shape[1], cfg or CFG)
    opt = torch.optim.Adam(net.parameters(), 1e-5)
    cache = {}

    def batch(day):
        if day not in cache:
            ix, x = master_day(d, M, day, look)
            cache[day] = (ix, torch.tensor(x, device=dev))
        return cache[day]

    def head0(out):
        return out[:, 0] if out.dim() == 2 else out

    def scores(days):
        net.eval()
        out = np.full((len(days), len(d["names"])), np.nan, dtype=np.float32)
        with torch.no_grad():
            for i, day in enumerate(days):
                ix, x = batch(day)
                if len(ix) >= 10:
                    out[i, ix] = head0(net(x)).float().cpu().numpy()
        return out

    vth = thursdays(S, va)
    y5 = d["y5"]
    labels = {}
    for day in tr:                                                      # as run: the fit rows are `tr`
        if day < look:
            continue
        ix, x = batch(day)
        Y = np.stack([d[f"y{h}"][day, ix] for h in hs], -1)
        fin = np.isfinite(Y).all(1)
        if fin.sum() < 50:
            continue
        fin_t = torch.tensor(fin, device=dev)
        labs = []
        for k in range(len(hs)):
            lab = torch.tensor(Y[fin, k], device=dev, dtype=torch.float32)
            keep, lab = drop_extreme(lab)
            if v["loss"] == "rankcorr":
                lab = torch.argsort(torch.argsort(lab)).float()
            labs.append((keep, zscore(lab)))
        labels[day] = (x[fin_t], labs)

    def day_loss(x_, labs):
        out = net(x_)
        out = out[:, None] if out.dim() == 1 else out
        ls = []
        for k, (keep, lab) in enumerate(labs):
            p = out[keep, k]
            if v["loss"] == "rankcorr":                                 # A3: -Pearson(pred, ranked target)
                pc, lc = p - p.mean(), lab - lab.mean()
                ls.append(-(pc * lc).sum() / (pc.norm() * lc.norm() + 1e-8))
            else:
                ls.append(torch.mean((p - lab) ** 2))
        return torch.stack(ls).mean()

    st = {"ep": 0, "best": -1, "best_ic": -np.inf, "best_state": None, "hist": [], "sec": 0.0}
    if os.path.exists(ckpt):
        ck = torch.load(ckpt, map_location="cpu", weights_only=False)
        net.load_state_dict(ck["net"])
        opt.load_state_dict(ck["opt"])
        np.random.set_state(ck["np_rng"])
        torch.set_rng_state(ck["torch_rng"])
        if ck.get("mps_rng") is not None and dev.type == "mps":
            torch.mps.set_rng_state(ck["mps_rng"])
        st = ck["st"]
        log(f"resumed {variant} s{seed} {year} at epoch {st['ep']} (best {st['best']} ic {st['best_ic']:.4f})")
    t_start = time.time()
    stopped = False
    while st["ep"] < max_epochs:
        if (deadline and time.time() > deadline) or disk_free_gb() < 4:   # no trading-window pause (owner, 2026-11-19)
            return "paused", None, {"epoch": st["ep"], "reason": "window/deadline/disk"}
        ep = st["ep"]
        t0 = time.time()
        net.train()
        losses = []
        for day in np.random.permutation(list(labels)):
            x_, labs = labels[day]
            loss = day_loss(x_, labs)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_value_(net.parameters(), 3.0)
            opt.step()
            losses.append(loss.detach())
        mloss = float(torch.stack(losses).float().mean().cpu())
        s = float(np.nanmean(F.weekly_ic(scores(vth).astype(np.float64), y5[vth], np.arange(len(vth)))))
        if np.isfinite(s) and s > st["best_ic"]:
            st["best"], st["best_ic"] = ep, s
            st["best_state"] = {k: v_.detach().cpu().clone() for k, v_ in net.state_dict().items()}
        st["hist"].append([ep, mloss, s, round(time.time() - t0, 1)])
        st["ep"] = ep + 1
        st["sec"] += time.time() - t0
        # as run: stop when mean training loss < 0.95 or 15 epochs without a validation gain. The loss threshold is
        # MSE-specific; for A3 (loss in [-1, 1]) only the patience rule applies.
        stop = (v["loss"] == "mse" and mloss < 0.95) or ep - st["best"] >= PATIENCE
        log(f"{variant} s{seed} {year} ep {ep} loss {mloss:.4f} val_ic {s:.4f} best {st['best']} "
            f"{time.time() - t0:.0f}s")
        if stop:
            stopped = True
            break
        torch.save({"net": net.state_dict(), "opt": opt.state_dict(), "np_rng": np.random.get_state(),
                    "torch_rng": torch.get_rng_state(),
                    "mps_rng": torch.mps.get_rng_state() if dev.type == "mps" else None, "st": st}, ckpt + ".tmp")
        os.replace(ckpt + ".tmp", ckpt)
    if st["best_state"] is not None:
        net.load_state_dict({k: v_.to(dev) for k, v_ in st["best_state"].items()})
    out = scores(pred_days)
    info = {"epochs": st["ep"], "best_epoch": st["best"], "val_ic": st["best_ic"], "train_sec": round(st["sec"], 1),
            "stopped_by_rule": stopped, "hist": st["hist"], "n_train_days": len(labels),
            "session_sec": round(time.time() - t_start, 1)}
    return "done", out, info
