"""Launch the trading cockpit on localhost.

Usage:
    python scripts/06_run_cockpit.py [--host 0.0.0.0] [--port 8765] [--reload]

Assumes the training pipeline (01..05) has produced ``artefacts/`` and
``reports/``. The cockpit opens at http://localhost:<port>/.
"""

from __future__ import annotations

import argparse

from _bootstrap import setup


def main() -> None:
    cfg = setup()
    ui_cfg = cfg.get("ui", {})
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=ui_cfg.get("host", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(ui_cfg.get("port", 8765)))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "src.ui.server:app",
        host=args.host,
        port=args.port,
        reload=bool(args.reload),
        log_level="info",
    )


if __name__ == "__main__":
    main()
