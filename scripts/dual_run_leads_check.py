#!/usr/bin/env python3
"""Batch dual-run check — Flask SQLite read vs NestJS /api/v1/leads (Phase 1b Bước 4)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Flask vs Nest leads API v1")
    parser.add_argument("--sample", type=int, default=50, help="Number of recent leads to sample")
    parser.add_argument("--sqlite", default="", help="Override PTT_SQLITE_PATH")
    parser.add_argument("--nest-url", default="", help="Override PTT_NEST_LEADS_URL")
    parser.add_argument("--no-list", action="store_true", help="Skip list endpoint compare")
    parser.add_argument("--quiet", action="store_true", help="Only print summary line")
    args = parser.parse_args()

    if args.nest_url:
        import os

        os.environ["PTT_NEST_LEADS_URL"] = args.nest_url.rstrip("/")

    from ptt_crm.dual_run import run_batch_dual_run_check

    report = run_batch_dual_run_check(
        sample_size=max(1, args.sample),
        sqlite_path=args.sqlite or None,
        include_list=not args.no_list,
    )

    if args.quiet:
        status = "OK" if report["ok"] else "FAIL"
        print(
            f"{status} dual-run sample={report['sample_size']} "
            f"mismatches={report['mismatch_count']} nest={report['nest_url']}"
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
