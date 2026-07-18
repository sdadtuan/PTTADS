"""SOP PG read path with feature flag (Phase 3 Track D3)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_crm.config import sop_read_source_pg
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def pg_sop_ready() -> bool:
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('sop_templates', 'sop_runs', 'sop_run_tasks')
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 3
    except Exception as exc:
        logger.debug("pg_sop_ready: %s", exc)
        return False


def list_sop_templates(*, active_only: bool = True) -> list[dict[str, Any]]:
    if not sop_read_source_pg() or not pg_sop_ready():
        return []
    clause = "WHERE active IS TRUE" if active_only else ""
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, sqlite_template_id, code, name, channel, description, notes, active
                FROM sop_templates
                {clause}
                ORDER BY name
                """
            )
            cols = [d[0] for d in cur.description]
            return [
                {
                    "id": int(rec["sqlite_template_id"] or rec["id"]),
                    "pg_id": int(rec["id"]),
                    "code": rec.get("code") or "",
                    "name": rec.get("name") or "",
                    "channel": rec.get("channel") or "other",
                    "description": rec.get("description") or "",
                    "notes": rec.get("notes") or "",
                    "active": bool(rec.get("active")),
                }
                for rec in (dict(zip(cols, row)) for row in cur.fetchall())
            ]


def list_sop_runs(*, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if not sop_read_source_pg() or not pg_sop_ready():
        return []
    lim = max(1, min(int(limit), 300))
    params: list[Any] = [lim]
    where = ""
    if status:
        where = "WHERE status = %s"
        params = [status, lim]
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, sqlite_run_id, hub_campaign_id, template_id, name, status,
                       start_date, notes, created_at, updated_at
                FROM sop_runs
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            out: list[dict[str, Any]] = []
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                out.append(
                    {
                        "id": int(rec["sqlite_run_id"] or rec["id"]),
                        "pg_id": int(rec["id"]),
                        "campaign_id": int(rec["hub_campaign_id"]) if rec.get("hub_campaign_id") else None,
                        "template_id": int(rec["template_id"]) if rec.get("template_id") else None,
                        "name": rec.get("name") or "",
                        "status": rec.get("status") or "active",
                        "start_date": rec["start_date"].isoformat() if rec.get("start_date") else "",
                        "notes": rec.get("notes") or "",
                    }
                )
            return out


def sop_run_tasks(run_id: int) -> list[dict[str, Any]]:
    if not sop_read_source_pg() or not pg_sop_ready():
        return []
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, t.sqlite_task_id, t.position, t.title, t.description,
                       t.status, t.due_date, t.completed_at, t.assignee, t.checklist_json
                FROM sop_run_tasks t
                JOIN sop_runs r ON r.id = t.run_id
                WHERE r.sqlite_run_id = %s OR r.id = %s
                ORDER BY t.position
                """,
                (run_id, run_id),
            )
            cols = [d[0] for d in cur.description]
            out: list[dict[str, Any]] = []
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                checklist = rec.get("checklist_json")
                if isinstance(checklist, str):
                    try:
                        checklist = json.loads(checklist)
                    except json.JSONDecodeError:
                        checklist = []
                out.append(
                    {
                        "id": int(rec["sqlite_task_id"] or rec["id"]),
                        "position": int(rec.get("position") or 0),
                        "title": rec.get("title") or "",
                        "description": rec.get("description") or "",
                        "status": rec.get("status") or "pending",
                        "due_date": rec["due_date"].isoformat() if rec.get("due_date") else "",
                        "completed_at": rec["completed_at"].isoformat() if rec.get("completed_at") else "",
                        "assignee": rec.get("assignee") or "",
                        "checklist_json": checklist or [],
                    }
                )
            return out
