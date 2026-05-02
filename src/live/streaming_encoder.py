"""Streaming feature + encoder pipeline for live bar ingestion.

``StreamingEncoder`` maintains a circular OHLCV buffer and, on each new
bar, computes features for the latest window then encodes one embedding
vector — exactly the data the policy needs at bar ``t`` without
precomputing the full historical matrix.

Why a circular buffer?
  Rolling z-score normalisation requires ~zscore_window (252) bars of
  history. We hold ``zscore_window + seq_len`` raw OHLCV rows so the
  z-score and EMA lookbacks are always satisfied.

Integration with PaperEngine:
  PaperEngine stores immutable numpy arrays at construction time. The live
  path needs to grow them bar-by-bar. ``PaperEngine.extend_precomputed()``
  (added in Phase J) appends a new bar's data and returns the new index
  so ``step(new_idx)`` can proceed identically to replay mode.

Usage::

    enc = StreamingEncoder(encoder, feat_cols, env_cfg, hist_df)
    for bar in feed:
        idx = enc.update(bar)
        if idx is not None:
            sig = engine.step(idx)
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Optional

import numpy as np
import pandas as pd

from ..data.features import build_features, feature_columns
from ..models.xlstm_lite import XLSTMLite
from ..models.precompute import build_rolling_windows

log = logging.getLogger(__name__)


class StreamingEncoder:
    """Incremental feature builder + encoder for the live path.

    Parameters
    ----------
    encoder:
        Frozen xLSTM-lite encoder (from ``load_encoder``).
    env_seq_len:
        Policy's look-back sequence length (from ``env_cfg.seq_len``).
    history:
        Initial OHLCV DataFrame (the tail of the precomputed window).
        Must contain at least ``zscore_window`` rows so rolling stats
        are warm from the first live bar. Typically the last
        ``zscore_window + seq_len`` rows of the training feature parquet.
    zscore_window:
        Rolling normalisation window (must match training config).
    warmup_bars:
        ``build_features`` drops the first ``warmup_bars`` rows (they
        have NaN rolling stats). We set this to 0 here because we feed
        already-warm history; ``build_features`` is called on the buffer
        only to extract the **last** row.
    """

    def __init__(
        self,
        encoder: XLSTMLite,
        env_seq_len: int,
        history: pd.DataFrame,
        zscore_window: int = 252,
        warmup_bars: int = 0,
    ) -> None:
        import torch
        self._encoder = encoder
        self._encoder.eval()
        self._seq_len = int(env_seq_len)
        self._zscore_window = int(zscore_window)
        self._warmup_bars = int(warmup_bars)

        # How many OHLCV rows to keep.
        # Breakdown of what each feature needs:
        #   ema_100_dist: min_periods=100 (EMA span) + zscore_window
        #   rv_60:        60 (rolling std) + zscore_window
        #   atm atr:      14 bars
        # The binding constraint is the EMA span=100 plus zscore_window.
        # Add seq_len so a full sequence window is always available after warmup.
        _ema_warmup = 100   # matches the max EMA span in build_features
        self._buf_size = _ema_warmup + self._zscore_window + self._seq_len + 64

        # Seed the OHLCV buffer from the tail of the historical parquet.
        # Keep only the columns the feature builder needs.
        needed_cols = [c for c in ("open", "high", "low", "close", "volume")
                       if c in history.columns]
        hist_tail = history[needed_cols].iloc[-self._buf_size:]
        self._buf: deque[pd.Series] = deque(
            [row for _, row in hist_tail.iterrows()],
            maxlen=self._buf_size,
        )
        self._timestamps: deque[pd.Timestamp] = deque(
            list(hist_tail.index)
            if isinstance(hist_tail.index, pd.DatetimeIndex)
            else [pd.Timestamp("1970-01-01")] * len(hist_tail),
            maxlen=self._buf_size,
        )

        # Determine feature column order from the first full computation.
        self._feat_cols: Optional[list[str]] = None
        if len(self._buf) >= self._zscore_window:
            self._feat_cols = self._compute_feat_cols()

        self._torch = torch

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _buf_to_df(self) -> pd.DataFrame:
        """Rebuild a DataFrame from the circular buffer for feature computation."""
        df = pd.DataFrame(list(self._buf))
        if self._timestamps:
            ts = list(self._timestamps)
            df.index = pd.DatetimeIndex(ts)
        return df

    def _compute_feat_cols(self) -> list[str]:
        df = self._buf_to_df()
        feats = build_features(df, warmup_bars=self._warmup_bars,
                               zscore_window=self._zscore_window)
        return feature_columns(feats)

    def _encode_window(self, feat_rows: np.ndarray) -> np.ndarray:
        """Encode a (seq_len, n_features) window → (hidden_size,) embedding."""
        window = feat_rows[-self._seq_len:]
        pad_len = self._seq_len - len(window)
        if pad_len > 0:
            window = np.vstack([np.zeros((pad_len, window.shape[1]), dtype=np.float32), window])
        tensor = self._torch.from_numpy(window[np.newaxis].astype(np.float32))
        with self._torch.no_grad():
            emb = self._encoder.encode(tensor)
        return emb.cpu().numpy()[0]

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    @property
    def ready(self) -> bool:
        """True once the buffer has enough bars for accurate z-scores."""
        return len(self._buf) >= self._zscore_window

    def update(self, bar) -> Optional[dict]:
        """Ingest one new bar and return a dict of new-bar arrays, or None
        during warmup.

        The returned dict has keys:
          ``close``, ``atr``, ``embedding``, ``vol_quantile``, ``ts``

        Caller should pass this to ``PaperEngine.extend_precomputed()`` to
        get a new bar index and then call ``engine.step(new_idx)``.
        """
        # Accept both a Bar dataclass and a plain dict/Series
        if hasattr(bar, "open"):
            row_data = {
                "open": float(bar.open), "high": float(bar.high),
                "low": float(bar.low), "close": float(bar.close),
                "volume": float(bar.volume),
            }
            ts = bar.ts if hasattr(bar, "ts") else pd.Timestamp.now(tz="UTC")
        else:
            row_data = {k: float(v) for k, v in bar.items()
                        if k in ("open", "high", "low", "close", "volume")}
            ts = bar.get("ts", pd.Timestamp.now(tz="UTC"))

        # Validate OHLCV before ingesting
        for k, v in row_data.items():
            if not np.isfinite(v) or v <= 0:
                log.warning("streaming encoder rejected bar: %s=%s", k, v)
                return None

        self._buf.append(pd.Series(row_data))
        self._timestamps.append(ts)

        if not self.ready:
            return None

        # Build features on the full buffer; extract the last row.
        try:
            df = self._buf_to_df()
            feats_df = build_features(df, warmup_bars=self._warmup_bars,
                                      zscore_window=self._zscore_window)
            if len(feats_df) == 0:
                return None
            if self._feat_cols is None:
                self._feat_cols = feature_columns(feats_df)
        except Exception as exc:
            log.warning("streaming encoder feature build failed: %s", exc)
            return None

        feat_arr = feats_df[self._feat_cols].to_numpy(dtype=np.float32)
        close_arr = feats_df["close"].to_numpy(dtype=np.float64)
        atr_arr = feats_df["atr"].to_numpy(dtype=np.float64)

        # Compute embedding for the last bar
        try:
            emb = self._encode_window(feat_arr)
        except Exception as exc:
            log.warning("streaming encoder encode failed: %s", exc)
            return None

        # vol_quantile for the last bar (rolling percentile rank of ATR/close)
        rv = atr_arr / np.maximum(close_arr, 1e-12)
        vol_q = float(np.sum(rv <= rv[-1]) / max(len(rv), 1))

        return {
            "close": float(close_arr[-1]),
            "atr": float(atr_arr[-1]),
            "embedding": emb,
            "vol_quantile": vol_q,
            "ts": feats_df.index[-1] if isinstance(feats_df.index, pd.DatetimeIndex) else ts,
        }
