"""Flask ↔ Temporal bridge for SEO content pipeline (Gate C P3)."""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


def content_temporal_enabled() -> bool:
    flag = os.environ.get("PTT_SEO_CONTENT_TEMPORAL", "0").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    addr = (os.environ.get("PTT_TEMPORAL_ADDRESS") or os.environ.get("TEMPORAL_ADDRESS") or "").strip()
    return bool(addr)


def content_workflow_id(content_id: int) -> str:
    return f"seo-content-{content_id}"


async def _start_workflow_async(
    content_id: int,
    customer_id: int,
    client_id: str,
    title: str,
    submitted_by: str,
) -> dict[str, Any]:
    from temporalio.client import Client

    from ptt_temporal.config import task_queue, temporal_address, temporal_namespace
    from ptt_temporal.workflows.seo_content_approval import SeoContentApprovalInput, SeoContentApprovalWorkflow

    client = await Client.connect(temporal_address(), namespace=temporal_namespace())
    wf_id = content_workflow_id(content_id)
    handle = await client.start_workflow(
        SeoContentApprovalWorkflow.run,
        SeoContentApprovalInput(
            content_id=content_id,
            customer_id=customer_id,
            client_id=client_id,
            title=title,
            submitted_by=submitted_by,
        ),
        id=wf_id,
        task_queue=task_queue(),
    )
    return {"started": True, "workflow_id": wf_id, "run_id": handle.result_run_id}


async def _signal_workflow_async(content_id: int, *, approved: bool, reviewed_by: str, note: str) -> dict[str, Any]:
    from temporalio.client import Client

    from ptt_temporal.config import temporal_address, temporal_namespace
    from ptt_temporal.workflows.seo_content_approval import SeoContentApprovalWorkflow

    client = await Client.connect(temporal_address(), namespace=temporal_namespace())
    handle = client.get_workflow_handle(content_workflow_id(content_id))
    payload = {"reviewed_by": reviewed_by, "note": note}
    if approved:
        await handle.signal(SeoContentApprovalWorkflow.approve_content, payload)
    else:
        await handle.signal(SeoContentApprovalWorkflow.reject_content, payload)
    return {"signaled": True, "workflow_id": content_workflow_id(content_id)}


def start_content_approval_workflow(
    conn: sqlite3.Connection,
    *,
    content_id: int,
    customer_id: int,
    title: str,
    submitted_by: str = "",
) -> dict[str, Any]:
    """Start Temporal workflow when content enters client_review; store workflow id."""
    if not content_temporal_enabled():
        return {"started": False, "temporal_signal": "stub"}

    from ptt_seo.portal_bridge import portal_client_for_customer

    client_id = portal_client_for_customer(conn, customer_id) or f"crm-{customer_id}"
    actor = submitted_by or "seo-ops"

    try:
        result = asyncio.run(
            _start_workflow_async(content_id, customer_id, client_id, title, actor)
        )
    except Exception as exc:
        logger.warning("SEO content Temporal start failed: %s", exc)
        return {"started": False, "temporal_signal": "skipped", "error": str(exc)}

    wf_id = result.get("workflow_id") or content_workflow_id(content_id)
    conn.execute(
        "UPDATE seo_content SET temporal_workflow_id = ?, updated_at = updated_at WHERE id = ?",
        (wf_id, content_id),
    )
    conn.commit()
    return {**result, "temporal_signal": "sent"}


def signal_content_review_workflow(
    conn: sqlite3.Connection,
    *,
    content_id: int,
    approved: bool,
    reviewed_by: str = "",
    note: str = "",
) -> dict[str, Any]:
    if not content_temporal_enabled():
        return {"signaled": False, "temporal_signal": "stub"}
    row = conn.execute(
        "SELECT temporal_workflow_id FROM seo_content WHERE id = ?",
        (content_id,),
    ).fetchone()
    wf_id = dict(row)["temporal_workflow_id"] if row else ""
    if not wf_id:
        return {"signaled": False, "temporal_signal": "skipped", "reason": "no_workflow_id"}
    try:
        result = asyncio.run(
            _signal_workflow_async(content_id, approved=approved, reviewed_by=reviewed_by, note=note)
        )
    except Exception as exc:
        logger.warning("SEO content Temporal signal failed: %s", exc)
        return {"signaled": False, "temporal_signal": "skipped", "error": str(exc)}
    return {**result, "temporal_signal": "sent"}
