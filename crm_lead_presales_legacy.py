"""Backfill draft lifecycle cũ → pre-sales trên Lead (P4)."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from crm_lead_presales import (
    PRESALES_STAGES,
    ensure_presales,
    get_by_lead,
    list_presales_tasks,
    presales_stage_index,
    seed_presales_tasks,
    update_presales_task,
)
from crm_service_lifecycle import stage_index as lifecycle_stage_index

logger = logging.getLogger(__name__)

BACKFILL_MARKER = "[P4 backfill]"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _presales_stage_from_lifecycle(lifecycle_stage: str) -> str:
    stage = str(lifecycle_stage or "lead").strip()
    if stage in PRESALES_STAGES:
        return stage
    if lifecycle_stage_index(stage) >= lifecycle_stage_index("onboard"):
        return "proposal"
    return "lead"


def list_draft_lifecycles_pending_backfill(
    conn: sqlite3.Connection,
    *,
    lead_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Draft lifecycle có lead_id, chưa có presales active/converted."""
    clauses = [
        "lc.status = 'draft'",
        "lc.lead_id IS NOT NULL",
        "lc.lead_id > 0",
        "TRIM(COALESCE(lc.service_slug, '')) != ''",
    ]
    params: list[Any] = []
    if lead_id is not None:
        clauses.append("lc.lead_id = ?")
        params.append(int(lead_id))
    sql = f"""
        SELECT lc.*
        FROM crm_service_lifecycle lc
        LEFT JOIN crm_lead_presales ps ON ps.lead_id = lc.lead_id
            AND ps.status IN ('active', 'converted')
        WHERE {' AND '.join(clauses)}
          AND ps.id IS NULL
        ORDER BY lc.id ASC
    """
    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _copy_lifecycle_tasks_to_presales(
    conn: sqlite3.Connection, lifecycle_id: int, presales_id: int
) -> int:
    from crm_svc_tasks import list_tasks as list_lc_tasks

    lc_tasks = list_lc_tasks(conn, int(lifecycle_id))
    ps_tasks = list_presales_tasks(conn, int(presales_id))
    copied = 0
    for stage in PRESALES_STAGES:
        lc_list = lc_tasks.get(stage) or []
        ps_list = ps_tasks.get(stage) or []
        if not lc_list or not ps_list:
            continue
        lc_by_step = {int(t.get("step_index") or 0): t for t in lc_list}
        for ps_task in ps_list:
            step_idx = int(ps_task.get("step_index") or 0)
            src = lc_by_step.get(step_idx)
            if src is None:
                continue
            form_data = src.get("form_data") or {}
            notes = str(src.get("notes") or "")
            is_done = bool(src.get("is_done"))
            if not is_done and not notes and not form_data:
                continue
            kwargs: dict[str, Any] = {}
            if is_done:
                kwargs["is_done"] = True
            if notes:
                kwargs["notes"] = notes
            if form_data:
                kwargs["form_data"] = form_data
            if src.get("done_by") is not None:
                kwargs["done_by"] = int(src["done_by"])
            if kwargs:
                update_presales_task(conn, int(ps_task["id"]), **kwargs)
                copied += 1
    return copied


