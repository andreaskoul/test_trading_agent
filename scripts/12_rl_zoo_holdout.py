"""Exploratory: the existing 168 RL policies on the 2023-26 holdout, under the
causal feature rebuild and bracket fills. Not a protocol trial; it answers
"how do the policies we already have compare with the baseline ladder on
the same test".

    python scripts/12_rl_zoo_holdout.py   # -> reports/research/rl_zoo_holdout.parquet
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.data.features import feature_columns
from src.data.regimes import HMMRegimeModel
from src.env.trading_env import EnvConfig
from src.live.paper_engine import CostModel, PaperEngine
from src.models.precompute import precompute_embeddings
from src.training.pretrain_encoder import load_encoder
import step_one_bar as sob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = {"__repo_root__": ROOT}
f = pd.read_parquet(os.path.join(ROOT, "data/processed/features_gc_extended_holdout.parquet"))
cols = feature_columns(f)
close, atr = f["close"].to_numpy(np.float64), f["atr"].to_numpy(np.float64)
vol_q = pd.Series(atr / close).expanding().rank(pct=True).to_numpy()
env_cfg = EnvConfig(seq_len=32, horizon=4, rr_upper=1.5, rr_lower=0.75, spread_bps=0.5, fill_model="bracket")
cost = CostModel(spread_bps=0.5, slippage_bps=0.3)
manifest = json.load(open(os.path.join(ROOT, "artefacts/ppo_manifest.json")))

emb, post, rows = {}, {}, []
t0 = time.time()
for m, e in enumerate(manifest):
    g = int(e["encoder_group"])
    if g not in emb:
        emb[g] = precompute_embeddings(load_encoder(os.path.join(ROOT, f"artefacts/encoders/encoder_group{g}.pt")),
                                       f[cols].to_numpy(np.float32), seq_len=32)
    rp = sob._normalize_artefact_path(cfg, e["regime_path"])
    if rp not in post:
        post[rp] = HMMRegimeModel.load(rp).posterior(close)
    pc = {"close": close, "atr": atr, "embeddings": emb[g], "vol_quantile": vol_q,
          "regime_posterior": post[rp], **{k: f[k].to_numpy(np.float64) for k in ("open", "high", "low")}}
    eng = PaperEngine(asset="GC=F", run_id=f"m{m}", model=sob._load_policy(cfg, e), precomputed=pc,
                      env_cfg=env_cfg, cost_model=cost, timestamps=f.index)
    for i in range(32, len(close)):
        eng.step(i)
    for r in eng.trade_records():
        rows.append(dict(model=m, algo=e["algorithm"], split=e["split"], seed=e["seed"], group=g,
                         direction=r.direction, entry_ts=r.entry_ts, exit_ts=r.exit_ts,
                         barrier=r.barrier, ret=r.pnl))
    if m % 12 == 0:
        print(f"model {m}/{len(manifest)} {time.time() - t0:.0f}s", flush=True)
pd.DataFrame(rows).to_parquet(os.path.join(ROOT, "reports/research/rl_zoo_holdout.parquet"))
print("done", len(rows))
