# tests/test_crm_customer_brief.py
from __future__ import annotations
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import crm_customer_brief as m


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT '',
            occupation TEXT NOT NULL DEFAULT '',
            lead_source TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            assigned_am INTEGER,
            assigned_sp INTEGER,
            contract_id INTEGER
        );
        CREATE TABLE crm_svc_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            received_on TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_svc_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE crm_svc_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT ''
        );
    """)
    m.ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_creates_table(self):
        conn = _setup_conn()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crm_customer_brief_scans'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_idempotent(self):
        conn = _setup_conn()
        m.ensure_schema(conn)  # second call should not raise
        row = conn.execute("SELECT COUNT(*) FROM crm_customer_brief_scans").fetchone()
        self.assertEqual(row[0], 0)


class TestGetCustomerSnapshot(unittest.TestCase):
    def _seed_customer(self, conn, *, created_at="2024-01-15 00:00:00"):
        conn.execute(
            "INSERT INTO crm_customers (name, company, occupation, lead_source, created_at) VALUES (?,?,?,?,?)",
            ("Nguyễn A", "Cty ABC", "Giám đốc", "facebook", created_at),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_no_data_returns_zeros(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["total_contract_vnd"], 0)
        self.assertEqual(snap["active_lifecycles"], [])
        self.assertEqual(snap["open_issues"], 0)

    def test_customer_fields(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn, created_at="2024-01-15 00:00:00")
        snap = m.get_customer_snapshot(conn, cid)
        c = snap["customer"]
        self.assertEqual(c["name"], "Nguyễn A")
        self.assertEqual(c["company"], "Cty ABC")
        self.assertEqual(c["occupation"], "Giám đốc")
        self.assertIsInstance(c["months_as_customer"], int)
        self.assertGreaterEqual(c["months_as_customer"], 0)

    def test_total_contract_vnd(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_contracts (customer_id, amount_vnd, status) VALUES (?,?,?)", (cid, 10_000_000, "active"))
        conn.execute("INSERT INTO crm_contracts (customer_id, amount_vnd, status) VALUES (?,?,?)", (cid, 5_000_000, "active"))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["total_contract_vnd"], 15_000_000)

    def test_active_lifecycles_populated(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "onboarding", "active"))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(len(snap["active_lifecycles"]), 1)
        lc = snap["active_lifecycles"][0]
        self.assertEqual(lc["service_slug"], "seo")
        self.assertEqual(lc["stage"], "onboarding")

    def test_margin_pct_calculation(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "active", "active"))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, status) VALUES (?,?,?)", (lc_id, 10_000_000, "received"))
        conn.execute("INSERT INTO crm_svc_expenses (lifecycle_id, amount_vnd) VALUES (?,?)", (lc_id, 2_000_000))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        lc = snap["active_lifecycles"][0]
        self.assertAlmostEqual(lc["margin_pct"], 80.0, places=1)

    def test_outstanding_calculation(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_contracts (customer_id, amount_vnd, status) VALUES (?,?,?)", (cid, 20_000_000, "active"))
        conn.commit()
        ct_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status, contract_id) VALUES (?,?,?,?,?)", (cid, "seo", "active", "active", ct_id))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, status) VALUES (?,?,?)", (lc_id, 5_000_000, "received"))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        lc = snap["active_lifecycles"][0]
        self.assertEqual(lc["outstanding"], 15_000_000)

    def test_pending_tasks_count(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "active", "active"))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_tasks (lifecycle_id, is_done) VALUES (?,?)", (lc_id, 0))
        conn.execute("INSERT INTO crm_svc_tasks (lifecycle_id, is_done) VALUES (?,?)", (lc_id, 0))
        conn.execute("INSERT INTO crm_svc_tasks (lifecycle_id, is_done) VALUES (?,?)", (lc_id, 1))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["active_lifecycles"][0]["pending_tasks"], 2)

    def test_active_risks_count(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute("INSERT INTO crm_service_lifecycle (customer_id, service_slug, stage, status) VALUES (?,?,?,?)", (cid, "seo", "active", "active"))
        conn.commit()
        lc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO crm_svc_risks (lifecycle_id, is_active) VALUES (?,?)", (lc_id, 1))
        conn.execute("INSERT INTO crm_svc_risks (lifecycle_id, is_active) VALUES (?,?)", (lc_id, 0))
        conn.commit()
        snap = m.get_customer_snapshot(conn, cid)
        self.assertEqual(snap["active_lifecycles"][0]["active_risks"], 1)


class TestGetLatestBrief(unittest.TestCase):
    def _seed_customer(self, conn):
        conn.execute("INSERT INTO crm_customers (name) VALUES (?)", ("Test",))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_no_brief_returns_none(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        self.assertIsNone(m.get_latest_brief(conn, cid))

    def test_returns_latest_by_id_desc(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        conn.execute(
            "INSERT INTO crm_customer_brief_scans (customer_id, meeting_purpose, ai_output, created_at) VALUES (?,?,?,?)",
            (cid, "first", "output1", "2026-01-01 00:00:00"),
        )
        conn.execute(
            "INSERT INTO crm_customer_brief_scans (customer_id, meeting_purpose, ai_output, created_at) VALUES (?,?,?,?)",
            (cid, "second", "output2", "2026-01-02 00:00:00"),
        )
        conn.commit()
        brief = m.get_latest_brief(conn, cid)
        self.assertIsNotNone(brief)
        self.assertEqual(brief["meeting_purpose"], "second")
        self.assertEqual(brief["ai_output"], "output2")


class TestRunBriefAi(unittest.TestCase):
    def _seed_customer(self, conn):
        conn.execute("INSERT INTO crm_customers (name) VALUES (?)", ("Test",))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        snap = {"customer": {"name": "Test", "company": "", "occupation": "", "months_as_customer": 1}, "total_contract_vnd": 0, "active_lifecycles": [], "open_issues": 0}
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.side_effect = Exception("no key")
            result = m.run_brief_ai(conn, cid, "", snap)
        self.assertEqual(result, "")

    def test_saves_to_scans_on_success(self):
        conn = _setup_conn()
        cid = self._seed_customer(conn)
        snap = {"customer": {"name": "Test", "company": "", "occupation": "", "months_as_customer": 1}, "total_contract_vnd": 0, "active_lifecycles": [], "open_issues": 0}
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="## Tóm tắt\nTest")]
        with patch("anthropic.Anthropic") as mock_cls:
            mock_cls.return_value.messages.create.return_value = mock_resp
            result = m.run_brief_ai(conn, cid, "upsell", snap)
        self.assertIn("Tóm tắt", result)
        row = conn.execute("SELECT * FROM crm_customer_brief_scans WHERE customer_id = ?", (cid,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["meeting_purpose"], "upsell")


if __name__ == "__main__":
    unittest.main()
