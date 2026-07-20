#!/usr/bin/env python3
"""Standalone Facebook autosync daemon (Sprint 0 — outside Gunicorn)."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main() -> int:
    os.environ.setdefault("CRM_FACEBOOK_BACKGROUND", "1")
    os.environ.setdefault("CRM_FACEBOOK_BACKGROUND_IN_GUNICORN", "0")
    from crm_facebook_autosync import run_facebook_background_daemon

    run_facebook_background_daemon()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
