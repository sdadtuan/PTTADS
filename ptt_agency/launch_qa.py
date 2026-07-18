"""Launch QA run storage (Phase 3 T3)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

DEFAULT_CHECKLIST: dict[str, dict[str, Any]] = {
    "pixel_verified": {"label": "Pixel / dataset verified", "completed": False},
    "naming_convention": {"label": "Naming convention OK", "completed": False},
    "budget_confirmed": {"label": "Budget confirmed with client", "completed": False},
    "creative_approved": {"label": "Creative client-approved", "completed": False},
    "utm_tracking": {"label": "UTM tracking template", "completed": False},
    "qa_signoff": {"label": "PM / QA sign-off", "completed": False},
}


def _row_dict(cur, row) -> dict[str, Any]:
    cols = [d[0] for d in cur.description]
    out: dict[str, Any] = {}
    for idx, col in enumerate(cols):
        val = row[idx]
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        elif col == "id":
            val = str(val)
        out[col] = val
    return out


def create_launch_qa_run(
    *,
    client_id: str,
    external_campaign_id: str,
    campaign_name: str = "",
    started_by: str = "",
    temporal_workflow_id: str | None = None,
    temporal_run_id: str | None = None,
) -> dict[str, Any]:
    checklist = json.loads(json.dumps(DEFAULT_CHECKLIST))
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO launch_qa_runs (
                    client_id, external_campaign_id, campaign_name, checklist,
                    temporal_workflow_id, temporal_run_id, started_by
                ) VALUES (%s::uuid, %s, %s, %s::jsonb, %s, %s, %s)
                RETURNING id::text
                """,
                (
                    client_id,
                    external_campaign_id.strip(),
                    campaign_name.strip() or None,
                    json.dumps(checklist),
                    temporal_workflow_id,
                    temporal_run_id,
                    started_by or None,
                ),
            )
            run_id = str(cur.fetchone()[0])
            conn.commit()
    run = fetch_launch_qa_run(run_id)
    assert run
    return run


def fetch_launch_qa_run(run_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, client_id::text, external_campaign_id, campaign_name,
                       status, checklist, launch_ready, temporal_workflow_id, temporal_run_id,
                       started_by, started_at, completed_at, created_at, updated_at
                FROM launch_qa_runs WHERE id = %s::uuid
                """,
                (run_id,),
            )
            row = cur.fetchone()
            return _row_dict(cur, row) if row else None


def list_launch_qa_runs(client_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, client_id::text, external_campaign_id, campaign_name,
                       status, checklist, launch_ready, started_by, started_at, completed_at
                FROM launch_qa_runs
                WHERE client_id = %s::uuid
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (client_id, limit),
            )
            return [_row_dict(cur, r) for r in cur.fetchall()]


def update_launch_qa_item(
    run_id: str,
    item_key: str,
    *,
    completed: bool,
    completed_by: str = "",
    note: str = "",
) -> dict[str, Any]:
    run = fetch_launch_qa_run(run_id)
    if not run:
        raise ValueError("Không tìm thấy launch QA run")
    if run.get("status") != "in_progress":
        raise ValueError("Launch QA đã kết thúc")
    checklist = dict(run.get("checklist") or {})
    if item_key not in checklist:
        raise ValueError("Mục checklist không hợp lệ")
    entry = dict(checklist[item_key])
    entry["completed"] = bool(completed)
    if completed_by:
        entry["completed_by"] = completed_by
    if note:
        entry["note"] = note
    checklist[item_key] = entry
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE launch_qa_runs
                SET checklist = %s::jsonb, updated_at = NOW()
                WHERE id = %s::uuid AND status = 'in_progress'
                RETURNING id
                """,
                (json.dumps(checklist), run_id),
            )
            if not cur.fetchone():
                raise ValueError("Không cập nhật được run")
            conn.commit()
    updated = fetch_launch_qa_run(run_id)
    assert updated
    return updated


def launch_qa_progress(run: dict[str, Any]) -> dict[str, Any]:
    checklist = run.get("checklist") or {}
    total = len(checklist)
    done = sum(1 for v in checklist.values() if isinstance(v, dict) and v.get("completed"))
    pct = int(round(done / total * 100)) if total else 0
    return {"total": total, "completed": done, "percent": pct}


def mark_launch_qa_passed(run_id: str) -> dict[str, Any]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE launch_qa_runs
                SET status = 'passed', launch_ready = TRUE, completed_at = NOW(), updated_at = NOW()
                WHERE id = %s::uuid AND status = 'in_progress'
                RETURNING id::text
                """,
                (run_id,),
            )
            if not cur.fetchone():
                return {"ok": False, "error": "run_not_in_progress"}
            conn.commit()
    run = fetch_launch_qa_run(run_id)
    return {"ok": True, "run": run}
