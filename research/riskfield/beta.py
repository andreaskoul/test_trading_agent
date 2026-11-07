"""Risk-field research (PREREG.md §5): beta forecasts on weekly decisions, scored against the next 21 sessions'
high-frequency realised beta."""
import numpy as np
import pandas as pd

import risk as K


def hf_beta(D, a, b, need):
    """Realised beta over sessions a..b (inclusive) from the 14 returns a day; NaN with fewer than `need` sessions
    where both the name and SPY are complete."""
    R = D.R[a:b + 1]
    rm = R[:, :, D.si]
    ok = np.isfinite(R).all(1) & np.isfinite(rm).all(1)[:, None]
    x = np.where(ok[:, None, :], R, 0.0)
    m = np.where(ok[:, None, :], rm[:, :, None], 0.0)
    num, den = (x * m).sum((0, 1)), (m * m).sum((0, 1))
    return np.where(ok.sum(0) >= need, num / np.where(den > 0, den, np.nan), np.nan)


def build(D):
    T, N = D.T, D.N
    thu = np.array([D.S[t].weekday() == 3 for t in range(T)])
    tgt, b21, b63 = (np.full((T, N), np.nan) for _ in range(3))
    for t in np.where(thu)[0]:
        if t + 21 < T:
            tgt[t] = hf_beta(D, t + 1, t + 21, 17)
        if t >= 62:
            b21[t] = hf_beta(D, t - 20, t, 17)
            b63[t] = hf_beta(D, t - 62, t, 50)
    # daily OLS beta, winsorised as the fund (common.py / regime.panel): returns clipped to [min, max](-2 rm, 4 rm)
    r = np.expm1(D.r)
    rm = r[:, D.si]
    lo, hi = np.minimum(-2 * rm, 4 * rm)[:, None], np.maximum(-2 * rm, 4 * rm)[:, None]
    w = pd.DataFrame(np.clip(r, lo, hi))
    m = pd.Series(rm)
    ols = (w.rolling(252, min_periods=200).cov(m).div(m.rolling(252, min_periods=200).var(), axis=0)).to_numpy(copy=True)
    ols[~thu] = np.nan
    return {"thu": thu, "tgt": tgt, "b21": b21, "b63": b63, "ols": ols, "B0": 2 / 3 * ols + 1 / 3}


def compare(D, B, test, period):
    """H-B1: B1 vs B0; H-B2: B2 vs B1. Squared-error difference (bench - cand), weekly mean, NW t with 5 lags."""
    ftxt = D.field("text", B["b63"])
    regs1 = [B["b21"], B["b63"], B["ols"]]
    regs2 = regs1 + [ftxt]
    mask = np.broadcast_to(D.stock, (D.T, D.N)) & B["thu"][:, None] & np.all(
        [np.isfinite(r) for r in regs2 + [B["B0"]]], 0)
    f1, _ = K.forecasts(D, regs1, B["tgt"], mask, 21, period[1])
    if test == "H-B1":
        cand, bench = f1, np.where(mask, B["B0"], np.nan)
    else:
        f2, _ = K.forecasts(D, regs2, B["tgt"], mask, 21, period[1])
        cand, bench = f2, f1
    L = (B["tgt"] - bench) ** 2 - (B["tgt"] - cand) ** 2
    o = K.origins(D, 21, period) & B["thu"]
    L[~o] = np.nan
    ok = np.isfinite(L)
    wk = np.where(ok.sum(1) > 0, np.nansum(L, 1) / np.maximum(ok.sum(1), 1), np.nan)[o]
    mean, t, n = K.nw_t(wk, 5)
    mse_b = float(np.nanmean(np.where(o[:, None], (B["tgt"] - bench) ** 2, np.nan)))
    return {"gain": mean, "t": t, "weeks": n, "mse_bench": mse_b, "names_per_week": float(ok.sum(1)[o].mean())}
