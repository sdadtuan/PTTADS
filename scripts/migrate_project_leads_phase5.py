#!/usr/bin/env python3
"""Phase 5 — map Form Facebook → dự án BĐS, gán NV vào crm_re_project_staff, backfill re_project_id.

Chạy trên VPS:
  cd /var/www/ptt
  python3 scripts/migrate_project_leads_phase5.py --dry-run
  python3 scripts/migrate_project_leads_phase5.py --form-id 2814926042203269 --project-code DA-A
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from ptt_crm.crm_sqlite import get_connection  # noqa: E402
from crm_lead_store import ensure_lead_schema  # noqa: E402
from crm_project_leads import add_project_staff, ensure_project_leads_schema  # noqa: E402
from crm_project_webhooks import save_project_lead_config  # noqa: E402
from crm_re_projects import ensure_re_projects_schema, refresh_project_re_leads_new_kpi  # noqa: E402


def _resolve_project_id(conn, *, project_id: int | None, project_code: str) -> int:
    if project_id and project_id > 0:
        row = conn.execute("SELECT id FROM crm_re_projects WHERE id = ?", (int(project_id),)).fetchone()
        if not row:
            raise SystemExit(f"Dự án #{project_id} không tồn tại.")
        return int(row["id"])
    code = str(project_code or "").strip()
    if not code:
        raise SystemExit("Cần --project-id hoặc --project-code.")
    row = conn.execute(
        "SELECT id, code, name FROM crm_re_projects WHERE code = ? COLLATE NOCASE",
        (code,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Không tìm thấy dự án code={code!r}.")
    print(f"Dự án: #{row['id']} {row['name']} ({row['code']})")
    return int(row["id"])


def _load_facebook_page_id(conn) -> str:
    try:
        from crm_facebook_config import fetch_facebook_config

        cfg = fetch_facebook_config(conn)
        return str(cfg.get("page_id") or "").strip()
    except Exception:
        return ""


def map_form_to_project(
    conn,
    *,
    project_id: int,
    form_id: str,
    page_id: str,
    dry_run: bool,
    ts: str,
) -> None:
    fid = str(form_id or "").strip()
    if not fid:
        raise SystemExit("Thiếu --form-id.")
    existing = conn.execute(
        "SELECT project_id FROM crm_re_project_facebook_forms WHERE form_id = ?",
        (fid,),
    ).fetchone()
    if existing and int(existing["project_id"]) != int(project_id):
        raise SystemExit(
            f"Form {fid} đã map dự án #{existing['project_id']} — bỏ map trước hoặc dùng dự án đó."
        )
    print(f"Map Form ID {fid} → dự án #{project_id}")
    if dry_run:
        return
    save_project_lead_config(
        conn,
        project_id,
        {
            "enabled": True,
            "webhook_enabled": True,
            "facebook_page_id": page_id,
            "forms": [{"form_id": fid, "form_name": f"Form {fid}", "page_id": page_id, "active": True}],
        },
        updated_by="migrate:phase5",
        ts=ts,
    )


def backfill_leads_by_form(conn, *, project_id: int, form_id: str, dry_run: bool) -> int:
    fid = str(form_id or "").strip()
    rows = conn.execute(
        """
        SELECT id FROM crm_leads
        WHERE re_project_id IS NULL
          AND (
            json_extract(meta_json, '$.facebook_form_id') = ?
            OR meta_json LIKE ?
          )
        """,
        (fid, f'%"facebook_form_id": "{fid}"%'),
    ).fetchall()
    ids = [int(r["id"]) for r in rows]
    print(f"Backfill re_project_id: {len(ids)} lead có form {fid}")
    if dry_run or not ids:
        return len(ids)
    conn.executemany(
        "UPDATE crm_leads SET re_project_id = ?, updated_at = ? WHERE id = ?",
        [(int(project_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), lid) for lid in ids],
    )
    return len(ids)


def assign_staff_from_lead_owners(conn, *, project_id: int, dry_run: bool, ts: str) -> int:
    rows = conn.execute(
        """
        SELECT DISTINCT owner_id FROM crm_leads
        WHERE re_project_id = ? AND owner_id IS NOT NULL
        ORDER BY owner_id
        """,
        (int(project_id),),
    ).fetchall()
    added = 0
    for r in rows:
        sid = int(r["owner_id"])
        exists = conn.execute(
            """
            SELECT 1 FROM crm_re_project_staff
            WHERE project_id = ? AND staff_id = ? AND left_at IS NULL
            """,
            (int(project_id), sid),
        ).fetchone()
        if exists:
            continue
        staff = conn.execute(
            "SELECT id, name FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
            (sid,),
        ).fetchone()
        if not staff:
            print(f"  Bỏ qua owner #{sid} — không phải NV active")
            continue
        print(f"  + NV #{sid} {staff['name']} → dự án #{project_id}")
        if not dry_run:
            add_project_staff(
                conn,
                project_id,
                staff_id=sid,
                role="sales",
                assign_enabled=True,
                ts=ts,
            )
        added += 1
    print(f"Gán NV từ owner lead: +{added}")
    return added


def assign_staff_ids(conn, *, project_id: int, staff_ids: list[int], dry_run: bool, ts: str) -> int:
    added = 0
    for sid in staff_ids:
        exists = conn.execute(
            """
            SELECT 1 FROM crm_re_project_staff
            WHERE project_id = ? AND staff_id = ? AND left_at IS NULL
            """,
            (int(project_id), int(sid)),
        ).fetchone()
        if exists:
            continue
        if not dry_run:
            add_project_staff(
                conn,
                project_id,
                staff_id=int(sid),
                role="sales",
                assign_enabled=True,
                ts=ts,
            )
        print(f"  + NV #{sid}")
        added += 1
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 migration — form map + project staff")
    parser.add_argument("--form-id", default="2814926042203269", help="Facebook Form ID")
    parser.add_argument("--project-id", type=int, default=0, help="crm_re_projects.id")
    parser.add_argument("--project-code", default="", help="Mã dự án (vd. DA-A)")
    parser.add_argument("--page-id", default="", help="Facebook Page ID (mặc định lấy từ cấu hình CRM)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in, không ghi DB")
    parser.add_argument(
        "--assign-from-owners",
        action="store_true",
        help="Thêm owner lead hiện có vào crm_re_project_staff",
    )
    parser.add_argument(
        "--staff-ids",
        default="",
        help="Danh sách staff_id cách nhau bởi dấu phẩy (vd. 1,2,3)",
    )
    parser.add_argument(
        "--backfill-leads",
        action="store_true",
        help="Gán re_project_id cho lead có form_id khớp",
    )
    parser.add_argument(
        "--refresh-kpi",
        action="store_true",
        help="Cập nhật KPI RE_LEADS_NEW sau migration",
    )
    args = parser.parse_args()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        ensure_re_projects_schema(conn)
        ensure_lead_schema(conn)
        ensure_project_leads_schema(conn)
        project_id = _resolve_project_id(
            conn,
            project_id=int(args.project_id or 0) or None,
            project_code=str(args.project_code or ""),
        )
        page_id = str(args.page_id or "").strip() or _load_facebook_page_id(conn)

        map_form_to_project(
            conn,
            project_id=project_id,
            form_id=str(args.form_id),
            page_id=page_id,
            dry_run=bool(args.dry_run),
            ts=ts,
        )

        if args.backfill_leads:
            backfill_leads_by_form(
                conn,
                project_id=project_id,
                form_id=str(args.form_id),
                dry_run=bool(args.dry_run),
            )

        if args.assign_from_owners:
            assign_staff_from_lead_owners(
                conn,
                project_id=project_id,
                dry_run=bool(args.dry_run),
                ts=ts,
            )

        staff_raw = str(args.staff_ids or "").strip()
        if staff_raw:
            ids = [int(x.strip()) for x in staff_raw.split(",") if x.strip()]
            assign_staff_ids(conn, project_id=project_id, staff_ids=ids, dry_run=bool(args.dry_run), ts=ts)

        if args.refresh_kpi and not args.dry_run:
            kpi = refresh_project_re_leads_new_kpi(conn, project_id, ts=ts)
            print(f"KPI RE_LEADS_NEW: actual={kpi.get('actual')} tháng {kpi.get('period_month')}")

        if args.dry_run:
            print("DRY RUN — không commit.")
            conn.rollback()
        else:
            conn.commit()
            print("Đã commit migration Phase 5.")


if __name__ == "__main__":
    main()
