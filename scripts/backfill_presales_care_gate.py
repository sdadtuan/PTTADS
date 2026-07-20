#!/usr/bin/env python3
"""Backfill gate chăm sóc B1–B3 cho lead legacy đã có pre-sales.

Chạy sau khi bật gate pre-sales (PTT_PRESALES_ON_LEAD=1):

  cd PTTADS
  python3 scripts/backfill_presales_care_gate.py --list-only
  python3 scripts/backfill_presales_care_gate.py --dry-run --limit 20
  python3 scripts/backfill_presales_care_gate.py --lead-id 123
  python3 scripts/backfill_presales_care_gate.py --limit 50 --note "Pilot Q2 — Director approved"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from ptt_crm.crm_sqlite import get_connection  # noqa: E402
from crm_lead_store import ensure_lead_schema  # noqa: E402
from crm_lead_care_pipeline import (  # noqa: E402
    admin_backfill_presales_care_gate,
    list_leads_needing_presales_care_backfill,
)
from crm_lead_presales import ensure_schema as ensure_presales_schema  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill gate B1–B3 cho lead đã có pre-sales (legacy)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Không ghi DB")
    parser.add_argument("--list-only", action="store_true", help="Chỉ liệt kê lead thiếu gate")
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số lead")
    parser.add_argument("--lead-id", type=int, default=0, help="Chỉ một lead")
    parser.add_argument(
        "--note",
        default="Backfill gate B1–B3 — lead đã vận hành pre-sales trước khi có gate",
        help="Ghi chú audit (≥3 ký tự)",
    )
    parser.add_argument(
        "--all-leads",
        action="store_true",
        help="Gồm lead chưa có pre-sales (mặc định: chỉ lead có pre-sales active)",
    )
    args = parser.parse_args()

    limit = args.limit if args.limit > 0 else None
    lead_id = args.lead_id if args.lead_id > 0 else None

    with get_connection() as conn:
        ensure_lead_schema(conn)
        ensure_presales_schema(conn)
        pending = list_leads_needing_presales_care_backfill(
            conn,
            lead_id=lead_id,
            limit=limit,
            require_presales=not args.all_leads,
        )

        if args.list_only:
            print(f"Lead thiếu gate B1–B3: {len(pending)}")
            for row in pending:
                missing = ", ".join(row["gate"].get("missing_labels") or [])
                ps = row.get("presales_id")
                ps_info = f" presales=#{ps} ({row.get('presales_stage')})" if ps else ""
                print(f"  lead #{row['id']} {row.get('full_name') or ''}{ps_info} — thiếu: {missing}")
            return 0

        if not pending:
            print("Không có lead cần backfill.")
            return 0

        results = []
        for row in pending:
            lid = int(row["id"])
            summary = admin_backfill_presales_care_gate(
                conn,
                lid,
                note=args.note,
                dry_run=args.dry_run,
            )
            results.append(summary)
            tag = "DRY" if args.dry_run else "OK"
            print(f"[{tag}] lead #{lid}: {json.dumps(summary, ensure_ascii=False)}")

    print(f"Done — {len(results)} lead(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
