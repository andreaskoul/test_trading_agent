"""Kolmogorov–Smirnov feature drift detector (Phase K).

Live deployment safety check: a policy trained on distribution P only
generalises to P. If the live feature distribution Q drifts (regime
change, data-vendor schema shift, new macro regime), we want to know
*before* the policy starts losing money.

Design
------
* ``FeatureDriftDetector(reference)`` snapshots the training feature
  distribution at construction time.
* ``check(live_window)`` runs a two-sample Kolmogorov–Smirnov test
  per feature column, comparing the live window to the reference.
* Returns a ``DriftReport`` with per-column p-values, a flagged-columns
  list (p < ``alpha``), and a single ``drifted`` boolean (True iff
  the fraction of flagged columns exceeds ``flag_fraction``).

Why KS?
  Non-parametric, distribution-free, works on any continuous feature.
  Rolling-window mean comparisons miss shape changes that KS catches
  (e.g. variance shift with stable mean).

Why a fraction-of-columns aggregate?
  At alpha=0.05, ~5% of features will trigger by chance even on iid
  data. We require >= ``flag_fraction`` (default 0.20) of features to
  drift before raising the alarm — the practitioner-standard balance
  between sensitivity and false-alarm rate.

Cost
  ~O(n_features × n_live × log(n_ref)). For 17 features × 252 live × 10k
  reference: <50ms on commodity CPU. Run once per session start; do
  *not* call per-bar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class DriftReport:
    """Outcome of one drift check."""

    drifted: bool
    fraction_flagged: float
    flagged_columns: list[str]
    p_values: dict[str, float] = field(default_factory=dict)
    n_reference: int = 0
    n_live: int = 0

    def summary(self) -> str:
        if not self.drifted:
            return (f"no drift (flagged {self.fraction_flagged:.0%} of "
                    f"{len(self.p_values)} cols)")
        worst = sorted(self.p_values.items(), key=lambda kv: kv[1])[:5]
        worst_str = ", ".join(f"{c} p={p:.4f}" for c, p in worst)
        return (f"DRIFT detected: {self.fraction_flagged:.0%} of "
                f"{len(self.p_values)} cols (worst: {worst_str})")


def _ks_pvalue(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample KS p-value.

    Prefers ``scipy.stats.ks_2samp`` when available; otherwise computes
    the Kolmogorov asymptotic p-value from the sup-distance D (this is
    accurate for n >= ~30 per sample which is always true for our
    use case).
    """
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return 1.0     # not enough data → don't flag
    try:
        from scipy.stats import ks_2samp
        return float(ks_2samp(a, b).pvalue)
    except ImportError:
        # Manual implementation: D = sup |F_a(x) - F_b(x)|.
        a_sorted = np.sort(a)
        b_sorted = np.sort(b)
        all_x = np.concatenate([a_sorted, b_sorted])
        cdf_a = np.searchsorted(a_sorted, all_x, side="right") / len(a_sorted)
        cdf_b = np.searchsorted(b_sorted, all_x, side="right") / len(b_sorted)
        d = float(np.max(np.abs(cdf_a - cdf_b)))
        # Kolmogorov asymptotic p-value (Smirnov 1948 series approximation,
        # truncated at first term — good to 1% for d > 0.05).
        n = len(a_sorted) * len(b_sorted) / (len(a_sorted) + len(b_sorted))
        lam = (np.sqrt(n) + 0.12 + 0.11 / np.sqrt(n)) * d
        # Two-term series.
        p = 2.0 * np.exp(-2.0 * lam ** 2) - 2.0 * np.exp(-8.0 * lam ** 2)
        return float(np.clip(p, 0.0, 1.0))


class FeatureDriftDetector:
    """Per-column KS drift check against a reference distribution.

    Parameters
    ----------
    reference:
        DataFrame holding the training (or last-known-good) feature
        distribution. Index is ignored.
    columns:
        Subset of feature columns to monitor. ``None`` = all numeric
        columns of ``reference`` except ``close`` and ``atr`` (the
        passthroughs from ``build_features``).
    alpha:
        Per-column significance level. Default 0.05.
    flag_fraction:
        Threshold for the aggregate drift flag. Default 0.20 (i.e. >=20%
        of monitored columns must trip before ``drifted=True``).
    """

    def __init__(
        self,
        reference: pd.DataFrame,
        columns: Optional[list[str]] = None,
        alpha: float = 0.05,
        flag_fraction: float = 0.20,
    ) -> None:
        if columns is None:
            columns = [c for c in reference.columns
                       if c not in ("close", "atr")
                       and pd.api.types.is_numeric_dtype(reference[c])]
        if not columns:
            raise ValueError("FeatureDriftDetector: no numeric columns to monitor")
        self._columns = list(columns)
        self._reference: dict[str, np.ndarray] = {
            c: reference[c].to_numpy(dtype=np.float64)
            for c in self._columns
        }
        self._alpha = float(alpha)
        self._flag_fraction = float(flag_fraction)

    @property
    def columns(self) -> list[str]:
        return list(self._columns)

    def check(self, live: pd.DataFrame) -> DriftReport:
        """Compare ``live`` against the reference distribution.

        Columns missing from ``live`` are skipped (logged at debug). All
        columns present in both are compared with a two-sample KS test.
        """
        n_ref = max(len(arr) for arr in self._reference.values()) if self._reference else 0
        n_live = len(live)

        p_values: dict[str, float] = {}
        flagged: list[str] = []
        for col in self._columns:
            if col not in live.columns:
                log.debug("drift: column %s not in live frame", col)
                continue
            ref = self._reference[col]
            cur = live[col].to_numpy(dtype=np.float64)
            p = _ks_pvalue(ref, cur)
            p_values[col] = p
            if p < self._alpha:
                flagged.append(col)

        n_checked = len(p_values)
        frac = len(flagged) / n_checked if n_checked else 0.0
        return DriftReport(
            drifted=frac >= self._flag_fraction,
            fraction_flagged=frac,
            flagged_columns=flagged,
            p_values=p_values,
            n_reference=n_ref,
            n_live=n_live,
        )
