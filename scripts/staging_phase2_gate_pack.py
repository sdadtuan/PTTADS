#!/usr/bin/env python3
"""Staging Phase 2 gate pack — 3-client closed-loop + write pilot + prod gates + UAT."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 staging gate pack")
    parser.add_argument(
        "--client-codes",
        default="",
        help="Comma-separated client codes (default: PTT_CLOSED_LOOP_CLIENT_CODES env)",
    )
    parser.add_argument("--no-sync", action="store_true", help="Skip Meta insights sync per client")
    parser.add_argument("--skip-write-pilot", action="store_true")
    parser.add_argument("--skip-prod-gates", action="store_true")
    parser.add_argument("--skip-uat", action="store_true")
    parser.add_argument("--skip-soak", action="store_true", help="Skip 48h soak in prod gates")
    parser.add_argument("--no-apply-sync", action="store_true")
    parser.add_argument("--no-drill", action="store_true")
    parser.add_argument("--no-lead-assigned-e2e", action="store_true")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "phase2-ops-gate-report.json"),
    )
    args = parser.parse_args()

    from ptt_crm.phase2_ops_gates import parse_client_codes, run_staging_gate_pack, write_gate_report

    codes = parse_client_codes(args.client_codes) if args.client_codes else parse_client_codes()
    if len(codes) < 3:
        print(f"WARN need ≥3 client codes, got {len(codes)}: {codes}", file=sys.stderr)

    report = run_staging_gate_pack(
        client_codes=codes,
        run_sync=not args.no_sync,
        write_pilot=not args.skip_write_pilot,
        prod_gates=not args.skip_prod_gates,
        uat=not args.skip_uat,
        apply_sync_mode=not args.no_apply_sync,
        drill=not args.no_drill,
        lead_assigned_e2e=not args.no_lead_assigned_e2e,
        skip_soak=args.skip_soak,
    )
    path = write_gate_report(report, path=Path(args.report))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:12000])
    print("")
    if report.get("ok"):
        print(f"OK  Phase 2 staging gate pack — {path}")
        print(f"    Sign-off template: {path} → signoff_template")
        return 0
    print(f"FAIL Phase 2 staging gate pack — {report.get('failed_steps')} — {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
