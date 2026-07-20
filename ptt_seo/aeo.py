"""AEO Console v2 — PG-first seo_questions + seo_ai_mentions (Phase 4A cutover)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from ptt_seo.aeo_engine import run_aeo_content_prompt, run_aeo_scan_prompt
from ptt_seo.aeo_store import (
    add_aeo_question as _add,
    delete_aeo_question as _delete,
    get_aeo_question,
    get_latest_content,
    get_scan_history,
    latest_gap_notes,
    list_aeo_questions as _list,
    save_generated_content,
)
from ptt_seo.db import seo_read, seo_write

logger = logging.getLogger(__name__)


def list_aeo_queries(customer_id: int) -> list[dict[str, Any]]:
    with seo_read() as conn:
        return _list(conn, customer_id)


def aeo_coverage_summary(customer_id: int) -> dict[str, Any]:
    queries = list_aeo_queries(customer_id)
    total = len(queries)
    visible = sum(1 for q in queries if int(q.get("brand_visible") or 0) == 1)
    coverage_pct = round(100.0 * visible / total, 1) if total else 0.0
    last_scan_at = None
    for q in queries:
        ts = q.get("last_scan_date")
        if ts and (last_scan_at is None or str(ts) > str(last_scan_at)):
            last_scan_at = ts
    mention_count = 0
    try:
        with seo_read() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM seo_ai_mentions
                WHERE customer_id = ? AND brand_visible = 1
                  AND detected_at >= datetime('now', '-30 days')
                """,
                (customer_id,),
            ).fetchone()
            mention_count = int(row["c"] or 0) if row else 0
    except Exception:
        logger.debug("aeo mention count unavailable customer_id=%s", customer_id)
    return {
        "total": total,
        "visible": visible,
        "coverage_pct": coverage_pct,
        "readiness_avg": coverage_pct,
        "mentions_30d": mention_count,
        "last_scan_at": last_scan_at,
    }


def list_mention_trends(customer_id: int, *, days: int = 90) -> list[dict[str, Any]]:
    with seo_read() as conn:
        rows = conn.execute(
            """
            SELECT id, query_text, platform, citation_status, brand_visible,
                   gap_notes, detected_at, legacy_scan_id
            FROM seo_ai_mentions
            WHERE customer_id = ?
              AND detected_at >= datetime('now', ?)
            ORDER BY detected_at DESC
            LIMIT 200
            """,
            (customer_id, f"-{max(1, days)} days"),
        ).fetchall()
    return [dict(r) for r in rows]


def add_aeo_query(
    customer_id: int,
    query_text: str,
    brand_name: str,
    *,
    lifecycle_id: int | None = None,
    notes: str = "",
) -> int:
    with seo_write() as conn:
        return _add(
            conn,
            customer_id,
            query_text,
            brand_name,
            lifecycle_id=lifecycle_id,
            notes=notes,
        )


def delete_aeo_query(query_id: int) -> None:
    with seo_write() as conn:
        _delete(conn, query_id)


def generate_aeo_content(query_id: int) -> dict[str, Any]:
    with seo_read() as conn:
        question = get_aeo_question(conn, query_id)
        if question is None:
            return {}
        gap_notes = latest_gap_notes(conn, query_id)
    try:
        generated = run_aeo_content_prompt(
            str(question.get("query_text") or ""),
            str(question.get("brand_name") or ""),
            gap_notes,
        )
    except Exception:
        logger.exception("generate_aeo_content failed question_id=%s", query_id)
        return {}
    with seo_write() as conn:
        return save_generated_content(
            conn,
            customer_id=int(question["customer_id"]),
            question_id=query_id,
            query_text=str(question.get("query_text") or ""),
            qa_text=generated.get("qa_text") or "",
            schema_json=generated.get("schema_json") or "",
        )


def run_aeo_scan(question_id: int) -> str:
    """Run Anthropic scan and persist seo_ai_mentions; returns ai_response text."""
    from ptt_seo.connectors.aeo_scan import scan_query

    with seo_read() as conn:
        question = get_aeo_question(conn, question_id)
        if question is None:
            return ""
        customer_id = int(question["customer_id"])
    outcome = scan_query(customer_id, question_id)
    if not outcome.get("ok"):
        return ""
    with seo_read() as conn:
        history = get_scan_history(conn, question_id)
    return str(history[0].get("ai_response") or "") if history else ""


def get_aeo_scan_history(query_id: int) -> list[dict[str, Any]]:
    with seo_read() as conn:
        return get_scan_history(conn, query_id)


def get_aeo_latest_content(query_id: int) -> dict[str, Any] | None:
    with seo_read() as conn:
        return get_latest_content(conn, query_id)


def enqueue_aeo_scan(
    customer_id: int,
    *,
    query_ids: list[int] | None = None,
) -> dict[str, Any]:
    from ptt_seo.connectors.aeo_scan import scan_customer_batch

    payload = {"customer_id": customer_id, "query_ids": query_ids or []}
    idem = f"seo_aeo_scan:{customer_id}:{date.today().isoformat()}"
    try:
        from ptt_jobs.config import jobs_enabled, jobs_sync_fallback
        from ptt_jobs.db import pg_available
        from ptt_jobs.enqueue import enqueue_job

        if jobs_enabled() and pg_available():
            job = enqueue_job("seo_aeo_scan", payload, idem)
            return {"ok": True, "mode": "queue", "job": job}
        if jobs_sync_fallback():
            outcome = scan_customer_batch(customer_id, query_ids=query_ids)
            return {"ok": outcome.get("ok", False), "mode": "sync", "outcome": outcome}
        return {"ok": False, "error": "job_queue_unavailable"}
    except Exception as exc:
        logger.exception("enqueue_aeo_scan failed")
        return {"ok": False, "error": str(exc)}
