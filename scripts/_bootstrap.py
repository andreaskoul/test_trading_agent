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


def setup() -> dict:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg_path = os.path.join(_REPO_ROOT, "configs", "default.yaml")
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)
    cfg["__repo_root__"] = _REPO_ROOT
    return cfg


def path(cfg: dict, *parts: str) -> str:
    return os.path.join(cfg["__repo_root__"], *parts)
