"""Launch the trading cockpit with artefact preflight.

Usage::

    python scripts/run_cockpit.py                       # default profile
    python scripts/run_cockpit.py --profile live        # live overlay
    python scripts/run_cockpit.py --profile aggressive --port 9000

The launcher refuses to boot when critical artefacts are missing — there
is no point opening the UI if there are no policies to load. Run the
training pipeline first (``scripts/01_build_data.py`` ->
``02_pretrain_encoder.py`` -> ``03_train_ppo.py``) to produce them.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from _bootstrap import setup, path

log = logging.getLogger("run_cockpit")


def _check_artefacts(cfg: dict) -> list[str]:
    """Return a list of missing-artefact messages (empty = ready to boot)."""
    missing: list[str] = []
    art_dir = path(cfg, cfg["artefact_dir"])
    manifest = os.path.join(art_dir, "ppo_manifest.json")
    if not os.path.exists(manifest):
        missing.append(f"manifest: {manifest}")

    # At least one encoder + at least one features parquet.
    enc_dir = os.path.join(art_dir, "encoders")
    if not os.path.isdir(enc_dir) or not any(
        f.endswith(".pt") for f in os.listdir(enc_dir)
    ):
        missing.append(f"encoders directory: {enc_dir}")

    feat_paths = [
        path(cfg, a.get("features_path", ""))
        for a in cfg.get("data", {}).get("assets", [])
        if a.get("features_path")
    ]
    if feat_paths and not any(os.path.exists(p) for p in feat_paths):
        missing.append(f"features parquets: none of {feat_paths} exist")

    return missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=os.environ.get("TRADING_PROFILE", ""),
                        help="config overlay (e.g. 'live', 'aggressive')")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--skip-preflight", action="store_true",
                        help="boot even if critical artefacts are missing "
                             "(useful for UI-only smoke tests)")
    args = parser.parse_args()

    if args.profile:
        os.environ["TRADING_PROFILE"] = args.profile

    cfg = setup()    # respects TRADING_PROFILE

    missing = [] if args.skip_preflight else _check_artefacts(cfg)
    if missing:
        log.error("cannot start cockpit; missing artefacts:")
        for m in missing:
            log.error("  - %s", m)
        log.error("run scripts/01_build_data.py through 03_train_ppo.py first, "
                  "or pass --skip-preflight to ignore")
        sys.exit(2)

    profile_label = args.profile or "default"
    log.info("starting cockpit (profile=%s) on %s:%d",
             profile_label, args.host, args.port)

    try:
        import uvicorn
    except ImportError:
        log.error("uvicorn not installed; pip install uvicorn[standard]")
        sys.exit(2)

    uvicorn.run("src.ui.server:app", host=args.host, port=args.port,
                log_level="info")


if __name__ == "__main__":
    main()
