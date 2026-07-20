"""AEO query store — PG-first via seo_questions (Phase 4A cutover)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ptt_seo.db import SeoDB

_AEO_SOURCE = "aeo"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _row_bool(value: Any) -> int:
    if value in (True, 1, "1", "true", "t"):
        return 1
    return 0


def list_aeo_questions(conn: SeoDB, customer_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT q.id, q.question_text AS query_text, q.brand_name, q.notes,
               q.lifecycle_id, q.created_at,
               m.detected_at AS last_scan_date,
               m.brand_visible
        FROM seo_questions q
        LEFT JOIN seo_ai_mentions m ON m.id = (
            SELECT id FROM seo_ai_mentions
            WHERE question_id = q.id ORDER BY id DESC LIMIT 1
        )
        WHERE q.customer_id = ? AND q.source = ? AND q.status = 'active'
        ORDER BY q.id
        """,
        (customer_id, _AEO_SOURCE),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["brand_visible"] = _row_bool(item.get("brand_visible"))
        out.append(item)
    return out


def get_aeo_question(conn: SeoDB, question_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, customer_id, question_text AS query_text, brand_name, notes,
               lifecycle_id, legacy_aeo_query_id, created_at
        FROM seo_questions
        WHERE id = ? AND source = ? AND status = 'active'
        """,
        (question_id, _AEO_SOURCE),
    ).fetchone()
    return dict(row) if row else None


def add_aeo_question(
    conn: SeoDB,
    customer_id: int,
    query_text: str,
    brand_name: str,
    *,
    lifecycle_id: int | None = None,
    notes: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_questions (
            customer_id, question_text, intent, funnel_stage, source,
            brand_name, lifecycle_id, notes, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            query_text,
            "informational",
            "awareness",
            _AEO_SOURCE,
            brand_name,
            lifecycle_id,
            notes,
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def delete_aeo_question(conn: SeoDB, question_id: int) -> None:
    conn.execute(
        "UPDATE seo_questions SET status = 'archived' WHERE id = ? AND source = ?",
        (question_id, _AEO_SOURCE),
    )
    conn.commit()


def list_customers_with_aeo(conn: SeoDB) -> list[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT customer_id FROM seo_questions
        WHERE source = ? AND status = 'active'
        ORDER BY customer_id
        """,
        (_AEO_SOURCE,),
    ).fetchall()
    return [int(r["customer_id"]) for r in rows]


def get_scan_history(conn: SeoDB, question_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, ai_response, brand_visible, gap_notes, detected_at AS created_at
        FROM seo_ai_mentions
        WHERE question_id = ?
        ORDER BY id DESC
        """,
        (question_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["brand_visible"] = _row_bool(item.get("brand_visible"))
        out.append(item)
    return out


def latest_gap_notes(conn: SeoDB, question_id: int) -> str:
    row = conn.execute(
        """
        SELECT gap_notes FROM seo_ai_mentions
        WHERE question_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (question_id,),
    ).fetchone()
    return str(row["gap_notes"]) if row else ""


def citation_status(brand_visible: bool, gap_notes: str) -> str:
    gap = (gap_notes or "").strip()
    if brand_visible and not gap:
        return "cited"
    if brand_visible:
        return "mentioned"
    return "absent"


def insert_mention(
    conn: SeoDB,
    *,
    customer_id: int,
    question_id: int,
    query_text: str,
    scan: dict[str, Any],
    legacy_scan_id: int | None = None,
) -> int:
    brand_visible = bool(scan.get("brand_visible"))
    gap_notes = str(scan.get("gap_notes") or "")
    cur = conn.execute(
        """
        INSERT INTO seo_ai_mentions (
            customer_id, question_id, platform, query_text, citation_status,
            brand_visible, gap_notes, ai_response, legacy_scan_id, detected_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            question_id,
            "anthropic_sim",
            query_text,
            citation_status(brand_visible, gap_notes),
            1 if brand_visible else 0,
            gap_notes,
            str(scan.get("ai_response") or ""),
            legacy_scan_id,
            scan.get("detected_at") or scan.get("created_at") or _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def save_generated_content(
    conn: SeoDB,
    *,
    customer_id: int,
    question_id: int,
    query_text: str,
    qa_text: str,
    schema_json: str,
) -> dict[str, Any]:
    brief = json.dumps({"qa_text": qa_text, "schema_json": schema_json}, ensure_ascii=False)
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO seo_content (
            customer_id, title, slug, content_type, workflow_status,
            target_question_id, brief_json, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            query_text[:200],
            f"aeo-faq-{question_id}",
            "aeo_faq",
            "draft",
            question_id,
            brief,
            ts,
            ts,
        ),
    )
    conn.commit()
    return {"qa_text": qa_text, "schema_json": schema_json, "created_at": ts, "id": cur.lastrowid}


def get_latest_content(conn: SeoDB, question_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, brief_json, created_at FROM seo_content
        WHERE target_question_id = ? AND content_type = 'aeo_faq'
        ORDER BY id DESC LIMIT 1
        """,
        (question_id,),
    ).fetchone()
    if row is None:
        return None
    brief_raw = row.get("brief_json") if isinstance(row, dict) else row["brief_json"]
    if isinstance(brief_raw, str):
        try:
            brief = json.loads(brief_raw or "{}")
        except json.JSONDecodeError:
            brief = {}
    else:
        brief = brief_raw or {}
    return {
        "id": row["id"],
        "qa_text": brief.get("qa_text") or "",
        "schema_json": brief.get("schema_json") or "",
        "created_at": row["created_at"],
    }
