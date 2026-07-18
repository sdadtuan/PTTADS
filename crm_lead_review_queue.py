"""Lead Phải tra soát — quá hạn B2 chưa 「Liên hệ OK」 (GDKD xử lý)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from crm_lead_care_pipeline import (
    CONTACT_OK_CARE_STATUS,
    presales_care_gate_state,
    stage_has_contact_ok_report,
)
from crm_lead_store import (
    TERMINAL_STATUSES,
    _lead_assigned_at,
    _parse_ts,
    assign_lead_owner,
    fetch_lead_by_id,
    log_assignment,
    log_lead_activity,
    normalize_status,
)

REVIEW_QUEUE_REASON = "b2_no_contact_ok"
DEFAULT_B2_CONTACT_DEADLINE_HOURS = 24
MIN_B2_CONTACT_DEADLINE_HOURS = 1
MAX_B2_CONTACT_DEADLINE_HOURS = 168


def normalize_b2_contact_deadline_hours(raw: Any) -> int:
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        hours = DEFAULT_B2_CONTACT_DEADLINE_HOURS
    return max(MIN_B2_CONTACT_DEADLINE_HOURS, min(hours, MAX_B2_CONTACT_DEADLINE_HOURS))


def parse_lead_meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def review_queue_from_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    rq = meta.get("review_queue")
    return dict(rq) if isinstance(rq, dict) else {}


def is_lead_in_review_queue(meta: dict[str, Any] | None) -> bool:
    rq = review_queue_from_meta(meta)
    return bool(rq.get("active"))


def review_queue_public_state(
    meta: dict[str, Any] | None,
    *,
    assigned_at: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    rq = review_queue_from_meta(meta)
    if not rq.get("active"):
        return {"active": False}
    ref = now or datetime.now()
    queued_at = str(rq.get("queued_at") or "")
    assigned_snap = str(rq.get("assigned_at") or assigned_at or "")
    deadline_hours = normalize_b2_contact_deadline_hours(rq.get("deadline_hours"))
    hours_waiting = None
    assigned_dt = _parse_ts(assigned_snap)
    if assigned_dt is not None:
        hours_waiting = round((ref - assigned_dt).total_seconds() / 3600.0, 1)
    return {
        "active": True,
        "reason": str(rq.get("reason") or REVIEW_QUEUE_REASON),
        "queued_at": queued_at,
        "assigned_at": assigned_snap,
        "deadline_hours": deadline_hours,
        "previous_owner_id": int(rq["previous_owner_id"])
        if rq.get("previous_owner_id") not in (None, "", 0)
        else None,
        "hours_waiting": hours_waiting,
        "message": (
            f"Quá {deadline_hours}h kể từ phân công — chưa có báo cáo "
            f"「Liên hệ OK» ({CONTACT_OK_CARE_STATUS})."
        ),
    }


def count_review_queue_leads(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_leads l
        WHERE COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') = 'true'
          AND COALESCE(l.is_duplicate, 0) = 0
        """
    ).fetchone()
    return int(row["c"] if row else 0)


def _lead_is_b2_review_candidate(row: sqlite3.Row | dict[str, Any], *, now: datetime) -> tuple[bool, str]:
    d = dict(row)
    st = normalize_status(str(d.get("status") or ""))
    if st in TERMINAL_STATUSES or st == "lost":
        return False, "terminal"
    if bool(d.get("is_duplicate")):
        return False, "duplicate"
    owner_id = d.get("owner_id")
    if not owner_id:
        return False, "no_owner"
    meta = parse_lead_meta(str(d.get("meta_json") or ""))
    if is_lead_in_review_queue(meta):
        return False, "already_queued"
    gate = presales_care_gate_state(
        care_stage_current=str(d.get("care_stage_current") or ""),
        care_stages_done_json=str(d.get("care_stages_done_json") or ""),
    )
    if gate.get("complete"):
        return False, "b2_done"
    return True, ""


