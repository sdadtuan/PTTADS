#!/usr/bin/env python3
"""P4 — backfill draft lifecycle (lead_id) → crm_lead_presales, archive lifecycle cũ.

Chạy trên VPS (sau khi bật PTT_PRESALES_ON_LEAD=1 cho pilot):

  cd /var/www/ptt   # hoặc thư mục PTTADS
  python3 scripts/backfill_draft_lifecycle_to_presales.py --dry-run
  python3 scripts/backfill_draft_lifecycle_to_presales.py --limit 50
  python3 scripts/backfill_draft_lifecycle_to_presales.py --lead-id 123
  python3 scripts/backfill_draft_lifecycle_to_presales.py --lifecycle-id 456 --dry-run
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
from crm_lead_presales import ensure_schema as ensure_presales_schema  # noqa: E402
from crm_lead_presales_legacy import (  # noqa: E402
    list_draft_lifecycles_pending_backfill,
    migrate_draft_lifecycle_to_presales,
    run_backfill_all,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill draft lifecycle → pre-sales trên Lead (P4)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ liệt kê / mô phỏng, không ghi DB",
    )
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số lifecycle")
    parser.add_argument("--lead-id", type=int, default=0, help="Chỉ lead cụ thể")
    parser.add_argument("--lifecycle-id", type=int, default=0, help="Chỉ 1 lifecycle")
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="In danh sách pending, không migrate",
    )
    args = parser.parse_args()

    limit = args.limit if args.limit > 0 else None
    lead_id = args.lead_id if args.lead_id > 0 else None

    with get_connection() as conn:
        ensure_lead_schema(conn)
        ensure_presales_schema(conn)

        if args.list_only:
            pending = list_draft_lifecycles_pending_backfill(
                conn, lead_id=lead_id, limit=limit
            )
            print(f"Pending draft lifecycles: {len(pending)}")
            for row in pending:
                print(
                    f"  lc #{row['id']} lead #{row['lead_id']} "
                    f"slug={row.get('service_slug')} stage={row.get('stage')}"
                )
            return 0

        if args.lifecycle_id > 0:
            summary = migrate_draft_lifecycle_to_presales(
                conn,
                args.lifecycle_id,
                dry_run=args.dry_run,
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0 if summary.get("action") != "error" else 1

        report = run_backfill_all(
            conn,
            dry_run=args.dry_run,
            limit=limit,
            lead_id=lead_id,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        c = report.get("counts") or {}
        if c.get("error"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
