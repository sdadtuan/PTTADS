# tests/test_crm_aeo.py
from __future__ import annotations
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import crm_aeo as m


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT ''
        );
    """)
    m.ensure_schema(conn)
    return conn


def _seed_customer(conn: sqlite3.Connection) -> int:
    conn.execute("INSERT INTO crm_customers (name) VALUES (?)", ("Test KH",))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestEnsureSchema(unittest.TestCase):
    def test_creates_tables(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_aeo_queries", tables)
        self.assertIn("crm_aeo_scans", tables)
        self.assertIn("crm_aeo_content", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        m.ensure_schema(conn)  # second call must not raise
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_aeo_queries").fetchone()[0], 0)


class TestAddQuery(unittest.TestCase):
    def test_returns_int_id(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "SEO local giá?", "PTTCOM")
        self.assertIsInstance(qid, int)
        self.assertGreater(qid, 0)

    def test_lifecycle_id_nullable(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "Agency uy tín?", "PTTCOM", lifecycle_id=None)
        row = conn.execute("SELECT lifecycle_id FROM crm_aeo_queries WHERE id = ?", (qid,)).fetchone()
        self.assertIsNone(row["lifecycle_id"])

    def test_notes_stored(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "query?", "Brand", notes="note123")
        row = conn.execute("SELECT notes FROM crm_aeo_queries WHERE id = ?", (qid,)).fetchone()
        self.assertEqual(row["notes"], "note123")


class TestListQueries(unittest.TestCase):
    def test_empty_returns_empty_list(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        self.assertEqual(m.list_queries(conn, cid), [])

    def test_returns_last_scan_date_and_brand_visible(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute(
            "INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)",
            (qid, "resp", 1, "gap", "2026-06-01 00:00:00"),
        )
        conn.commit()
        rows = m.list_queries(conn, cid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["brand_visible"], 1)
        self.assertEqual(rows[0]["last_scan_date"], "2026-06-01 00:00:00")

    def test_no_scan_returns_none_fields(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        m.add_query(conn, cid, "q?", "B")
        rows = m.list_queries(conn, cid)
        self.assertIsNone(rows[0]["last_scan_date"])
        self.assertIsNone(rows[0]["brand_visible"])


class TestDeleteQuery(unittest.TestCase):
    def test_deletes_query(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        m.delete_query(conn, qid)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_aeo_queries WHERE id = ?", (qid,)).fetchone()[0], 0)

    def test_cascade_deletes_scans(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute(
            "INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)",
            (qid, "r", 0, "g", "2026-06-01"),
        )
        conn.commit()
        m.delete_query(conn, qid)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM crm_aeo_scans WHERE query_id = ?", (qid,)).fetchone()[0], 0)


class TestRunScan(unittest.TestCase):
    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.run_scan(conn, qid)
        self.assertEqual(result, "")

    def test_saves_scan_on_success(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="## Câu trả lời AI điển hình\nAI says.\n## Phân tích Brand Visibility\nbrand_visible: yes\nB xuất hiện.\n## Content Gap\nCần thêm FAQ.")]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.run_scan(conn, qid)
        self.assertIn("brand_visible", result)
        row = conn.execute("SELECT brand_visible, gap_notes FROM crm_aeo_scans WHERE query_id = ?", (qid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["brand_visible"], 1)
        self.assertIn("FAQ", row["gap_notes"])


class TestGetScanHistory(unittest.TestCase):
    def test_no_scans_returns_empty(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        self.assertEqual(m.get_scan_history(conn, qid), [])

    def test_returns_order_by_id_desc(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute("INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)", (qid, "r1", 0, "g1", "2026-06-01"))
        conn.execute("INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)", (qid, "r2", 1, "g2", "2026-06-02"))
        conn.commit()
        history = m.get_scan_history(conn, qid)
        self.assertEqual(history[0]["ai_response"], "r2")


class TestGenerateContent(unittest.TestCase):
    def test_no_api_key_returns_empty_dict(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.generate_content(conn, qid)
        self.assertEqual(result, {})

    def test_saves_content_on_success(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute("INSERT INTO crm_aeo_scans (query_id, ai_response, brand_visible, gap_notes, created_at) VALUES (?,?,?,?,?)", (qid, "r", 1, "Cần FAQ", "2026-06-01"))
        conn.commit()
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='## Q&A Pairs\nQ: Hỏi?\nA: Trả lời B.\n## FAQ Schema JSON-LD\n{"@context":"https://schema.org"}')]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.generate_content(conn, qid)
        self.assertIn("qa_text", result)
        self.assertIn("schema_json", result)
        row = conn.execute("SELECT qa_text, schema_json FROM crm_aeo_content WHERE query_id = ?", (qid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertIn("Hỏi", row["qa_text"])


class TestGetLatestContent(unittest.TestCase):
    def test_no_content_returns_none(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        self.assertIsNone(m.get_latest_content(conn, qid))

    def test_returns_latest_by_id_desc(self):
        conn = _setup_conn()
        cid = _seed_customer(conn)
        qid = m.add_query(conn, cid, "q?", "B")
        conn.execute("INSERT INTO crm_aeo_content (query_id, qa_text, schema_json, created_at) VALUES (?,?,?,?)", (qid, "qa1", "{}", "2026-06-01"))
        conn.execute("INSERT INTO crm_aeo_content (query_id, qa_text, schema_json, created_at) VALUES (?,?,?,?)", (qid, "qa2", "{}", "2026-06-02"))
        conn.commit()
        result = m.get_latest_content(conn, qid)
        self.assertIsNotNone(result)
        self.assertEqual(result["qa_text"], "qa2")


if __name__ == "__main__":
    unittest.main()
