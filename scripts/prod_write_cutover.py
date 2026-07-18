#!/usr/bin/env python3
"""Production write cutover assistant — runbook §4–§8."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod write cutover pack")
    parser.add_argument("--apply", action="store_true", help="Apply sync_mode (not full systemd cutover)")
    parser.add_argument("--skip-rollback", action="store_true")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "prod-write-cutover-report.json"),
    )
    args = parser.parse_args()

    from ptt_crm.prod_write_cutover import run_prod_cutover_pack, write_prod_report

    report = run_prod_cutover_pack(
        dry_run=not args.apply,
        include_rollback=not args.skip_rollback,
    )
    path = write_prod_report(report, path=Path(args.report))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:8000])
    print("")
    if report.get("ok"):
        mode = "APPLY" if args.apply else "DRY_RUN"
        print(f"OK  prod write cutover ({mode}) — {path}")
        if not args.apply:
            print("    Re-run with --apply after change window preflight on VPS")
        return 0
    print(f"FAIL prod cutover — {report.get('failed_steps')} — {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
