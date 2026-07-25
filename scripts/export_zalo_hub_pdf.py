#!/usr/bin/env python3
"""CLI: read Zalo hub JSON from stdin, write PDF bytes to stdout."""
from __future__ import annotations

import json
import sys

from ptt_zalo.report_export import build_zalo_hub_pdf


def main() -> int:
    hub = json.load(sys.stdin)
    buf, _name = build_zalo_hub_pdf(hub)
    sys.stdout.buffer.write(buf.read())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
