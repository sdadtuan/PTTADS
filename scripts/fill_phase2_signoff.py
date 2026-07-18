#!/usr/bin/env python3
"""Fill Phase 2 UAT sign-off checklist from gate pack report."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill Phase 2 UAT sign-off from gate pack")
    parser.add_argument(
        "--gate-report",
        default=str(ROOT / ".local-dev" / "phase2-ops-gate-report.json"),
    )
    parser.add_argument("--am-name", default=os.environ.get("PTT_AM_NAME", "PTT Account Manager"))
    parser.add_argument("--admin-name", default=os.environ.get("PTT_ADMIN_NAME", "PTT DevOps"))
    parser.add_argument(
        "--signed-at",
        default="",
        help="ISO timestamp for both signatories (default: now UTC)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / ".local-dev" / "phase2-uat-signoff.json"),
    )
    parser.add_argument(
        "--update-gate-report",
        action="store_true",
        help="Merge signoff back into phase2-ops-gate-report.json",
    )
    args = parser.parse_args()

    gate_path = Path(args.gate_report)
    if not gate_path.is_file():
        print(f"FAIL gate report not found: {gate_path}", file=sys.stderr)
        return 1

    gate_report = json.loads(gate_path.read_text(encoding="utf-8"))
    signed_at = args.signed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    from ptt_crm.phase2_ops_gates import build_filled_uat_signoff

    signoff = build_filled_uat_signoff(
        gate_report,
        signatories={
            "am_name": args.am_name,
            "admin_name": args.admin_name,
            "am_signed_at": signed_at,
            "admin_signed_at": signed_at,
        },
        artifacts_dir=gate_path.parent,
    )

    out = {
        "phase": "phase2_uat_signoff",
        "generated_at": signed_at,
        "gate_report_path": str(gate_path),
        "signoff": signoff,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    if args.update_gate_report:
        gate_report["signoff_template"] = signoff
        gate_path.write_text(
            json.dumps(gate_report, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    s = signoff["summary"]
    print(json.dumps(signoff, indent=2, ensure_ascii=False, default=str)[:8000])
    print("")
    print(f"Sign-off saved: {out_path}")
    print(
        f"Summary: {s['passed']}/{s['total']} pass, {s['pending']} pending — "
        f"gate_pack={'OK' if s['automated_gate_pack_ok'] else 'FAIL'}"
    )
    if args.update_gate_report:
        print(f"Updated gate report signoff: {gate_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
