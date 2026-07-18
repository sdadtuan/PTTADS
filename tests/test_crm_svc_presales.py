"""Tests cho crm_svc_presales — Phase L1 pre-sales cost summary."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_finance import (
    ExpenseValidationError,
    create_expense,
    ensure_schema,
)
from crm_svc_presales import (
    PRESALES_CATEGORY_LABELS,
    get_presales_cost_summary,
    show_presales_panel,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            service_slug TEXT NOT NULL DEFAULT 'dich-vu-aeo',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (id, stage, status, created_at, updated_at)
        VALUES (1, 'lead', 'draft', '2026-06-01', '2026-06-01'),
               (2, 'onboard', 'active', '2026-06-01', '2026-06-01')
        """
    )
    conn.commit()
    ensure_schema(conn)
    return conn


class TestPresalesSummary(unittest.TestCase):
    def test_empty_summary(self):
        conn = _setup_conn()
        s = get_presales_cost_summary(conn, 1)
        self.assertEqual(s["total_presales_vnd"], 0)
        self.assertEqual(s["expense_count"], 0)
        self.assertEqual(s["by_category"], [])

    def test_aggregates_presales_only(self):
        conn = _setup_conn()
        create_expense(
            conn,
            1,
            "Gọi lead",
            "dien_thoai",
            150_000,
            "2026-06-02",
            cost_phase="presales",
            lifecycle_stage="lead",
        )
        create_expense(conn, 2, "Triển khai", "nhan-cong", 5_000_000, "2026-06-10")
        s = get_presales_cost_summary(conn, 1)
        self.assertEqual(s["total_presales_vnd"], 150_000)
        self.assertEqual(s["expense_count"], 1)
        self.assertEqual(len(s["by_category"]), 1)
        self.assertEqual(s["by_category"][0]["category"], "dien_thoai")
        self.assertEqual(
            s["by_category"][0]["label"],
            PRESALES_CATEGORY_LABELS["dien_thoai"],
        )

    def test_rejects_presales_on_onboard_lifecycle(self):
        conn = _setup_conn()
        with self.assertRaises(ExpenseValidationError):
            create_expense(
                conn,
                2,
                "Không hợp lệ",
                "dien_thoai",
                100_000,
                "2026-06-02",
                cost_phase="presales",
                lifecycle_stage="onboard",
            )


class TestShowPresalesPanel(unittest.TestCase):
    def test_draft_lead(self):
        self.assertTrue(show_presales_panel({"status": "draft", "stage": "lead"}))

    def test_active_onboard_hidden(self):
        self.assertFalse(show_presales_panel({"status": "active", "stage": "onboard"}))

    def test_consult_draft(self):
        self.assertTrue(show_presales_panel({"status": "draft", "stage": "consult"}))


if __name__ == "__main__":
    unittest.main()
