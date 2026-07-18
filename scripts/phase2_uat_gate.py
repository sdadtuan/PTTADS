#!/usr/bin/env python3
"""Phase 2 UAT automated checks + sign-off template export."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 UAT gate")
    parser.add_argument("--am-name", default="")
    parser.add_argument("--admin-name", default="")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "phase2-uat-signoff.json"),
    )
    args = parser.parse_args()

    from ptt_crm.phase2_ops_gates import build_signoff_template, run_uat_automated_checks

    uat = run_uat_automated_checks()
    signoff = build_signoff_template(
        gate_report={"ok": uat.get("ok"), "failed_steps": uat.get("failed_checks")},
        signatories={"am_name": args.am_name, "admin_name": args.admin_name},
    )
    report = {"uat_automated": uat, "signoff": signoff}
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str)[:6000])
    print("")
    if uat.get("ok"):
        print(f"OK  UAT automated checks — sign-off template: {path}")
        return 0
    print(f"FAIL UAT — {uat.get('failed_checks')} — {path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
