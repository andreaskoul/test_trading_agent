"""Contract tests for the short-volume paper book (research/riskfield/forward_f2.py).

    cd research/quant_trials && PYTHONPATH=. python ../riskfield/test_forward_f2.py
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import forward_f2 as F  # noqa: E402


def _cache(days, rows_fn):
    d = tempfile.mkdtemp()
    F.CACHE = d
    for x in days:
        rows_fn(x).to_parquet(os.path.join(d, f"CNMS{x:%Y%m%d}.parquet"))


def test_ratio_is_summed_short_over_summed_total_and_needs_16_of_20_days():
    S = pd.bdate_range("2026-09-01", periods=25)
    t = 24
    def rows(x):
        k = S.get_loc(x)
        r = [("AAA", 30, 100), ("BBB", 10 * (k % 2 + 1), 50)]
        if k < 20:
            r.append(("CCC", 1, 10))                                 # CCC on 15 of the last 20 days (k 5..19)
        return pd.DataFrame(r, columns=["Symbol", "ShortVolume", "TotalVolume"])
    _cache(S, rows)
    f = F.f2_at(S, t, ["AAA", "BBB", "CCC", "DDD"])
    assert abs(f[0] - 0.3) < 1e-12
    ks = range(t - 19, t + 1)
    assert abs(f[1] - sum(10 * (k % 2 + 1) for k in ks) / (50 * 20)) < 1e-12
    assert np.isnan(f[2]) and np.isnan(f[3])                          # 15 of 20 days, and no data


def test_book_is_long_low_ratio_short_high_ratio_and_hedged():
    score = np.linspace(0.2, 0.8, 100)
    beta = np.linspace(0.5, 1.5, 100)
    w, h = F.decile_book(score, beta)
    assert (w[:10] > 0).all() and (w[-10:] < 0).all() and (w[10:90] == 0).all()
    assert abs(w[w > 0].sum() - 0.5) < 1e-12 and abs(w[w < 0].sum() + 0.5) < 1e-12
    assert abs((w * beta).sum() + h) < 1e-12


def test_a_bad_file_is_an_error_not_data():
    F.CACHE = tempfile.mkdtemp()
    real = F.urllib.request.urlopen

    class R:
        def __init__(self, b): self.b = b
        def read(self): return self.b
    try:
        F.urllib.request.urlopen = lambda *a, **k: R(b"<Error>AccessDenied</Error>")
        try:
            F.finra_day(pd.Timestamp("2026-09-01"))
            raise AssertionError("accepted a non-FINRA body")
        except RuntimeError as e:
            assert "header" in str(e)
    finally:
        F.urllib.request.urlopen = real


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
