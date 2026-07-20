"""Scheduled AEO batch scan + auto content drafts from gaps (Gate D)."""
from __future__ import annotations

import os
import sqlite3
from typing import Any

from ptt_seo.connectors.aeo_scan import scan_customer_batch


def aeo_schedule_enabled() -> bool:
    return os.getenv("PTT_AEO_SCHEDULE_ENABLED", "1").strip().lower() not in ("0", "false", "no")


def aeo_auto_draft_enabled() -> bool:
    return os.getenv("PTT_AEO_AUTO_DRAFT_ENABLED", "1").strip().lower() not in ("0", "false", "no")


def _existing_question_content(conn: sqlite3.Connection, question_id: int) -> bool:
    row = conn.execute(
        """
        SELECT id FROM seo_content
        WHERE target_question_id = ? AND workflow_status != 'archived'
        LIMIT 1
        """,
        (question_id,),
    ).fetchone()
    return row is not None


def create_drafts_from_gaps(
    conn: sqlite3.Connection,
    customer_id: int,
    scan_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create brief_ready content for queries with brand_visible=0 after scan."""
    if not aeo_auto_draft_enabled():
        return []
    from ptt_seo.content import create_content_from_research

    drafts: list[dict[str, Any]] = []
    for item in scan_results:
        qid = int(item.get("query_id") or 0)
        if not qid or not item.get("ok"):
            continue
        if item.get("brand_visible"):
            continue
        if _existing_question_content(conn, qid):
            continue
        gap = str(item.get("gap_notes") or "").strip()
        brief = {"sections": [{"title": "AEO gap", "body": gap or "Improve AI visibility for this query."}]}
        cid = create_content_from_research(
            conn,
            customer_id,
            question_id=qid,
            brief=brief,
        )
        drafts.append({"content_id": cid, "question_id": qid})
    return drafts


def run_aeo_schedule_for_customer(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    batch = scan_customer_batch(customer_id)
    drafts: list[dict[str, Any]] = []
    if batch.get("ok") or batch.get("ok_count", 0) > 0:
        drafts = create_drafts_from_gaps(conn, customer_id, batch.get("results") or [])
    return {
        "customer_id": customer_id,
        "scan": batch,
        "drafts_created": len(drafts),
        "drafts": drafts,
    }


def run_aeo_schedule_all(
    conn: sqlite3.Connection,
    *,
    max_customers: int | None = None,
) -> dict[str, Any]:
    from ptt_seo.aeo_store import list_customers_with_aeo

    customer_ids = list_customers_with_aeo(conn)
    if max_customers is not None:
        customer_ids = customer_ids[: max(0, max_customers)]
    results: list[dict[str, Any]] = []
    total_drafts = 0
    for cid in customer_ids:
        row = run_aeo_schedule_for_customer(conn, cid)
        total_drafts += row.get("drafts_created", 0)
        results.append(row)
    return {
        "ok": True,
        "customers": len(customer_ids),
        "drafts_created": total_drafts,
        "results": results,
    }
