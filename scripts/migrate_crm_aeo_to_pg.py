#!/usr/bin/env python3
"""Migrate crm_aeo_* (SQLite) → seo_questions + seo_ai_mentions + seo_content (PG)."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from ptt_jobs.db import pg_available, pg_connection
from ptt_seo.pg_schema import ensure_pg_schema


def _sqlite_path() -> Path:
    import os

    raw = os.environ.get("PTT_SQLITE_PATH", "ptt.db").strip()
    p = Path(raw)
    return p if p.is_absolute() else Path(__file__).resolve().parents[1] / p


def _citation_status(brand_visible: int, gap_notes: str) -> str:
    gap = (gap_notes or "").strip()
    if brand_visible and not gap:
        return "cited"
    if brand_visible:
        return "mentioned"
    return "absent"


def fetch_queries(sqlite: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = sqlite.execute(
        """
        SELECT id, customer_id, lifecycle_id, query_text, brand_name, notes, created_at
        FROM crm_aeo_queries ORDER BY id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_scans(sqlite: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = sqlite.execute(
        """
        SELECT s.id AS scan_id, s.ai_response, s.brand_visible, s.gap_notes, s.created_at,
               q.id AS legacy_query_id, q.customer_id, q.query_text
        FROM crm_aeo_scans s
        JOIN crm_aeo_queries q ON q.id = s.query_id
        ORDER BY s.id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_content(sqlite: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = sqlite.execute(
        """
        SELECT c.id, c.query_id AS legacy_query_id, c.qa_text, c.schema_json, c.created_at,
               q.customer_id, q.query_text
        FROM crm_aeo_content c
        JOIN crm_aeo_queries q ON q.id = c.query_id
        ORDER BY c.id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _count_pg(cur: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("seo_questions", "seo_ai_mentions", "seo_content"):
        cur.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE 1=1")
        row = cur.fetchone()
        counts[table] = int(row["c"] if isinstance(row, dict) else row[0])
    cur.execute(
        "SELECT COUNT(*) AS c FROM seo_questions WHERE source = 'aeo'"
    )
    row = cur.fetchone()
    counts["seo_questions_aeo"] = int(row["c"] if isinstance(row, dict) else row[0])
    return counts


def apply(*, dry_run: bool, verify_only: bool) -> dict[str, Any]:
    if not pg_available():
        raise SystemExit("DATABASE_URL / PostgreSQL not available")
    sp = _sqlite_path()
    if not sp.exists():
        raise SystemExit(f"SQLite not found: {sp}")
    sqlite = sqlite3.connect(str(sp))
    sqlite.row_factory = sqlite3.Row

    queries = fetch_queries(sqlite)
    scans = fetch_scans(sqlite)
    content_rows = fetch_content(sqlite)

    summary = {
        "legacy_queries": len(queries),
        "legacy_scans": len(scans),
        "legacy_content": len(content_rows),
        "migrated_questions": 0,
        "migrated_mentions": 0,
        "migrated_content": 0,
        "skipped_questions": 0,
        "skipped_mentions": 0,
        "skipped_content": 0,
    }

    if verify_only:
        with pg_connection() as pg:
            ensure_pg_schema(pg)
            with pg.cursor() as cur:
                cur.execute("SET search_path TO seo_aeo, public")
                summary["pg_counts"] = _count_pg(cur)
        print(json.dumps(summary, indent=2))
        return summary

    if dry_run:
        print(
            f"Would migrate {len(queries)} queries, {len(scans)} scans, "
            f"{len(content_rows)} content rows"
        )
        return summary

    legacy_to_pg: dict[int, int] = {}
    with pg_connection() as pg:
        ensure_pg_schema(pg)
        with pg.cursor() as cur:
            cur.execute("SET search_path TO seo_aeo, public")

            for row in queries:
                cur.execute(
                    """
                    SELECT id FROM seo_questions
                    WHERE legacy_aeo_query_id = %s LIMIT 1
                    """,
                    (row["id"],),
                )
                existing = cur.fetchone()
                if existing:
                    legacy_to_pg[int(row["id"])] = int(
                        existing["id"] if isinstance(existing, dict) else existing[0]
                    )
                    summary["skipped_questions"] += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO seo_questions (
                        customer_id, question_text, intent, funnel_stage, source,
                        legacy_aeo_query_id, brand_name, lifecycle_id, notes, created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        row["customer_id"],
                        row["query_text"],
                        "informational",
                        "awareness",
                        "aeo",
                        row["id"],
                        row["brand_name"] or "",
                        row["lifecycle_id"],
                        row["notes"] or "",
                        row["created_at"],
                    ),
                )
                new_id = cur.fetchone()
                pg_id = int(new_id["id"] if isinstance(new_id, dict) else new_id[0])
                legacy_to_pg[int(row["id"])] = pg_id
                summary["migrated_questions"] += 1

            for row in scans:
                cur.execute(
                    "SELECT 1 FROM seo_ai_mentions WHERE legacy_scan_id = %s LIMIT 1",
                    (row["scan_id"],),
                )
                if cur.fetchone():
                    summary["skipped_mentions"] += 1
                    continue
                question_id = legacy_to_pg.get(int(row["legacy_query_id"]))
                if question_id is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO seo_ai_mentions (
                        customer_id, question_id, platform, query_text, citation_status,
                        brand_visible, gap_notes, ai_response, legacy_scan_id, detected_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        row["customer_id"],
                        question_id,
                        "anthropic_sim",
                        row["query_text"],
                        _citation_status(int(row["brand_visible"] or 0), row["gap_notes"] or ""),
                        bool(int(row["brand_visible"] or 0)),
                        row["gap_notes"] or "",
                        row["ai_response"] or "",
                        row["scan_id"],
                        row["created_at"],
                    ),
                )
                summary["migrated_mentions"] += 1

            for row in content_rows:
                question_id = legacy_to_pg.get(int(row["legacy_query_id"]))
                if question_id is None:
                    continue
                cur.execute(
                    """
                    SELECT 1 FROM seo_content
                    WHERE target_question_id = %s AND content_type = 'aeo_faq'
                      AND created_at = %s
                    LIMIT 1
                    """,
                    (question_id, row["created_at"]),
                )
                if cur.fetchone():
                    summary["skipped_content"] += 1
                    continue
                brief = json.dumps(
                    {"qa_text": row["qa_text"] or "", "schema_json": row["schema_json"] or ""},
                    ensure_ascii=False,
                )
                cur.execute(
                    """
                    INSERT INTO seo_content (
                        customer_id, title, slug, content_type, workflow_status,
                        target_question_id, brief_json, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                    """,
                    (
                        row["customer_id"],
                        (row["query_text"] or "")[:200],
                        f"aeo-faq-{question_id}",
                        "aeo_faq",
                        "draft",
                        question_id,
                        brief,
                        row["created_at"],
                        row["created_at"],
                    ),
                )
                summary["migrated_content"] += 1

            summary["pg_counts"] = _count_pg(cur)
        pg.commit()

    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate crm_aeo SQLite tables to PG seo_questions + mentions + content"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    apply(dry_run=args.dry_run, verify_only=args.verify_only)


if __name__ == "__main__":
    main()
