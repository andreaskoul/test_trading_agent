"""Mutual-information feature selection (Phase G / iter-6).

Wraps sklearn's Kraskov kNN-based ``mutual_info_classif`` estimator to rank
candidate features against the multi-class triple-barrier target and drop
those that carry less MI than a configured threshold. Keeps a small
passthrough whitelist (``close``, ``atr``) that the env requires regardless
of predictive power.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def mi_filter(
    feats: pd.DataFrame,
    labels: np.ndarray,
    threshold: float = 0.003,
    always_keep: Sequence[str] = ("close", "atr"),
    always_score: Sequence[str] = (),
    random_state: int = 7,
) -> Tuple[List[str], List[Tuple[str, float]]]:
    """Return (kept_cols, ranking) where `ranking` is [(col, mi_bits), ...].

    Any column in ``always_keep`` bypasses the threshold. Columns in
    ``always_score`` are scored but only kept if they clear the threshold;
    everything else is scored and thresholded. ``labels`` must be integer
    class indices (e.g. mapped triple-barrier labels in {0, 1, 2}).
    """
    try:
        from sklearn.feature_selection import mutual_info_classif
    except Exception as exc:
        log.warning("sklearn MI unavailable (%s); keeping all columns", exc)
        return list(feats.columns), []

    keep_set = set(always_keep)
    score_cols = [c for c in feats.columns if c not in keep_set]
    if not score_cols:
        return list(feats.columns), []

    X = feats[score_cols].to_numpy(dtype=np.float64)
    y = np.asarray(labels, dtype=np.int64)
    mask = np.isfinite(X).all(axis=1) & np.isfinite(y)
    if mask.sum() < 100:
        log.warning("MI filter: only %d finite rows; skipping", int(mask.sum()))
        return list(feats.columns), []
    mi = mutual_info_classif(X[mask], y[mask], random_state=random_state)
    ranking = sorted(zip(score_cols, mi.tolist()), key=lambda t: t[1], reverse=True)

    kept = [c for c in feats.columns if c in keep_set]
    for col, score in ranking:
        if score >= threshold or col in always_score:
            kept.append(col)

    # Preserve input column order for kept non-passthrough features.
    kept_unique: list[str] = []
    for c in feats.columns:
        if c in kept and c not in kept_unique:
            kept_unique.append(c)

    dropped = [c for c, s in ranking if s < threshold and c not in keep_set]
    log.info(
        "MI filter: kept %d / %d (threshold=%.4f); dropped %s",
        len(kept_unique), len(feats.columns), threshold, dropped,
    )
    for col, score in ranking:
        log.info("  MI  %s = %.5f", col, score)
    return kept_unique, ranking
