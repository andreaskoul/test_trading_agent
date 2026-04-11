"""Combinatorial Purged K-Fold Cross Validation (Lopez de Prado, AFML Ch. 12).

Partitions the time series into N sequential groups, tests k of them at a
time. For (N, k) = (6, 2) this yields C(6,2)=15 unique splits which can be
reassembled into 5 full backtest paths (each of the N groups appears as a
test block in exactly floor(15 * k / N) = 5 of the splits).

Purging: any training sample whose `t1` (end-of-label timestamp) falls
within a test block is removed so forward-looking labels do not leak.

Embargo: a small number of training samples immediately after each test
block are additionally removed to handle autocorrelation.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterator, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class CPCVSplit:
    train_idx: np.ndarray
    test_idx: np.ndarray
    test_groups: Tuple[int, ...]


def _group_bounds(n_samples: int, n_splits: int) -> List[Tuple[int, int]]:
    edges = np.linspace(0, n_samples, n_splits + 1, dtype=int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(n_splits)]


def _purge_train(
    train_idx: np.ndarray,
    test_bounds: List[Tuple[int, int]],
    t1: pd.Series,
) -> np.ndarray:
    """Remove training samples whose label window overlaps ANY test block.

    test_bounds is a list of [lo, hi) tuples (one per test group), so that
    disjoint combinations such as {group 0, group 5} are purged correctly
    (the earlier implementation treated the union as one contiguous block
    and purged the entire middle).

    Integer positions are used throughout to avoid tz-aware / tz-naive
    timestamp comparison pitfalls.
    """
    if not test_bounds:
        return train_idx

    # Compute integer position of each label's t1 endpoint.
    try:
        idx_ns = pd.DatetimeIndex(t1.index).asi8
        t1_ns = pd.DatetimeIndex(t1.values).asi8
    except Exception:
        idx_ns = np.asarray(t1.index.values, dtype="datetime64[ns]").astype(np.int64)
        t1_ns = np.asarray(t1.values, dtype="datetime64[ns]").astype(np.int64)
    t1_pos = np.searchsorted(idx_ns, t1_ns)
    t1_pos = np.clip(t1_pos, 0, len(idx_ns) - 1)

    label_start = train_idx.astype(int)
    label_end = t1_pos[label_start].astype(int)
    keep = np.ones(len(train_idx), dtype=bool)
    for lo, hi in test_bounds:
        # test block covers integer positions [lo, hi) i.e. closed range [lo, hi-1]
        test_lo = int(lo)
        test_hi = int(hi - 1)
        overlap = ~((label_end < test_lo) | (label_start > test_hi))
        keep &= ~overlap
    return train_idx[keep]


def _embargo(
    train_idx: np.ndarray,
    test_bounds: List[Tuple[int, int]],
    embargo: int,
    n_samples: int,
) -> np.ndarray:
    if embargo <= 0:
        return train_idx
    forbidden = np.zeros(n_samples, dtype=bool)
    for lo, hi in test_bounds:
        forbidden[hi : min(hi + embargo, n_samples)] = True
    return train_idx[~forbidden[train_idx]]


class CombinatorialPurgedKFold:
    def __init__(self, n_splits: int = 6, n_test_splits: int = 2, embargo_pct: float = 0.01):
        if n_test_splits >= n_splits:
            raise ValueError("n_test_splits must be < n_splits")
        self.n_splits = n_splits
        self.n_test_splits = n_test_splits
        self.embargo_pct = embargo_pct

    def split(
        self, t1: pd.Series
    ) -> Iterator[CPCVSplit]:
        n = len(t1)
        groups = _group_bounds(n, self.n_splits)
        embargo = int(self.embargo_pct * n)
        all_groups = list(range(self.n_splits))

        for test_combo in combinations(all_groups, self.n_test_splits):
            test_bounds = [groups[g] for g in test_combo]
            test_idx = np.concatenate([np.arange(lo, hi) for lo, hi in test_bounds])
            train_candidates = np.setdiff1d(np.arange(n), test_idx, assume_unique=True)
            train_idx = _purge_train(train_candidates, test_bounds, t1)
            train_idx = _embargo(train_idx, test_bounds, embargo, n)
            yield CPCVSplit(train_idx=train_idx, test_idx=test_idx, test_groups=test_combo)

    def backtest_paths(self, t1: pd.Series) -> List[List[Tuple[int, np.ndarray]]]:
        """Reassemble CPCV splits into full backtest paths.

        Each path is a list of (group_id, test_idx_for_that_group) tuples
        covering the full series. With N splits, k test groups, we have
        C(N,k)*k/N paths.
        """
        splits = list(self.split(t1))
        n_paths = len(splits) * self.n_test_splits // self.n_splits
        groups = _group_bounds(len(t1), self.n_splits)
        # Pool of test-block assignments per group, FIFO
        pool: dict[int, list[np.ndarray]] = {g: [] for g in range(self.n_splits)}
        for sp in splits:
            for g in sp.test_groups:
                lo, hi = groups[g]
                pool[g].append(np.arange(lo, hi))
        paths = []
        for _ in range(n_paths):
            path = []
            for g in range(self.n_splits):
                if pool[g]:
                    path.append((g, pool[g].pop(0)))
            paths.append(path)
        return paths