def _lead_assigned_at_row(row: sqlite3.Row | dict[str, Any]) -> str:
    d = dict(row)
    meta = parse_lead_meta(str(d.get("meta_json") or ""))
    owner_id = int(d["owner_id"]) if d.get("owner_id") else None
    return _lead_assigned_at(
        meta,
        owner_id=owner_id,
        first_assigned_at=str(d.get("first_assigned_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )


def lead_b2_overdue_for_review(
    row: sqlite3.Row | dict[str, Any],
    *,
    deadline_hours: int,
    now: datetime | None = None,
) -> bool:
    ok, _ = _lead_is_b2_review_candidate(row, now=now or datetime.now())
    if not ok:
        return False
    assigned_at = _lead_assigned_at_row(row)
    assigned_dt = _parse_ts(assigned_at)
    if assigned_dt is None:
        return False
    ref = now or datetime.now()
    elapsed_h = (ref - assigned_dt).total_seconds() / 3600.0
    return elapsed_h >= float(deadline_hours)


def queue_lead_for_review(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    ts: str,
    actor: str,
    previous_owner_id: int | None,
    assigned_at: str,
    deadline_hours: int,
    reason: str = REVIEW_QUEUE_REASON,
) -> sqlite3.Row:
    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    meta = parse_lead_meta(str(lead["meta_json"] or ""))
    if is_lead_in_review_queue(meta):
        raise ValueError("Lead đã ở danh mục Phải tra soát.")
    prev_owner = int(previous_owner_id) if previous_owner_id else None
    if prev_owner is None and lead["owner_id"]:
        prev_owner = int(lead["owner_id"])
    meta["review_queue"] = {
        "active": True,
        "reason": reason,
        "queued_at": ts,
        "previous_owner_id": prev_owner,
        "assigned_at": assigned_at,
        "deadline_hours": normalize_b2_contact_deadline_hours(deadline_hours),
    }
    conn.execute(
        """
        UPDATE crm_leads
        SET owner_id = NULL,
            meta_json = ?,
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (json.dumps(meta, ensure_ascii=False), ts, actor[:120], int(lead_id)),
    )
    if prev_owner:
        log_assignment(
            conn,
            lead_id=int(lead_id),
            from_user_id=prev_owner,
            to_user_id=None,
            reason="Quá hạn B2 — chuyển Lead Phải tra soát (GDKD)",
            created_by=actor,
            ts=ts,
        )
    log_lead_activity(
        conn,
        lead_id=int(lead_id),
        activity_type="system",
        content=(
            f"Lead Phải tra soát — quá {meta['review_queue']['deadline_hours']}h "
            f"kể từ phân công, chưa có báo cáo 「Liên hệ OK»."
        ),
        created_by=actor,
        ts=ts,
    )
    row = fetch_lead_by_id(conn, lead_id)
    assert row is not None
    return row


def release_lead_from_review_queue(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    mode: str,
    new_owner_id: int | None = None,
    actor: str,
    ts: str,
    note: str = "",
) -> sqlite3.Row:
    from crm_lead_rules import fetch_lead_config

    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    meta = parse_lead_meta(str(lead["meta_json"] or ""))
    rq = review_queue_from_meta(meta)
    if not rq.get("active"):
        raise ValueError("Lead không ở danh mục Phải tra soát.")
    prev_owner = int(rq["previous_owner_id"]) if rq.get("previous_owner_id") else None
    mode_norm = str(mode or "").strip().lower()
    if mode_norm not in ("auto", "manual"):
        raise ValueError("mode phải là auto hoặc manual.")
    ld = dict(lead)
    if mode_norm == "manual":
        if not new_owner_id:
            raise ValueError("Chọn AM để gán lại.")
        target_owner = int(new_owner_id)
        strategy = "manual_gdkd"
        owner_name = conn.execute(
            "SELECT name FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
            (target_owner,),
        ).fetchone()
        if owner_name is None:
            raise ValueError("AM không hợp lệ hoặc đã ngưng.")
        owner_label = str(owner_name["name"])
    else:
        cfg = fetch_lead_config(conn)
        fallback = str(cfg.get("inactive_owner_fallback") or "round_robin")
        from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner

        ctx = LeadAssignContext(
            lead_level=str(ld.get("lead_level") or "warm"),
            lead_score=int(ld.get("lead_score") or 0),
            region=str(ld.get("region") or ""),
            product_interest=str(ld.get("product_interest") or ""),
            industry_slug=str(ld.get("industry_slug") or ""),
            source=str(ld.get("source") or ""),
            need=str(ld.get("need") or ""),
            prefer_min_workload=(fallback == "min_workload"),
            re_project_id=int(ld["re_project_id"]) if ld.get("re_project_id") else None,
            product_line=str(ld.get("product_line") or ""),
            zone=str(ld.get("zone") or ""),
            exclude_staff_ids=frozenset({prev_owner}) if prev_owner else frozenset(),
        )
        assign_cfg = cfg.get("assign_config") or {}
        target_owner, owner_label, strategy = auto_assign_lead_owner(
            conn, ctx, config=assign_cfg
        )
        if not target_owner:
            target_owner, owner_label, strategy = assign_lead_owner(
                conn,
                region=str(ld.get("region") or ""),
                product_interest=str(ld.get("product_interest") or ""),
                industry_slug=str(ld.get("industry_slug") or ""),
                lead_level=str(ld.get("lead_level") or "warm"),
                lead_score=int(ld.get("lead_score") or 0),
                source=str(ld.get("source") or ""),
                need=str(ld.get("need") or ""),
                prefer_min_workload=(fallback == "min_workload"),
                re_project_id=int(ld["re_project_id"]) if ld.get("re_project_id") else None,
                product_line=str(ld.get("product_line") or ""),
                zone=str(ld.get("zone") or ""),
            )
        if not target_owner:
            raise ValueError("Không tìm được AM để phân lại — kiểm tra cấu hình phân lead.")
        if prev_owner and int(target_owner) == int(prev_owner):
            raise ValueError("Không có AM khác để phân lại (chỉ còn owner cũ).")
    if ld.get("re_project_id"):
        from crm_project_leads import assert_staff_in_project

        assert_staff_in_project(conn, int(ld["re_project_id"]), int(target_owner))
    meta.pop("review_queue", None)
    meta["auto_assigned_at"] = ts
    note_clean = str(note or "").strip()
    release_note = note_clean or (
        "GDKD phân lại tự động" if mode_norm == "auto" else "GDKD gán AM mới"
    )
    log_assignment(
        conn,
        lead_id=int(lead_id),
        from_user_id=None,
        to_user_id=int(target_owner),
        reason=f"{release_note} ({strategy})",
        created_by=actor,
        ts=ts,
    )
    log_lead_activity(
        conn,
        lead_id=int(lead_id),
        activity_type="system",
        content=f"GDKD đưa lead ra khỏi Phải tra soát — gán {owner_label}. {release_note}",
        user_id=int(target_owner),
        created_by=actor,
        ts=ts,
    )
    conn.execute(
        """
        UPDATE crm_leads
        SET owner_id = ?,
            meta_json = ?,
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (
            int(target_owner),
            json.dumps(meta, ensure_ascii=False),
            ts,
            actor[:120],
            int(lead_id),
        ),
    )
    row = fetch_lead_by_id(conn, lead_id)
    assert row is not None
    return row


def sync_b2_review_queue(
    conn: sqlite3.Connection,
    *,
    ts: str,
    actor: str = "system:b2_review",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Cron/maintenance: thu hồi lead quá hạn B2 chưa Liên hệ OK → Phải tra soát."""
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    if not cfg.get("b2_review_queue_enabled", True):
        return {
            "enabled": False,
            "queued": 0,
            "scanned": 0,
            "deadline_hours": normalize_b2_contact_deadline_hours(
                cfg.get("b2_contact_deadline_hours")
            ),
        }
    deadline_hours = normalize_b2_contact_deadline_hours(cfg.get("b2_contact_deadline_hours"))
    now = _parse_ts(ts) or datetime.now()
    rows = conn.execute(
        f"""
        SELECT l.*,
               (
                   SELECT al.created_at
                   FROM crm_lead_assignment_logs al
                   WHERE al.lead_id = l.id AND al.to_user_id IS NOT NULL
                   ORDER BY al.created_at ASC
                   LIMIT 1
               ) AS first_assigned_at
        FROM crm_leads l
        WHERE l.owner_id IS NOT NULL
          AND COALESCE(l.is_duplicate, 0) = 0
          AND l.status NOT IN ('lost')
          AND COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') != 'true'
          AND COALESCE(json_extract(l.care_stages_done_json, '$.first_contact'), '') = ''
        """
    ).fetchall()
    queued = 0
    scanned = 0
    lead_ids: list[int] = []
    for row in rows:
        scanned += 1
        if not _lead_is_b2_review_candidate(row, now=now)[0]:
            continue
        lid = int(row["id"])
        if stage_has_contact_ok_report(
            conn, lead_id=lid, stage_key="first_contact"
        ):
            continue
        if not lead_b2_overdue_for_review(row, deadline_hours=deadline_hours, now=now):
            continue
        lead_ids.append(lid)
        if dry_run:
            queued += 1
            continue
        assigned_at = _lead_assigned_at_row(row)
        queue_lead_for_review(
            conn,
            lid,
            ts=ts,
            actor=actor,
            previous_owner_id=int(row["owner_id"]) if row["owner_id"] else None,
            assigned_at=assigned_at,
            deadline_hours=deadline_hours,
        )
        queued += 1
    return {
        "enabled": True,
        "dry_run": dry_run,
        "queued": queued,
        "scanned": scanned,
        "deadline_hours": deadline_hours,
        "lead_ids": lead_ids,
    }
