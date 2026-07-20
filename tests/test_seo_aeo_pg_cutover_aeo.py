"""Tests for AEO PG cutover — seo_questions store + migration mapping."""
from __future__ import annotations

import json
import sqlite3
import unittest

from ptt_seo.aeo_store import (
    add_aeo_question,
    delete_aeo_question,
    get_latest_content,
    get_scan_history,
    insert_mention,
    list_aeo_questions,
    save_generated_content,
)
from ptt_seo.db import SeoDB
from ptt_seo.schema import ensure_schema


def _seo_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_ai_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            question_id INTEGER,
            platform TEXT NOT NULL DEFAULT 'anthropic_sim',
            query_text TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            citation_status TEXT NOT NULL DEFAULT 'absent',
            brand_visible INTEGER NOT NULL DEFAULT 0,
            gap_notes TEXT NOT NULL DEFAULT '',
            ai_response TEXT NOT NULL DEFAULT '',
            legacy_scan_id INTEGER,
            detected_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    return SeoDB(conn, "sqlite")


class TestAeoStore(unittest.TestCase):
    def test_add_list_delete_question(self) -> None:
        db = _seo_db()
        qid = add_aeo_question(db, 1, "best seo?", "PTTADS", notes="note")
        rows = list_aeo_questions(db, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["query_text"], "best seo?")
        self.assertEqual(rows[0]["brand_name"], "PTTADS")
        delete_aeo_question(db, qid)
        self.assertEqual(list_aeo_questions(db, 1), [])

    def test_scan_history_and_content(self) -> None:
        db = _seo_db()
        qid = add_aeo_question(db, 2, "aeo query", "Brand")
        insert_mention(
            db,
            customer_id=2,
            question_id=qid,
            query_text="aeo query",
            scan={
                "brand_visible": True,
                "gap_notes": "need FAQ",
                "ai_response": "response",
                "detected_at": "2026-07-19",
            },
        )
        history = get_scan_history(db, qid)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["brand_visible"], 1)

        saved = save_generated_content(
            db,
            customer_id=2,
            question_id=qid,
            query_text="aeo query",
            qa_text="Q: x\nA: y",
            schema_json='{"@type":"FAQPage"}',
        )
        self.assertIn("qa_text", saved)
        latest = get_latest_content(db, qid)
        assert latest is not None
        self.assertIn("FAQPage", latest["schema_json"])

    def test_list_shows_latest_scan(self) -> None:
        db = _seo_db()
        qid = add_aeo_question(db, 3, "q", "B")
        insert_mention(
            db,
            customer_id=3,
            question_id=qid,
            query_text="q",
            scan={"brand_visible": False, "gap_notes": "g", "ai_response": "r", "detected_at": "2026-07-01"},
        )
        insert_mention(
            db,
            customer_id=3,
            question_id=qid,
            query_text="q",
            scan={"brand_visible": True, "gap_notes": "", "ai_response": "r2", "detected_at": "2026-07-19"},
        )
        rows = list_aeo_questions(db, 3)
        self.assertEqual(rows[0]["brand_visible"], 1)
        self.assertEqual(rows[0]["last_scan_date"], "2026-07-19")


class TestMigrateMapping(unittest.TestCase):
    def test_legacy_id_column_exists(self) -> None:
        db = _seo_db()
        row = db.execute(
            """
            INSERT INTO seo_questions (
                customer_id, question_text, source, legacy_aeo_query_id,
                brand_name, created_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (1, "legacy q", "aeo", 99, "Brand", "2026-07-19"),
        )
        db.commit()
        self.assertIsNotNone(row.lastrowid)
        found = db.execute(
            "SELECT id FROM seo_questions WHERE legacy_aeo_query_id = ?",
            (99,),
        ).fetchone()
        assert found is not None
        mapping = {99: int(found["id"])}
        self.assertEqual(json.dumps(mapping), json.dumps({99: int(found["id"])}))


if __name__ == "__main__":
    unittest.main()
