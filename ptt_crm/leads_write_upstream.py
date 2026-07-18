"""Proxy CRM write (assign) to NestJS when PTT_LEADS_WRITE_UPSTREAM=nest (Phase 2 W6)."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from ptt_crm.config import lead_shadow_sync_enabled, leads_write_upstream
from ptt_crm.dual_run import request_nest_json

logger = logging.getLogger(__name__)


def nest_write_upstream_enabled() -> bool:
    return leads_write_upstream() == "nest"


def _validate_assign(
    conn: sqlite3.Connection,
    lead_id: int,
    to_user_id: int,
) -> tuple[Any, int | None]:
    from crm_lead_store import fetch_lead_by_id

    prev = fetch_lead_by_id(conn, lead_id)
    if prev is None:
        raise ValueError("Không tìm thấy lead.")
    from_id = int(prev["owner_id"]) if prev["owner_id"] else None
    to_id = int(to_user_id)
    staff = conn.execute(
        "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
        (to_id,),
    ).fetchone()
    if staff is None:
        raise ValueError("Nhân viên không hợp lệ hoặc đã ngưng.")
    pd = dict(prev)
    project_id = int(pd["re_project_id"]) if pd.get("re_project_id") else None
    if project_id:
        from crm_project_leads import assert_staff_in_project

        assert_staff_in_project(conn, project_id, to_id)
    return prev, from_id


def _sync_sqlite_after_nest_assign(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    to_user_id: int,
    assigned_by: str,
    ts: str,
) -> None:
    """Ensure SQLite row reflects PG assign for legacy UI reads."""
    if lead_shadow_sync_enabled():
        try:
            from ptt_crm.lead_shadow_sync import sync_shadow_lead_ids

            sync_shadow_lead_ids([lead_id])
        except Exception as exc:
            logger.warning("shadow sync after assign lead_id=%s: %s", lead_id, exc)

    row = conn.execute("SELECT id FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return
    conn.execute(
        """
        UPDATE crm_leads
        SET owner_id = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (int(to_user_id), ts, assigned_by[:120], int(lead_id)),
    )
    conn.commit()


def _mirror_sqlite_assign_audit(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    from_user_id: int | None,
    to_user_id: int,
    reason: str,
    assigned_by: str,
    ts: str,
) -> dict[str, Any]:
    from crm_lead_store import fetch_lead_by_id, lead_row_to_dict, log_assignment, log_lead_activity

    log_assignment(
        conn,
        lead_id=lead_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        reason=reason,
        created_by=assigned_by,
        ts=ts,
    )
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=f"Phân lại lead: {reason}",
        user_id=to_user_id,
        created_by=assigned_by,
        ts=ts,
    )
    try:
        from crm_service_lifecycle import sync_assigned_am_for_lead

        sync_assigned_am_for_lead(conn, int(lead_id), overwrite=True)
    except Exception:
        pass
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        raise ValueError("Không tìm thấy lead sau assign.")
    return lead_row_to_dict(row, conn)


def _sqlite_connection() -> sqlite3.Connection:
    from ptt_jobs.config import sqlite_db_path

    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def proxy_assign_lead(
    lead_id: int,
    *,
    to_user_id: int,
    reason: str,
    assigned_by: str,
    ts: str,
) -> tuple[dict[str, Any], int]:
    """
    PATCH Nest /api/v1/leads/:id then mirror SQLite for UI + audit logs.
    Returns Flask legacy shape {"lead": {...}}.
    """
    with _sqlite_connection() as conn:
        try:
            _prev, from_id = _validate_assign(conn, lead_id, to_user_id)
        except ValueError as exc:
            msg = str(exc)
            status = 404 if "Không tìm thấy" in msg else 400
            return {"error": msg}, status

    patch_body = {
        "owner_id": int(to_user_id),
        "assigned_by": assigned_by[:120],
    }
    status, body, err = request_nest_json(
        f"/api/v1/leads/{lead_id}",
        method="PATCH",
        body=patch_body,
        actor=assigned_by[:120],
    )
    if err and not body:
        logger.warning("nest assign lead_id=%s failed: %s", lead_id, err)
        return {"error": err, "upstream": "nest"}, 502
    if status >= 400 or not body:
        return body or {"error": err or "Nest assign failed", "upstream": "nest"}, status or 502

    with _sqlite_connection() as conn:
        _sync_sqlite_after_nest_assign(
            conn,
            lead_id,
            to_user_id=to_user_id,
            assigned_by=assigned_by,
            ts=ts,
        )
        try:
            out = _mirror_sqlite_assign_audit(
                conn,
                lead_id=lead_id,
                from_user_id=from_id,
                to_user_id=int(to_user_id),
                reason=reason,
                assigned_by=assigned_by,
                ts=ts,
            )
        except ValueError as exc:
            return {"error": str(exc)}, 404

    return {"lead": out, "upstream": "nest"}, 200
