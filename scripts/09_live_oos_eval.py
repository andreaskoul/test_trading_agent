"""Out-of-sample evaluation of the whole policy zoo on the live window.

Every policy in artefacts/ppo_manifest.json was trained on 2012-2022 spot
data; 1 Apr 2026 onward is untouched by training, selection and tuning, so
it is the one clean test the project has. We replay every policy through the
same PaperEngine the cron uses, at unit size (no Kelly, no regime sizing),
and record per-trade returns under two information sets:

  causal : macro closes lagged to availability, forward-filtered HMM
           regime, expanding vol rank  (what live trading can know)
  leaky  : macro closes on their own date, smoothed HMM, full-sample rank
           (what the pre-fix code computed)

and two execution assumptions for each trade:

  engine : fill at the bar close that triggered, barrier price on exits
  next   : fill at the next bar's open, the earliest a cron job can act

Outputs reports/live_oos/{trades.parquet, summary.json}.

    TRADING_PROFILE=live python scripts/09_live_oos_eval.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

from _bootstrap import setup, path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
sob = importlib.import_module("step_one_bar")

from src.data.features import PASSTHROUGH, build_features, feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import env_config_from_yaml
from src.live.paper_engine import CostModel, PaperEngine
from src.models.precompute import precompute_embeddings
from src.training.pretrain_encoder import load_encoder

LIVE_START = pd.Timestamp("2026-04-01", tz="UTC")

cfg = setup()
asset = sob.parse_asset_configs(cfg)[0]
env_cfg = env_config_from_yaml(cfg)
out_dir = path(cfg, "reports", "live_oos")
os.makedirs(out_dir, exist_ok=True)

train = pd.read_parquet(path(cfg, asset.raw_path))
live = sob._fetch_bars_since(asset.symbol, asset.interval, LIVE_START - pd.Timedelta(hours=1))
live = live[live.index >= LIVE_START]
ohlcv = pd.concat([train, live])
ohlcv = ohlcv[~ohlcv.index.duplicated(keep="last")].sort_index()
ref_cols = feature_columns(pd.read_parquet(path(cfg, asset.features_path)))
macro = sob._fetch_macro_data(ref_cols, train.index.min())
w = int(cfg["features"]["warmup_bars"])
zw = int(cfg["features"]["zscore_window"])

manifest = json.load(open(path(cfg, cfg["artefact_dir"], "ppo_manifest.json")))
paper = cfg["ui"]["paper"]
cost = CostModel(**{k: float(v) for k, v in paper["costs"].items()})

trades = []
for info in ("causal", "leaky"):
    lag = pd.Timedelta(days=1) if info == "causal" else pd.Timedelta(0)
    feats = build_features(ohlcv, warmup_bars=w, zscore_window=zw, macro_data=macro, macro_lag=lag)
    feats = feats[ref_cols + list(PASSTHROUGH)]
    i0 = int(np.argmax(feats.index >= LIVE_START))
    # Embeddings only need the last seq_len rows before the live window.
    lo = i0 - env_cfg.seq_len + 1
    close = feats["close"].to_numpy(np.float64)
    atr = feats["atr"].to_numpy(np.float64)
    rv = pd.Series(atr / close)
    vol_q = (rv.expanding().rank(pct=True) if info == "causal" else rv.rank(pct=True)).to_numpy()
    opens = ohlcv["open"].reindex(feats.index).to_numpy(np.float64)
    if info == "causal":
        pd.DataFrame({"open": opens, "high": ohlcv["high"].reindex(feats.index).to_numpy(),
                      "low": ohlcv["low"].reindex(feats.index).to_numpy(),
                      "close": close, "atr": atr, "vol_q": vol_q},
                     index=feats.index).iloc[lo:].to_parquet(os.path.join(out_dir, "bars.parquet"))

    emb_cache: dict[int, np.ndarray] = {}
    post_cache: dict[str, np.ndarray] = {}
    t0 = time.time()
    for m_idx, e in enumerate(manifest):
        g = int(e["encoder_group"])
        if g not in emb_cache:
            enc = load_encoder(path(cfg, cfg["artefact_dir"], "encoders", f"encoder_group{g}.pt"))
            emb_cache[g] = precompute_embeddings(enc, feats[ref_cols].to_numpy(np.float32)[lo:],
                                                 seq_len=env_cfg.seq_len)
        rp = sob._normalize_artefact_path(cfg, e["regime_path"])
        if rp not in post_cache:
            hmm = HMMRegimeModel.load(rp)
            post_cache[rp] = (hmm.filtered_posterior(close) if info == "causal"
                              else hmm.posterior(close))[lo:]
        pc = {"close": close[lo:], "atr": atr[lo:], "embeddings": emb_cache[g],
              **{k: feats[k].to_numpy(np.float64)[lo:] for k in ("open", "high", "low")},
              "vol_quantile": vol_q[lo:], "regime_posterior": post_cache[rp]}
        eng = PaperEngine(asset=asset.symbol, run_id=f"m{m_idx}", model=sob._load_policy(cfg, e),
                          precomputed=pc, env_cfg=env_cfg, cost_model=cost,
                          meta_threshold=0.55, timestamps=feats.index[lo:], store=None)
        for i in range(env_cfg.seq_len - 1, len(pc["close"])):
            eng.step(i)
        base = 2 * env_cfg.spread_bps / 1e4
        for r in eng.trade_records():
            a, b = r.entry_idx + lo, r.exit_idx + lo
            c = cost.roundtrip_deduction(r.entry_price, r.vol_q)
            nxt_in = opens[a + 1] if a + 1 < len(opens) else np.nan
            nxt_out = opens[b + 1] if b + 1 < len(opens) else np.nan
            trades.append(dict(
                info=info, model=m_idx, algo=e["algorithm"], split=e["split"], seed=e["seed"],
                group=g, direction=r.direction, entry_ts=feats.index[a], exit_ts=feats.index[b],
                bars=b - a, barrier=r.barrier, regime=r.regime_idx,
                ret_booked=r.direction * (r.exit_price / r.entry_price - 1) - max(c, base),
                ret_next_open=r.direction * (nxt_out / nxt_in - 1) - max(c, base),
                # passive benchmark over the identical holding period
                mkt=close[b] / close[a] - 1,
            ))
        if m_idx % 24 == 0:
            print(f"{info} model {m_idx}/{len(manifest)}  {time.time() - t0:.0f}s", flush=True)

T = pd.DataFrame(trades)
T.to_parquet(os.path.join(out_dir, "trades.parquet"))

# Per-bar buy & hold over the live window, for context.
lc = live["close"]
json.dump({
    "live_start": str(LIVE_START), "live_end": str(live.index.max()), "n_bars": int(len(live)),
    "gold_ret": float(lc.iloc[-1] / lc.iloc[0] - 1), "n_models": len(manifest),
    "env": {"horizon": env_cfg.horizon, "rr_upper": env_cfg.rr_upper, "rr_lower": env_cfg.rr_lower,
            "spread_bps": env_cfg.spread_bps},
    "macro_last": {k: str(v.index[-1].date()) for k, v in macro.items()},
}, open(os.path.join(out_dir, "meta.json"), "w"), indent=2)
print("wrote", len(T), "trades")
