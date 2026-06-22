# tests/test_crm_service_lifecycle.py
"""Tests cho crm_service_lifecycle module."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timedelta

from crm_service_lifecycle import (
    VALID_STAGES,
    VALID_STATUSES,
    activate_lifecycle,
    advance_stage,
    create_draft_lifecycle,
    ensure_schema,
    get_by_contract,
    get_by_lead,
    get_stage_context,
    list_active,
)

TS = "2026-06-22 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    # Seed bảng phụ tối thiểu
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crm_leads (id INTEGER PRIMARY KEY, meta_json TEXT DEFAULT '{}')"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '')"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS crm_contracts (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            service_slug TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft'
        )"""
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)"
    )
    conn.execute("INSERT INTO crm_leads (id) VALUES (1)")
    conn.execute("INSERT INTO crm_customers (id, name) VALUES (1, 'Test Co')")
    conn.execute(
        "INSERT INTO crm_contracts (id, customer_id, service_slug, status) VALUES (1, 1, 'dich-vu-seo-tong-the', 'draft')"
    )
    conn.commit()
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("crm_service_lifecycle", tables)
        self.assertIn("crm_service_lifecycle_events", tables)

    def test_contracts_has_service_slug(self):
        conn = _setup_conn()
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()
        }
        self.assertIn("service_slug", cols)


class TestCreateDraftLifecycle(unittest.TestCase):
    def test_creates_draft_record(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertIsInstance(lid, int)
        row = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["status"], "draft")
        self.assertEqual(row["stage"], "lead")
        self.assertEqual(row["service_slug"], "dich-vu-seo-tong-the")
        self.assertEqual(row["lead_id"], 1)

    def test_records_initial_event(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        events = conn.execute(
            "SELECT * FROM crm_service_lifecycle_events WHERE lifecycle_id = ?", (lid,)
        ).fetchall()
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0]["from_stage"])
        self.assertEqual(events[0]["to_stage"], "lead")


class TestActivateLifecycle(unittest.TestCase):
    def test_activates_draft_and_sets_onboard(self):
        conn = _setup_conn()
        # Tạo lifecycle gắn với customer_id=1
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id = 1 WHERE id = ?", (lid,)
        )
        conn.commit()
        # Contract customer_id=1 → activate
        ok = activate_lifecycle(conn, contract_id=1)
        self.assertTrue(ok)
        row = conn.execute(
            "SELECT * FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["stage"], "onboard")
        self.assertEqual(row["contract_id"], 1)

    def test_returns_false_when_no_draft_found(self):
        conn = _setup_conn()
        ok = activate_lifecycle(conn, contract_id=1)
        self.assertFalse(ok)


class TestAdvanceStage(unittest.TestCase):
    def test_advances_stage_and_logs_event(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        advance_stage(conn, lid, "consult", actor_type="human")
        row = conn.execute(
            "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["stage"], "consult")
        events = conn.execute(
            "SELECT * FROM crm_service_lifecycle_events WHERE lifecycle_id = ? ORDER BY id",
            (lid,),
        ).fetchall()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["from_stage"], "lead")
        self.assertEqual(events[1]["to_stage"], "consult")
        self.assertEqual(events[1]["actor_type"], "human")


class TestGetters(unittest.TestCase):
    def test_get_by_lead(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="tiep-thi-noi-dung")
        row = get_by_lead(conn, lead_id=1)
        self.assertIsNotNone(row)
        self.assertEqual(row["service_slug"], "tiep-thi-noi-dung")

    def test_get_by_contract(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="quang-cao-google")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id = 1, contract_id = 1 WHERE id = ?",
            (lid,),
        )
        conn.commit()
        row = get_by_contract(conn, contract_id=1)
        self.assertIsNotNone(row)

    def test_get_stage_context_returns_days(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-local")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id = 1, status = 'active' WHERE id = ?",
            (lid,),
        )
        conn.commit()
        ctx = get_stage_context(conn, customer_id=1)
        self.assertIsNotNone(ctx)
        self.assertIn("stage", ctx)
        self.assertIn("stage_days", ctx)
        self.assertIn("service_slug", ctx)

    def test_get_by_lead_none_when_missing(self):
        conn = _setup_conn()
        self.assertIsNone(get_by_lead(conn, lead_id=999))


class TestListActive(unittest.TestCase):
    def test_excludes_draft_by_default(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        results = list_active(conn)
        self.assertEqual(len(results), 0)

    def test_includes_draft_when_requested(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        results = list_active(conn, include_draft=True)
        self.assertEqual(len(results), 1)

    def test_filters_by_service_slug(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        conn.execute(
            "UPDATE crm_service_lifecycle SET status = 'active' WHERE id = ?", (lid,)
        )
        conn.commit()
        results = list_active(conn, service_slug="dich-vu-aeo")
        self.assertEqual(len(results), 1)
        results_none = list_active(conn, service_slug="quang-cao-google")
        self.assertEqual(len(results_none), 0)


class TestKpiAlertAsync(unittest.TestCase):
    def test_check_kpi_alert_async_does_not_raise(self):
        """check_kpi_alert_async không raise dù không có API key."""
        import tempfile
        import os
        from crm_service_lifecycle import check_kpi_alert_async
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            ensure_schema(conn)
            conn.execute("CREATE TABLE IF NOT EXISTS crm_leads (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE IF NOT EXISTS crm_customers (id INTEGER PRIMARY KEY)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS crm_contracts (id INTEGER PRIMARY KEY, customer_id INTEGER, service_slug TEXT DEFAULT '', status TEXT DEFAULT 'draft')"
            )
            conn.execute("CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)")
            lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
            conn.close()
            t = check_kpi_alert_async(lifecycle_id=lid, db_path=db_path)
            t.join(timeout=3)
        finally:
            os.unlink(db_path)


class TestMigrationContractsColumn(unittest.TestCase):
    def test_service_slug_added_idempotent(self):
        """ensure_schema chạy 2 lần không lỗi."""
        conn = _setup_conn()
        ensure_schema(conn)  # lần 2 — không được raise
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()
        }
        self.assertIn("service_slug", cols)


class TestStageContextForCare(unittest.TestCase):
    def test_active_lifecycle_returns_context(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="quang-cao-facebook")
        conn.execute(
            "UPDATE crm_service_lifecycle SET customer_id=1, status='active', stage='deliver' WHERE id=?",
            (lid,),
        )
        conn.commit()
        ctx = get_stage_context(conn, customer_id=1)
        self.assertEqual(ctx["service_slug"], "quang-cao-facebook")
        self.assertEqual(ctx["stage"], "deliver")
        self.assertGreaterEqual(ctx["stage_days"], 0)

    def test_no_active_lifecycle_returns_none(self):
        conn = _setup_conn()
        self.assertIsNone(get_stage_context(conn, customer_id=999))


if __name__ == "__main__":
    unittest.main()
