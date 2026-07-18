"""Cảnh báo SLA lead — đồng bộ crm_reminders và thông báo."""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from crm_lead_store import (
    LEAD_STATUS_LABELS,
    TERMINAL_STATUSES,
    _UNSET,
    _lead_list_filters,
    assign_lead_owner,
    fetch_lead_by_id,
    fetch_leads,
    is_sla_overdue,
    lead_row_to_dict,
    log_assignment,
    log_lead_activity,
    update_lead,
)
from crm_lead_kpi_metrics import is_lead_qualified, is_lead_won


def _lead_sla_delete_pending(conn: sqlite3.Connection, lead_id: int) -> None:
    conn.execute(
        """
        DELETE FROM crm_reminders
        WHERE scope = 'lead' AND ref_id = ? AND reminder_kind = 'sla_overdue'
          AND status = 'pending'
        """,
        (int(lead_id),),
    )


def sync_lead_sla_reminders(conn: sqlite3.Connection, *, ts: str) -> int:
    """Đồng bộ nhắc việc SLA cho lead quá hạn. Trả số lead đang quá SLA."""
    rows = fetch_leads(conn, limit=5000)
    overdue_count = 0
    for row in rows:
        ld = dict(row)
        lid = int(ld["id"])
        st = str(ld.get("status") or "new")
        if st in TERMINAL_STATUSES:
            _lead_sla_delete_pending(conn, lid)
            continue
        entered = str(ld.get("status_entered_at") or "")
        if not is_sla_overdue(st, entered):
            _lead_sla_delete_pending(conn, lid)
            continue
        overdue_count += 1
        existing = conn.execute(
            """
            SELECT id FROM crm_reminders
            WHERE scope = 'lead' AND ref_id = ? AND reminder_kind = 'sla_overdue'
              AND status = 'pending'
            LIMIT 1
            """,
            (lid,),
        ).fetchone()
        if existing is not None:
            conn.execute(
                "UPDATE crm_reminders SET updated_at = ?, remind_at = ? WHERE id = ?",
                (ts, ts, int(existing["id"])),
            )
            continue
        owner_id = int(ld["owner_id"]) if ld.get("owner_id") else None
        title = f"[SLA] Lead #{lid} — {str(ld.get('full_name') or '')[:120]}"
        body = (
            f"Lead quá hạn SLA ở trạng thái «{LEAD_STATUS_LABELS.get(st, st)}». "
            f"Cần liên hệ/xử lý ngay."
        )
        meta = json.dumps({"lead_id": lid, "status": st}, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO crm_reminders (
                scope, ref_id, reminder_kind, title, body, remind_at,
                status, staff_id, meta_json, created_at, updated_at
            ) VALUES ('lead', ?, 'sla_overdue', ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (lid, title, body, ts, owner_id, meta, ts, ts),
        )
        log_lead_activity(
            conn,
            lead_id=lid,
            activity_type="system",
            content=f"Cảnh báo SLA — trạng thái {LEAD_STATUS_LABELS.get(st, st)} quá hạn.",
            user_id=owner_id,
            created_by="system:sla",
            ts=ts,
        )
        _maybe_email_sla_alert(conn, lead_id=lid, owner_id=owner_id, title=title, body=body)
    return overdue_count


def _maybe_email_sla_alert(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    owner_id: int | None,
    title: str,
    body: str,
) -> None:
    if str(os.getenv("CRM_LEAD_SLA_EMAIL", "1")).strip().lower() in ("0", "false", "no"):
        return
    if not owner_id:
        return
    try:
        from crm_sales_pipeline import send_pipeline_notify_email
    except ImportError:
        return
    row = conn.execute(
        "SELECT email, name FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
        (int(owner_id),),
    ).fetchone()
    if not row or not str(row["email"] or "").strip():
        return
    send_pipeline_notify_email(
        to_email=str(row["email"]).strip(),
        subject=f"[CRM Lead SLA] {title[:160]}",
        body=f"Xin chào {row['name']},\n\n{body}\n\nXem: /crm/leads\n",
    )


def fetch_lead_sla_alerts(
    conn: sqlite3.Connection,
    *,
    owner_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Danh sách lead quá SLA trạng thái hoặc không có activity."""
    from crm_lead_rules import fetch_lead_config, is_no_activity_sla_overdue

    cfg = fetch_lead_config(conn)
    activity_sla = bool(cfg.get("activity_sla_enabled"))
    rows = fetch_leads(conn, owner_id=owner_id, limit=5000)
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        st = str(d["status"] or "new")
        status_overdue = is_sla_overdue(st, str(d.get("status_entered_at") or ""))
        no_act = False
        if activity_sla:
            no_act = is_no_activity_sla_overdue(
                conn,
                lead_id=int(d["id"]),
                status=st,
                status_entered_at=str(d.get("status_entered_at") or ""),
                created_at=str(d.get("created_at") or ""),
            )
        if not status_overdue and not no_act:
            continue
        reasons: list[str] = []
        if status_overdue:
            reasons.append("status_sla")
        if no_act:
            reasons.append("no_activity")
        out.append(
            {
                "lead_id": int(d["id"]),
                "full_name": str(d.get("full_name") or ""),
                "phone": str(d.get("phone") or ""),
                "status": st,
                "status_label": LEAD_STATUS_LABELS.get(st, st),
                "owner_id": int(d["owner_id"]) if d.get("owner_id") else None,
                "owner_name": str(d.get("owner_name") or ""),
                "status_entered_at": str(d.get("status_entered_at") or ""),
                "lead_score": int(d.get("lead_score") or 0),
                "alert_types": reasons,
                "alert_label": "Quá SLA trạng thái" if status_overdue and not no_act
                else ("Không có activity" if no_act and not status_overdue else "Quá SLA + không activity"),
            }
        )
        if len(out) >= limit:
            break
    return out


def fetch_lead_owner_stats(
    conn: sqlite3.Connection,
    *,
    owner_id: int | None = None,
    staff_portal_id: int | None = None,
    re_project_id: int | None | object = _UNSET,
    status: str | None = None,
    level: str | None = None,
    source: str | None = None,
    q: str | None = None,
    product_line: str | None = None,
    zone: str | None = None,
    sla_overdue_only: bool = False,
    hide_review_queue: bool = True,
    review_queue_only: bool = False,
) -> list[dict[str, Any]]:
    """Hiệu suất lead theo owner — cùng bộ lọc với danh sách lead bên dưới.

    Portal NV: scope theo dự án tham gia (lead không gán dự án không được đếm).
    """
    from crm_lead_care_pipeline import CARE_PIPELINE_STAGES, CARE_STAGE_KEYS, care_stage_for_status

    all_leads = fetch_leads(
        conn,
        owner_id=owner_id,
        staff_portal_id=staff_portal_id,
        re_project_id=re_project_id,
        status=status,
        level=level,
        source=source,
        q=q,
        product_line=product_line,
        zone=zone,
        sla_overdue_only=sla_overdue_only,
        hide_review_queue=hide_review_queue,
        review_queue_only=review_queue_only,
        limit=5000,
    )
    buckets: dict[int | None, dict[str, Any]] = {}
    for row in all_leads:
        lead = lead_row_to_dict(row, conn)
        # Chỉ tính lead đã gán dự án BĐS — khớp danh sách NV / vận hành thực tế
        if not lead.get("re_project_id"):
            continue
        oid = lead.get("owner_id")
        if oid not in buckets:
            buckets[oid] = {
                "owner_id": oid,
                "owner_name": str(lead.get("owner_name") or "Chưa gán"),
                "owner_code": str(lead.get("owner_code") or ""),
                "total": 0,
                "won": 0,
                "lost": 0,
                "open": 0,
                "qualified": 0,
                "hot": 0,
                "sla_overdue": 0,
                "score_sum": 0,
                "by_care_stage": {k: 0 for k in CARE_STAGE_KEYS},
                "by_project": {},
            }
        b = buckets[oid]
        b["total"] += 1
        b["score_sum"] += int(lead.get("lead_score") or 0)

        pid_raw = lead.get("re_project_id")
        pid_key = int(pid_raw)
        pcode = str(lead.get("re_project_code") or "").strip()
        pname = str(lead.get("re_project_name") or "").strip()
        from crm_project_leads import format_project_display_label, format_project_full_label

        plabel = format_project_display_label(code=pcode, name=pname, project_id=pid_key)
        pfull = format_project_full_label(code=pcode, name=pname, project_id=pid_key)
        if pid_key not in b["by_project"]:
            b["by_project"][pid_key] = {
                "project_id": pid_key,
                "project_code": pcode,
                "project_name": pname,
                "project_label": plabel,
                "project_full_label": pfull,
                "count": 0,
            }
        b["by_project"][pid_key]["count"] += 1

        st = str(lead.get("status") or "")
        pipe = lead.get("care_pipeline") or {}
        stage = str(pipe.get("current_stage_key") or lead.get("care_stage_key") or "").strip()
        if stage not in CARE_STAGE_KEYS:
            stage = care_stage_for_status(st)
        if stage in b["by_care_stage"]:
            b["by_care_stage"][stage] += 1

        if st == "lost":
            b["lost"] += 1
        elif is_lead_won(conn, int(lead.get("id") or 0)):
            b["won"] += 1
        else:
            b["open"] += 1
        if is_lead_qualified(conn, int(lead.get("id") or 0)):
            b["qualified"] += 1

        if str(lead.get("lead_level") or "") == "hot":
            b["hot"] += 1
        if lead.get("sla_overdue"):
            b["sla_overdue"] += 1

    out: list[dict[str, Any]] = []
    for b in buckets.values():
        total = int(b["total"] or 0)
        won = int(b["won"] or 0)
        qualified = int(b["qualified"] or 0)
        by_stage = dict(b["by_care_stage"])
        projects = sorted(
            [p for p in b["by_project"].values() if p.get("project_id")],
            key=lambda x: (-int(x.get("count") or 0), str(x.get("project_label") or "")),
        )
        out.append(
            {
                "owner_id": b["owner_id"],
                "owner_name": b["owner_name"],
                "owner_code": b["owner_code"],
                "total": total,
                "won": won,
                "qualified_leads": qualified,
                "lost": int(b["lost"] or 0),
                "open": int(b["open"] or 0),
                "hot": int(b["hot"] or 0),
                "sla_overdue": int(b["sla_overdue"] or 0),
                "conversion_rate": round(won * 100.0 / qualified, 1) if qualified else 0.0,
                "close_rate_pct": round(won * 100.0 / qualified, 1) if qualified else 0.0,
                "avg_score": round(float(b["score_sum"]) / total, 1) if total else 0.0,
                "by_care_stage": by_stage,
                "project_count": len([p for p in projects if p.get("project_id")]),
                "projects": projects,
                "projects_summary": " · ".join(
                    f'{p.get("project_label") or p.get("project_code") or "—"}: {p.get("count") or 0}'
                    for p in projects
                ),
                "care_stages": [
                    {
                        "key": st["key"],
                        "label": st["label"],
                        "short": f"B{i + 1}",
                        "count": int(by_stage.get(st["key"]) or 0),
                    }
                    for i, st in enumerate(CARE_PIPELINE_STAGES)
                ],
            }
        )
    out.sort(key=lambda x: (-int(x["total"]), str(x.get("owner_name") or "")))
    return out


def reassign_leads_from_inactive_owners(
    conn: sqlite3.Connection,
    *,
    ts: str,
    actor: str = "system:maintenance",
) -> int:
    """Phân lại lead khi owner ngưng hoặc không tồn tại."""
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    fallback = str(cfg.get("inactive_owner_fallback") or "round_robin")
    rows = conn.execute(
        """
        SELECT l.id, l.owner_id, l.region, l.product_interest, l.lead_level
        FROM crm_leads l
        LEFT JOIN crm_staff s ON s.id = l.owner_id
        WHERE l.owner_id IS NOT NULL
          AND l.status NOT IN ('won', 'lost')
          AND COALESCE(l.is_duplicate, 0) = 0
          AND (s.id IS NULL OR COALESCE(s.active, 1) = 0)
        """
    ).fetchall()
    reassigned = 0
    for row in rows:
        ld = dict(row)
        lid = int(ld["id"])
        old_owner = int(ld["owner_id"])
        new_id, _, _strategy = assign_lead_owner(
            conn,
            region=str(ld.get("region") or ""),
            product_interest=str(ld.get("product_interest") or ""),
            industry_slug=str(ld.get("industry_slug") or ""),
            lead_level=str(ld.get("lead_level") or "warm"),
            prefer_min_workload=(fallback == "min_workload"),
        )
        if not new_id or int(new_id) == old_owner:
            continue
        conn.execute(
            "UPDATE crm_leads SET owner_id = ?, updated_at = ?, updated_by = ? WHERE id = ?",
            (int(new_id), ts, actor[:120], lid),
        )
        log_assignment(
            conn,
            lead_id=lid,
            from_user_id=old_owner,
            to_user_id=int(new_id),
            reason="Owner không còn active — tự động phân lại",
            created_by=actor,
            ts=ts,
        )
        log_lead_activity(
            conn,
            lead_id=lid,
            activity_type="system",
            content=f"Tự động phân lại — owner cũ (#{old_owner}) không còn hoạt động.",
            user_id=int(new_id),
            created_by=actor,
            ts=ts,
        )
        reassigned += 1
    return reassigned