def _archive_draft_lifecycle(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    presales_id: int,
    ts: str,
) -> None:
    note = (
        f"{BACKFILL_MARKER} Dữ liệu Lead/Consult/Proposal → pre-sales #{presales_id}. "
        f"Draft lifecycle archived — dùng /crm/leads cho pre-sales."
    )[:4000]
    row = conn.execute(
        "SELECT stage, notes FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    from_stage = str(row["stage"] or "lead") if row else "lead"
    old_notes = str(row["notes"] or "") if row else ""
    merged_notes = f"{old_notes}\n{note}".strip()[:8000]
    conn.execute(
        """
        UPDATE crm_service_lifecycle
        SET status = 'closed', notes = ?, updated_at = ?
        WHERE id = ? AND status = 'draft'
        """,
        (merged_notes, ts, int(lifecycle_id)),
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, actor_type, notes, created_at)
        VALUES (?, ?, ?, 'system', ?, ?)
        """,
        (
            int(lifecycle_id),
            from_stage,
            from_stage,
            f"Backfill P4 → pre-sales #{presales_id}",
            ts,
        ),
    )


def migrate_draft_lifecycle_to_presales(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    dry_run: bool = False,
    actor: str = "backfill_p4",
) -> dict[str, Any]:
    """
    Chuyển 1 draft lifecycle (có lead_id) sang crm_lead_presales.
    Trả summary: action, presales_id, tasks_copied, ...
    """
    lc = conn.execute(
        "SELECT * FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if lc is None:
        return {"action": "error", "lifecycle_id": lifecycle_id, "error": "not_found"}
    lc = dict(lc)
    if str(lc.get("status") or "") != "draft":
        return {
            "action": "skip",
            "lifecycle_id": lifecycle_id,
            "reason": f"status={lc.get('status')}",
        }
    lead_id = int(lc["lead_id"])
    slug = str(lc.get("service_slug") or "").strip()
    if not slug:
        return {"action": "skip", "lifecycle_id": lifecycle_id, "reason": "no_service_slug"}

    existing = get_by_lead(conn, lead_id)
    if existing and str(existing.get("status") or "") in ("active", "converted"):
        return {
            "action": "skip",
            "lifecycle_id": lifecycle_id,
            "lead_id": lead_id,
            "reason": f"presales_{existing.get('status')}",
            "presales_id": int(existing["id"]),
        }

    target_stage = _presales_stage_from_lifecycle(str(lc.get("stage") or "lead"))
    ts = _ts()

    if dry_run:
        return {
            "action": "dry_run",
            "lifecycle_id": lifecycle_id,
            "lead_id": lead_id,
            "service_slug": slug,
            "target_presales_stage": target_stage,
            "would_archive_lifecycle": True,
        }

    if existing:
        ps_id = int(existing["id"])
        if str(existing.get("service_slug") or "") != slug:
            conn.execute(
                "UPDATE crm_lead_presales SET service_slug = ?, updated_at = ? WHERE id = ?",
                (slug, ts, ps_id),
            )
    else:
        ps = ensure_presales(conn, lead_id, slug, suggested_by=actor)
        ps_id = int(ps["id"])

    seed_presales_tasks(conn, ps_id, slug)
    tasks_copied = _copy_lifecycle_tasks_to_presales(conn, int(lifecycle_id), ps_id)

    cur_stage = str(
        conn.execute(
            "SELECT stage FROM crm_lead_presales WHERE id = ?", (ps_id,)
        ).fetchone()["stage"]
    )
    if presales_stage_index(target_stage) > presales_stage_index(cur_stage):
        conn.execute(
            """
            UPDATE crm_lead_presales
            SET stage = ?, stage_entered_at = ?, updated_at = ?,
                assigned_am = COALESCE(assigned_am, ?),
                notes = TRIM(notes || char(10) || ?)
            WHERE id = ?
            """,
            (
                target_stage,
                ts,
                ts,
                lc.get("assigned_am"),
                f"{BACKFILL_MARKER} từ lifecycle #{lifecycle_id} ({actor})"[:500],
                ps_id,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE crm_lead_presales
            SET assigned_am = COALESCE(assigned_am, ?), updated_at = ?,
                notes = TRIM(notes || char(10) || ?)
            WHERE id = ?
            """,
            (
                lc.get("assigned_am"),
                ts,
                f"{BACKFILL_MARKER} từ lifecycle #{lifecycle_id} ({actor})"[:500],
                ps_id,
            ),
        )

    _archive_draft_lifecycle(conn, int(lifecycle_id), presales_id=ps_id, ts=ts)
    conn.commit()
    logger.info(
        "migrate_draft_lifecycle_to_presales lc=%s lead=%s presales=%s tasks=%s",
        lifecycle_id,
        lead_id,
        ps_id,
        tasks_copied,
    )
    return {
        "action": "migrated",
        "lifecycle_id": lifecycle_id,
        "lead_id": lead_id,
        "presales_id": ps_id,
        "service_slug": slug,
        "presales_stage": target_stage,
        "tasks_copied": tasks_copied,
    }


def run_backfill_all(
    conn: sqlite3.Connection,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    lead_id: int | None = None,
    actor: str = "backfill_p4",
) -> dict[str, Any]:
    """Chạy backfill cho mọi draft lifecycle pending."""
    pending = list_draft_lifecycles_pending_backfill(
        conn, lead_id=lead_id, limit=limit
    )
    results: list[dict[str, Any]] = []
    counts = {"migrated": 0, "skip": 0, "dry_run": 0, "error": 0}
    for row in pending:
        summary = migrate_draft_lifecycle_to_presales(
            conn,
            int(row["id"]),
            dry_run=dry_run,
            actor=actor,
        )
        results.append(summary)
        action = str(summary.get("action") or "error")
        if action in counts:
            counts[action] += 1
        else:
            counts["error"] += 1
    return {
        "dry_run": dry_run,
        "pending_count": len(pending),
        "counts": counts,
        "results": results,
    }
