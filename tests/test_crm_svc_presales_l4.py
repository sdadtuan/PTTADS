"""Tests L4 — presales cap alert + AI lead scan."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_finance import create_expense, ensure_schema as finance_schema
from crm_svc_kpi import run_ai_lead_kpi_scan
from crm_svc_presales import (
    get_presales_cap_alert,
    get_presales_cost_cap,
    get_presales_cost_summary,
    merge_lifecycle_meta,
    parse_lifecycle_meta,
    set_presales_cost_cap,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle (id, stage, status, notes)
        VALUES (1, 'lead', 'draft', 'Ghi chú AM thường')
        """
    )
    conn.execute("""
        CREATE TABLE crm_svc_kpi_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            ai_output TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'am',
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    finance_schema(conn)
    conn.commit()
    return conn


class TestLifecycleMeta(unittest.TestCase):
    def test_parse_and_merge_preserves_notes(self):
        notes = merge_lifecycle_meta("Ghi chú AM", {"presales_cost_cap_vnd": 3_000_000})
        self.assertTrue(notes.startswith("Ghi chú AM"))
        meta = parse_lifecycle_meta(notes)
        self.assertEqual(meta["presales_cost_cap_vnd"], 3_000_000)

    def test_parse_meta_with_trailing_text_after_marker(self) -> None:
        notes = (
            '\n<!--ptt:{"presales_cost_cap_vnd":2000000}-->\n'
            "→ Lifecycle #1 (Onboard)"
        )
        meta = parse_lifecycle_meta(notes)
        self.assertEqual(meta["presales_cost_cap_vnd"], 2_000_000)


class TestPresalesCapAlert(unittest.TestCase):
    def setUp(self) -> None:
        self._cap_env = os.environ.get("PTT_PRESALES_COST_CAP_VND")
        self._strict_env = os.environ.get("PTT_PRESALES_CAP_STRICT")
        os.environ.pop("PTT_PRESALES_COST_CAP_VND", None)
        os.environ.pop("PTT_PRESALES_CAP_STRICT", None)

    def tearDown(self) -> None:
        if self._cap_env is None:
            os.environ.pop("PTT_PRESALES_COST_CAP_VND", None)
        else:
            os.environ["PTT_PRESALES_COST_CAP_VND"] = self._cap_env
        if self._strict_env is None:
            os.environ.pop("PTT_PRESALES_CAP_STRICT", None)
        else:
            os.environ["PTT_PRESALES_CAP_STRICT"] = self._strict_env

    def test_no_cap_no_alert(self):
        conn = _setup_conn()
        alert = get_presales_cap_alert(conn, 1)
        self.assertFalse(alert["over_cap"])
        self.assertIsNone(alert["presales_cost_cap_vnd"])

    def test_over_cap_when_expenses_exceed(self):
        conn = _setup_conn()
        set_presales_cost_cap(conn, 1, 100_000)
        create_expense(
            conn, 1, "Gọi", "dien_thoai", 150_000, "2026-06-02",
            cost_phase="presales", lifecycle_stage="lead",
        )
        alert = get_presales_cap_alert(conn, 1)
        self.assertTrue(alert["over_cap"])
        self.assertIn("vượt cap", alert["cap_alert_message"].lower())

    def test_summary_includes_cap_fields(self):
        conn = _setup_conn()
        set_presales_cost_cap(conn, 1, 500_000)
        summary = get_presales_cost_summary(conn, 1)
        self.assertEqual(summary["presales_cost_cap_vnd"], 500_000)
        self.assertFalse(summary["over_cap"])

    def test_get_and_clear_cap(self):
        conn = _setup_conn()
        set_presales_cost_cap(conn, 1, 200_000)
        self.assertEqual(get_presales_cost_cap(conn, 1), 200_000)
        set_presales_cost_cap(conn, 1, None)
        self.assertIsNone(get_presales_cost_cap(conn, 1))


class TestRunAiLeadKpiScan(unittest.TestCase):
    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_ai_lead_kpi_scan(
            conn,
            staff_id=1,
            year=2026,
            month=6,
            context={
                "staff_name": "AM Test",
                "month": 6,
                "year": 2026,
                "lead_intake_completed": 2,
                "lead_phone_within_48h_pct": 50.0,
                "lead_phone_within_48h_num": 1,
                "lead_phone_within_48h_denom": 2,
                "lead_go_decisions": 1,
                "lead_to_consult_pct": 100.0,
                "lead_to_consult_num": 1,
                "lead_to_consult_denom": 1,
                "presales_cost_vnd": 200_000,
                "presales_cost_per_go_vnd": 200_000,
                "lead_avg_phone_minutes": 18.0,
                "target_lead_intake_completed": 3,
                "target_lead_phone_within_48h_pct": 80.0,
                "target_lead_to_consult_pct": 70.0,
                "target_presales_cost_vnd": 500_000,
                "presales_over_cap_count": 0,
            },
        )
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
