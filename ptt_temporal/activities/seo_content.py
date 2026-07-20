"""SEO content approval Temporal activities (Gate C P3)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class SeoContentPendingInput:
    content_id: int
    customer_id: int
    client_id: str
    title: str
    submitted_by: str


@dataclass
class SeoContentDecisionInput:
    content_id: int
    customer_id: int
    client_id: str
    title: str
    submitted_by: str
    decision: str
    reviewed_by: Optional[str]
    note: Optional[str]


def _pg_conn():
    from ptt_jobs.db import pg_connection

    return pg_connection()


@activity.defn(name="notify_am_seo_content_pending")
async def notify_am_seo_content_pending(inp: SeoContentPendingInput) -> dict[str, Any]:
    title = f"SEO content chờ client duyệt: {inp.title}"
    body = f"Client {inp.client_id} — content #{inp.content_id} đang ở client_review."
    link = f"/crm/seo/content?customer_id={inp.customer_id}&content_id={inp.content_id}"
    meta = {
        "content_id": inp.content_id,
        "customer_id": inp.customer_id,
        "client_id": inp.client_id,
        "kind": "seo_content_pending",
    }
    return _insert_notification(inp.submitted_by, title, body, link, meta)


@activity.defn(name="notify_am_seo_content_decision")
async def notify_am_seo_content_decision(inp: SeoContentDecisionInput) -> dict[str, Any]:
    if inp.decision == "approved":
        title = f"Client đã duyệt SEO content: {inp.title}"
    elif inp.decision == "rejected":
        title = f"Client từ chối SEO content: {inp.title}"
    else:
        title = f"SEO content hết hạn duyệt: {inp.title}"
    body = inp.note or f"Quyết định: {inp.decision}"
    if inp.reviewed_by:
        body = f"{body} — bởi {inp.reviewed_by}"
    link = f"/crm/seo/content?customer_id={inp.customer_id}&content_id={inp.content_id}"
    meta = {
        "content_id": inp.content_id,
        "customer_id": inp.customer_id,
        "client_id": inp.client_id,
        "decision": inp.decision,
        "reviewed_by": inp.reviewed_by,
        "kind": "seo_content_decision",
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
                    ) VALUES (%s, 'seo_content', %s, %s, %s, %s::jsonb)
                    RETURNING id::text
                    """,
                    (recipient_id, title, body, link_url, json.dumps(meta)),
                )
                row = cur.fetchone()
            conn.commit()
        return {"ok": True, "notification_id": row[0] if row else None}
    except Exception as exc:
        logger.warning("notify_am seo content fallback (PG unavailable): %s", exc)
        return {"ok": False, "error": str(exc)}
