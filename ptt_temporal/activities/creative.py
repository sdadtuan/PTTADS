"""Creative approval workflow activities."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class NotifyPendingInput:
    creative_id: str
    client_id: str
    title: str
    version: int
    submitted_by: str


@dataclass
class NotifyDecisionInput:
    creative_id: str
    client_id: str
    title: str
    version: int
    submitted_by: str
    decision: str
    reviewed_by: Optional[str]
    note: Optional[str]


def _pg_conn():
    from ptt_jobs.db import pg_connection

    return pg_connection()


@activity.defn(name="notify_am_creative_pending")
async def notify_am_creative_pending(inp: NotifyPendingInput) -> dict[str, Any]:
    """Notify AM that a creative awaits client approval."""
    title = f"Creative chờ duyệt: {inp.title} (v{inp.version})"
    body = f"Client {inp.client_id} — creative {inp.creative_id} đang chờ approver trên portal."
    link = f"/portal/creatives?client_id={inp.client_id}"
    meta = {
        "creative_id": inp.creative_id,
        "client_id": inp.client_id,
        "version": inp.version,
        "kind": "creative_pending",
    }
    return _insert_notification(inp.submitted_by, title, body, link, meta)


@activity.defn(name="notify_am_creative_decision")
async def notify_am_creative_decision(inp: NotifyDecisionInput) -> dict[str, Any]:
    """Notify AM after client approve/reject/expired."""
    if inp.decision == "approved":
        title = f"Client đã duyệt: {inp.title} (v{inp.version})"
    elif inp.decision == "rejected":
        title = f"Client từ chối: {inp.title} (v{inp.version})"
    else:
        title = f"Creative hết hạn duyệt: {inp.title} (v{inp.version})"
    body = inp.note or f"Quyết định: {inp.decision}"
    if inp.reviewed_by:
        body = f"{body} — bởi {inp.reviewed_by}"
    link = f"/crm/creatives/{inp.creative_id}"
    meta = {
        "creative_id": inp.creative_id,
        "client_id": inp.client_id,
        "version": inp.version,
        "decision": inp.decision,
        "reviewed_by": inp.reviewed_by,
        "kind": "creative_decision",
    }
    return _insert_notification(inp.submitted_by, title, body, link, meta)


def _insert_notification(
    recipient_id: str,
    title: str,
    body: str,
    link_url: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    try:
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notification_inbox (
                        recipient_id, category, title, body, link_url, meta
                    ) VALUES (%s, 'creative', %s, %s, %s, %s::jsonb)
                    RETURNING id::text
                    """,
                    (recipient_id, title, body, link_url, json.dumps(meta)),
                )
                row = cur.fetchone()
            conn.commit()
        return {"ok": True, "notification_id": row[0] if row else None}
    except Exception as exc:
        logger.warning("notify_am activity fallback (PG unavailable): %s", exc)
        return {"ok": False, "error": str(exc)}
