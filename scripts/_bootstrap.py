"""Common setup for entry-point scripts: load config, configure logging.

Importing this module puts the repository root on sys.path so the scripts
can do `from src.data.loader import ...` without relying on PYTHONPATH.
"""

from __future__ import annotations

import logging
import os
import sys

import yaml

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base. Overlay lists replace, dicts merge."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def setup() -> dict:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg_path = os.path.join(_REPO_ROOT, "configs", "default.yaml")
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)
    # Overlay profile, e.g. `TRADING_PROFILE=aggressive` -> merges
    # configs/aggressive.yaml on top of default.yaml (recursively).
    profile = os.environ.get("TRADING_PROFILE", "").strip()
    if profile:
        profile_path = os.path.join(_REPO_ROOT, "configs", f"{profile}.yaml")
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                overlay = yaml.safe_load(f) or {}
            cfg = _deep_merge(cfg, overlay)
            logging.getLogger("bootstrap").info("applied profile %s", profile)
        else:
            logging.getLogger("bootstrap").warning(
                "TRADING_PROFILE=%s set but %s not found; using default", profile, profile_path,
            )
    cfg["__repo_root__"] = _REPO_ROOT
    return cfg


def path(cfg: dict, *parts: str) -> str:
    return os.path.join(cfg["__repo_root__"], *parts)
