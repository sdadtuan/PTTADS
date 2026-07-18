#!/usr/bin/env python3
"""CLI — LeadAssigned outbox → RMQ E2E gate (Phase 2 P1 #7–#8)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="LeadAssigned RMQ E2E verification")
    parser.add_argument("--lead-id", type=int, default=None, help="Existing staging lead id")
    parser.add_argument("--owner-id", type=int, default=99)
    parser.add_argument("--max-lag-sec", type=float, default=30.0)
    parser.add_argument("--skip-idempotency", action="store_true")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "lead-assigned-rmq-e2e.json"),
    )
    args = parser.parse_args()

    from ptt_crm.lead_assigned_e2e import run_lead_assigned_rmq_e2e

    result = run_lead_assigned_rmq_e2e(
        lead_id=args.lead_id,
        owner_id=args.owner_id,
        max_publish_lag_sec=args.max_lag_sec,
        skip_idempotency=args.skip_idempotency,
    )
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(json.dumps(result, indent=2, default=str)[:6000])
    print("")
    if result.get("ok"):
        print(f"OK  LeadAssigned RMQ E2E passed — {report_path}")
        return 0
    print(f"FAIL LeadAssigned RMQ E2E — {report_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
