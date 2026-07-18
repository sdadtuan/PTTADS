# tests/test_crm_svc_risk.py
"""Tests cho crm_svc_risk module."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_risk import (
    create_custom_risk,
    delete_risk,
    ensure_schema,
    get_latest_scan,
    list_risks,
    seed_risks,
    update_risk,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'active',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (1, 'dich-vu-seo-tong-the', 'deliver', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_risks", tables)
        self.assertIn("crm_svc_risk_scans", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)
        ensure_schema(conn)


class TestSeedRisks(unittest.TestCase):
    def test_seeds_correct_count(self):
        conn = _setup_conn()
        count = seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count, 0)
        db_count = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_risks WHERE lifecycle_id = 1"
        ).fetchone()[0]
        self.assertEqual(db_count, count)

    def test_idempotent(self):
        conn = _setup_conn()
        count1 = seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        count2 = seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count1, 0)
        self.assertEqual(count2, 0)

    def test_unknown_slug_returns_zero(self):
        conn = _setup_conn()
        self.assertEqual(seed_risks(conn, lifecycle_id=1, service_slug="nonexistent"), 0)

    def test_seeded_risks_are_active(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rows = conn.execute(
            "SELECT is_active FROM crm_svc_risks WHERE lifecycle_id = 1"
        ).fetchall()
        self.assertTrue(all(r["is_active"] == 1 for r in rows))

    def test_seeded_are_not_custom(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rows = conn.execute(
            "SELECT is_custom FROM crm_svc_risks WHERE lifecycle_id = 1"
        ).fetchall()
        self.assertTrue(all(r["is_custom"] == 0 for r in rows))


class TestListRisks(unittest.TestCase):
    def test_returns_list(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        risks = list_risks(conn, lifecycle_id=1)
        self.assertIsInstance(risks, list)
        self.assertGreater(len(risks), 0)

    def test_empty_lifecycle_returns_empty(self):
        conn = _setup_conn()
        self.assertEqual(list_risks(conn, lifecycle_id=999), [])

    def test_risk_has_required_fields(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        risk = list_risks(conn, lifecycle_id=1)[0]
        for field in ["id", "lifecycle_id", "stage", "title", "category",
                      "probability", "impact", "mitigation", "is_active", "is_custom"]:
            self.assertIn(field, risk, f"Missing field: {field}")

    def test_active_risks_listed_first(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        first_id = conn.execute(
            "SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()["id"]
        update_risk(conn, first_id, is_active=False)
        risks = list_risks(conn, lifecycle_id=1)
        active_statuses = [r["is_active"] for r in risks]
        self.assertEqual(active_statuses, sorted(active_statuses, reverse=True))


class TestUpdateRisk(unittest.TestCase):
    def test_update_probability(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute("SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1").fetchone()["id"]
        update_risk(conn, rid, probability="thap")
        row = conn.execute("SELECT probability FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        self.assertEqual(row["probability"], "thap")

    def test_update_impact(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute("SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1").fetchone()["id"]
        update_risk(conn, rid, impact="thap")
        row = conn.execute("SELECT impact FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        self.assertEqual(row["impact"], "thap")

    def test_resolve_risk(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute("SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1").fetchone()["id"]
        update_risk(conn, rid, is_active=False)
        row = conn.execute("SELECT is_active FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        self.assertEqual(row["is_active"], 0)

    def test_reactivate_risk(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute("SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1").fetchone()["id"]
        update_risk(conn, rid, is_active=False)
        update_risk(conn, rid, is_active=True)
        row = conn.execute("SELECT is_active FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        self.assertEqual(row["is_active"], 1)

    def test_update_mitigation(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute("SELECT id FROM crm_svc_risks WHERE lifecycle_id = 1 LIMIT 1").fetchone()["id"]
        update_risk(conn, rid, mitigation="Plan B mới")
        row = conn.execute("SELECT mitigation FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        self.assertEqual(row["mitigation"], "Plan B mới")


class TestCustomRisk(unittest.TestCase):
    def test_create_custom_risk(self):
        conn = _setup_conn()
        rid = create_custom_risk(
            conn, lifecycle_id=1, stage="deliver", title="Rủi ro tuỳ chỉnh"
        )
        self.assertIsInstance(rid, int)
        row = conn.execute("SELECT * FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        self.assertEqual(row["is_custom"], 1)
        self.assertEqual(row["title"], "Rủi ro tuỳ chỉnh")
        self.assertEqual(row["is_active"], 1)
        self.assertEqual(row["probability"], "trung")
        self.assertEqual(row["impact"], "trung")

    def test_delete_custom_risk(self):
        conn = _setup_conn()
        rid = create_custom_risk(
            conn, lifecycle_id=1, stage="deliver", title="Xoá đi"
        )
        self.assertTrue(delete_risk(conn, rid))
        self.assertIsNone(
            conn.execute("SELECT id FROM crm_svc_risks WHERE id = ?", (rid,)).fetchone()
        )

    def test_cannot_delete_template_risk(self):
        conn = _setup_conn()
        seed_risks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        rid = conn.execute(
            "SELECT id FROM crm_svc_risks WHERE is_custom = 0 LIMIT 1"
        ).fetchone()["id"]
        self.assertFalse(delete_risk(conn, rid))

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        self.assertFalse(delete_risk(conn, 99999))


class TestGetLatestScan(unittest.TestCase):
    def test_no_scan_returns_empty_string(self):
        conn = _setup_conn()
        self.assertEqual(get_latest_scan(conn, lifecycle_id=1), "")

    def test_returns_latest_not_first(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_risk_scans (lifecycle_id, ai_output, created_at) "
            "VALUES (1, 'scan cũ', '2026-06-23 08:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_risk_scans (lifecycle_id, ai_output, created_at) "
            "VALUES (1, 'scan mới nhất', '2026-06-23 09:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_scan(conn, lifecycle_id=1), "scan mới nhất")


if __name__ == "__main__":
    unittest.main()
