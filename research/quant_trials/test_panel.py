"""Point-in-time guards for the quant trials (run before any trial):  pytest research/quant_trials"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as F  # noqa: E402
import models as M  # noqa: E402
import panel as P  # noqa: E402
import trials as T  # noqa: E402

SEALED = pd.Timestamp("2026-01-01")


@pytest.fixture(scope="module")
def p():
    return F.Panel()


def test_nothing_from_the_sealed_window(p):
    assert p.S.max() < SEALED
    assert P.load_prices().index.max() < SEALED
    for t in P.UNIVERSE:
        z = np.load(os.path.join(P.CACHE, "text", f"{t}_dedup.npz"))
        assert (z["session"] < np.datetime64("2026-01-01")).all(), t


def test_session_rule():
    S = P.sessions()
    ts = pd.Series(["2022-03-07 20:59:00", "2022-03-07 21:00:00", "2022-03-05 15:00:00",
                    "2016-01-04T23:50:06Z", "2014-06-01 12:00:00"])
    got = P.assign_sessions(ts, S).tolist()
    assert got[0] == pd.Timestamp("2022-03-07")             # 15:59 ET: same session
    assert got[1] == pd.Timestamp("2022-03-08")             # 16:00 ET: next session
    assert got[2] == pd.Timestamp("2022-03-07")             # Saturday: Monday
    assert got[3] == pd.Timestamp("2016-01-05")             # mixed formats parse
    assert pd.isna(got[4])                                  # before the calendar: dropped


def test_text_state_is_causal(p):
    """Changing headlines after session d leaves every text feature at d unchanged."""
    d = int(np.searchsorted(p.S, pd.Timestamp("2019-06-03")))
    s5, s0 = p.state(5)[d].copy(), p.state(0)[d].copy()
    keep = p.tsum[d + 1:].copy()
    p.tsum[d + 1:] = np.random.default_rng(0).normal(size=keep.shape).astype(np.float32)
    try:
        assert np.allclose(p.state(5)[d], s5)
        assert np.allclose(p.state(0)[d], s0)
    finally:
        p.tsum[d + 1:] = keep


def test_target_starts_after_next_close(p):
    h = 5
    y = p.target(h)
    d, i = 1000, 3
    raw = np.array([sum(p.r[k, j] - p.beta[d, j] * p.rm[k] for k in range(d + 2, d + 2 + h))
                    for j in range(p.N)])                    # sessions d+2 .. d+1+h: close(d+1) -> close(d+1+h)
    assert np.isclose(y[d, i], raw[i] - raw.mean())


def test_folds_embargo_and_stage1_stop(p):
    for fy in F.INNER_FOLDS:
        for h in (1, 5, 20):
            tr, te = F.fold_index(p, fy, h)
            assert tr.max() + 1 + h < te.min()
            assert p.S[te].year.min() == fy and p.S[te + 1 + h].year.max() == fy


def test_encoders_fit_on_training_rows_only(p):
    """PCA fitted on a fold must not change when post-training text changes."""
    tx = T.Text(p)
    tr, _ = F.fold_index(p, 2019, 5)
    a = tx.pca(tr).components_[:3].copy()
    keep = p.tsum[tr[-1] + 1:].copy()
    p.tsum[tr[-1] + 1:] *= -1
    try:
        tx2 = T.Text(p)
        b = tx2.pca(tr).components_[:3]
    finally:
        p.tsum[tr[-1] + 1:] = keep
    assert np.allclose(np.abs(a), np.abs(b), atol=1e-4)


def test_random_target_ic_is_zero(p):
    rng = np.random.default_rng(0)
    y = rng.normal(size=(p.D, p.N))
    tr, te = F.fold_index(p, 2020, 5)
    X = T.standardise(np.concatenate([p.price, p.intensity], -1), tr)
    pred, _ = M.ridge(X, y, tr, te, 5)
    ic = F.weekly_ic(pred, y, F.thursdays(p, te))
    assert abs(np.nanmean(ic)) < 0.05
