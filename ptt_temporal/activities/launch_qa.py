"""Launch QA workflow activities (Phase 3 T3)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class LaunchQaRunInput:
    run_id: str


@dataclass
class LaunchQaNotifyInput:
    run_id: str
    client_id: str
    started_by: str
    message: str
    external_campaign_id: Optional[str] = None


@activity.defn(name="fetch_launch_qa_checklist")
async def fetch_launch_qa_checklist(inp: LaunchQaRunInput) -> dict[str, Any]:
    from ptt_agency.launch_qa import fetch_launch_qa_run

    run = fetch_launch_qa_run(inp.run_id)
    if not run:
        return {"ok": False, "error": "not_found"}
    checklist = run.get("checklist") or {}
    total = len(checklist)
    done = sum(1 for v in checklist.values() if isinstance(v, dict) and v.get("completed"))
    pct = int(round(done / total * 100)) if total else 0
    return {
        "ok": True,
        "run_id": inp.run_id,
        "status": run.get("status"),
        "launch_ready": bool(run.get("launch_ready")),
        "checklist": checklist,
        "total": total,
        "completed": done,
        "percent": pct,
    }


@activity.defn(name="mark_launch_qa_passed")
async def mark_launch_qa_passed(inp: LaunchQaRunInput) -> dict[str, Any]:
    from ptt_agency.launch_qa import mark_launch_qa_passed

    return mark_launch_qa_passed(inp.run_id)


@activity.defn(name="notify_am_launch_qa")
async def notify_am_launch_qa(inp: LaunchQaNotifyInput) -> dict[str, Any]:
    recipient = inp.started_by or "am@pttads.vn"
    meta = {
        "run_id": inp.run_id,
        "client_id": inp.client_id,
        "external_campaign_id": inp.external_campaign_id,
        "kind": "launch_qa",
    }
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notification_inbox (recipient_id, category, title, body, link_url, meta)
                    VALUES (%s, 'launch_qa', %s, %s, %s, %s::jsonb)
                    RETURNING id::text
                    """,
                    (
                        recipient,
                        inp.message,
                        f"Campaign {inp.external_campaign_id or '—'}",
                        f"/crm/agency/clients/{inp.client_id}",
                        json.dumps(meta),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return {"ok": True, "notification_id": row[0] if row else None}
    except Exception as exc:
        logger.warning("notify_am_launch_qa fallback: %s", exc)
        return {"ok": False, "error": str(exc)}
