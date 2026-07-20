"""AEO scan connector — PG-first seo_questions + seo_ai_mentions (Phase 4A cutover)."""
from __future__ import annotations

import logging
import os
from typing import Any

from ptt_seo.aeo_engine import run_aeo_scan_prompt, stub_scan_result
from ptt_seo.aeo_store import get_aeo_question, insert_mention
from ptt_seo.db import seo_read, seo_write

logger = logging.getLogger(__name__)


def aeo_stub_mode() -> bool:
    return os.environ.get("PTT_AEO_SCAN_STUB", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _run_scan_for_question(question: dict[str, Any]) -> dict[str, Any]:
    if aeo_stub_mode():
        return stub_scan_result(str(question.get("query_text") or ""))
    try:
        return run_aeo_scan_prompt(
            str(question.get("query_text") or ""),
            str(question.get("brand_name") or ""),
            str(question.get("notes") or ""),
        )
    except Exception:
        logger.exception("aeo scan prompt failed question_id=%s", question.get("id"))
        return {}


def scan_query(customer_id: int, query_id: int) -> dict[str, Any]:
    """Run AEO scan and persist seo_ai_mentions only (no crm_aeo_* writes)."""
    with seo_read() as conn:
        question = get_aeo_question(conn, query_id)
        if question is None:
            return {"ok": False, "error": "query_not_found"}
        if int(question["customer_id"]) != customer_id:
            return {"ok": False, "error": "customer_mismatch"}

    scan = _run_scan_for_question(question)
    if not scan:
        return {"ok": False, "error": "scan_failed"}

    try:
        with seo_write() as conn:
            mention_id = insert_mention(
                conn,
                customer_id=customer_id,
                question_id=query_id,
                query_text=str(question.get("query_text") or ""),
                scan=scan,
            )
    except Exception as exc:
        logger.exception("aeo mention insert failed query_id=%s", query_id)
        return {"ok": False, "error": str(exc)}

    return {
        "ok": True,
        "mention_id": mention_id,
        "brand_visible": bool(scan.get("brand_visible")),
        "gap_notes": scan.get("gap_notes") or "",
    }


def scan_customer_batch(
    customer_id: int,
    *,
    query_ids: list[int] | None = None,
) -> dict[str, Any]:
    from ptt_seo.aeo import list_aeo_queries

    if query_ids:
        ids = [int(i) for i in query_ids]
    else:
        ids = [int(q["id"]) for q in list_aeo_queries(customer_id)]

    if not ids:
        return {"ok": True, "skipped": True, "reason": "no_queries", "scanned": 0}

    results: list[dict[str, Any]] = []
    ok_count = 0
    for qid in ids:
        outcome = scan_query(customer_id, qid)
        results.append({"query_id": qid, **outcome})
        if outcome.get("ok"):
            ok_count += 1

    failed = len(ids) - ok_count
    return {
        "ok": failed == 0,
        "customer_id": customer_id,
        "scanned": len(ids),
        "ok_count": ok_count,
        "failed": failed,
        "results": results,
    }


def process_seo_aeo_scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(payload.get("customer_id") or 0)
    if not customer_id:
        return {"ok": False, "error": "missing_customer_id"}
    raw_ids = payload.get("query_ids") or []
    query_ids = [int(i) for i in raw_ids] if raw_ids else None
    return scan_customer_batch(customer_id, query_ids=query_ids)
