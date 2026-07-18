#!/usr/bin/env python3
"""CLI — record write rollback drill evidence (Phase 2 P1 #9)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Write rollback drill evidence")
    parser.add_argument("--flags-only", action="store_true", help="Skip shell drill script")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "rollback-drill-evidence.json"),
    )
    args = parser.parse_args()

    from ptt_crm.rollback_drill_evidence import run_rollback_drill_evidence, write_drill_report

    report = run_rollback_drill_evidence(include_shell=not args.flags_only)
    path = write_drill_report(report, path=Path(args.report))
    report["report_path"] = str(path)

    print(json.dumps(report, indent=2, default=str)[:4000])
    print("")
    if report.get("ok"):
        print(f"OK  rollback drill evidence — {path}")
        return 0
    print(f"FAIL rollback drill evidence — {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
