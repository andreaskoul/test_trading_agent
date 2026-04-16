"""Natural-language trade explanations via the Claude API.

Given a trade row from the SQLite store, build a compact structured
context (direction, P&L, entry/exit prices, meta-label probability,
HMM regime, top-extreme embedding and feature z-scores) and ask Claude
to write a short explanation grounded in those numbers.

The prompt caches the static system prompt so repeated explanations in
a session re-use the cache and avoid paying for the full prompt on
each call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "You are explaining a single trade made by a frozen reinforcement-learning "
    "policy in a research backtest.\n"
    "You will receive a JSON blob with the trade's direction, prices, realised "
    "P&L, the meta-label model's probability of profit, the HMM regime index, "
    "the volatility quantile, the top most-extreme encoder embedding dimensions, "
    "and the top most-extreme raw feature z-scores at entry.\n"
    "Write a plain-English paragraph that:\n"
    "  - States the side, entry and exit prices, and realised P&L.\n"
    "  - Anchors the decision in the meta-label probability and the regime.\n"
    "  - Cites at most two of the extreme feature z-scores.\n"
    "  - Does NOT speculate about fundamentals, news, or macroeconomic context.\n"
    "  - Uses at most {max_words} words total.\n"
    "If the trade was a loss, be honest about it rather than rationalising."
)


def _build_context(trade: dict, max_top: int = 3) -> dict:
    """Pick the interpretable bits out of a stored trade row."""
    ctx: dict = {
        "asset": trade.get("asset"),
        "direction": trade.get("direction"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "pnl": trade.get("pnl"),
        "barrier": trade.get("barrier"),
        "meta_prob": trade.get("meta_prob"),
        "regime_idx": trade.get("regime_idx"),
        "vol_q": trade.get("vol_q"),
        "entry_ts": trade.get("entry_ts"),
        "exit_ts": trade.get("exit_ts"),
    }
    emb_json = trade.get("embedding_json")
    feats_json = trade.get("entry_features_json")
    if emb_json:
        try:
            emb = np.asarray(json.loads(emb_json), dtype=np.float32)
            # Report the dims whose absolute value is most extreme —
            # these are the "loudest" activations the policy saw.
            order = np.argsort(-np.abs(emb))[:max_top]
            ctx["top_embedding_dims"] = [
                {"dim": int(d), "z": float(emb[d])} for d in order
            ]
        except Exception as exc:  # pragma: no cover
            log.warning("emb json parse failed: %s", exc)
    if feats_json:
        try:
            feats = np.asarray(json.loads(feats_json), dtype=np.float32)
            # The feature vector is [embedding(128), direction, vol_q].
            # We don't have named raw features here, so report the top
            # extreme indices in the packed vector as a proxy — the
            # dashboard can map them back if needed.
            order = np.argsort(-np.abs(feats))[:max_top]
            ctx["top_entry_feature_dims"] = [
                {"dim": int(d), "z": float(feats[d])} for d in order
            ]
        except Exception as exc:  # pragma: no cover
            log.warning("feature json parse failed: %s", exc)
    return ctx


def _fallback_text(ctx: dict, max_words: int) -> str:
    """Deterministic local explanation when the Anthropic SDK is absent."""
    side = "long" if ctx.get("direction") == 1 else "short"
    pnl = ctx.get("pnl") or 0.0
    meta = ctx.get("meta_prob")
    regime = ctx.get("regime_idx")
    entry = ctx.get("entry_price") or 0.0
    exit_ = ctx.get("exit_price") or 0.0
    barrier = ctx.get("barrier") or "timeout"
    pnl_bps = pnl * 1e4
    meta_str = f"{meta:.2f}" if isinstance(meta, (int, float)) else "n/a"
    regime_str = str(regime) if regime is not None else "n/a"
    text = (
        f"{side.capitalize()} {ctx.get('asset','?')} at {entry:.2f}, "
        f"exited at {exit_:.2f} via {barrier} for {pnl_bps:+.1f} bps. "
        f"Meta-label probability of profit was {meta_str}; HMM regime {regime_str}. "
        "Policy acted on the embedding state at entry."
    )
    # Cap to max_words.
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])
    return text


async def explain_trade(trade: dict, cfg: dict) -> str:
    """Return a short NL explanation of ``trade`` using Claude.

    Falls back to a deterministic template if ``anthropic`` isn't
    installed or the ``ANTHROPIC_API_KEY`` env var is missing — the
    cockpit still functions, just without generative text.
    """
    ui_cfg = cfg.get("ui", {}).get("explain", {})
    model_id = ui_cfg.get("model", "claude-opus-4-7")
    max_words = int(ui_cfg.get("max_words", 120))
    ctx = _build_context(trade)

    try:
        import anthropic  # type: ignore
    except ImportError:
        log.info("anthropic SDK not installed; using fallback explanation")
        return _fallback_text(ctx, max_words)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("ANTHROPIC_API_KEY not set; using fallback explanation")
        return _fallback_text(ctx, max_words)

    system = [
        {
            "type": "text",
            "text": _SYSTEM_PROMPT.format(max_words=max_words),
            "cache_control": {"type": "ephemeral"},
        }
    ]
    user = (
        "Trade context JSON (use only these numbers):\n"
        + json.dumps(ctx, indent=2)
    )

    def _call() -> str:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model_id,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts).strip() or _fallback_text(ctx, max_words)

    try:
        return await asyncio.to_thread(_call)
    except Exception as exc:
        log.warning("anthropic call failed (%s); using fallback", exc)
        return _fallback_text(ctx, max_words)
