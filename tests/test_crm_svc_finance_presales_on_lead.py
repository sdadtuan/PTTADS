"""Tests L3.2 — chi phí pre-sales gắn lead/presales (không cần lifecycle)."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_lead_presales import ensure_presales, ensure_schema as presales_schema
from crm_lead_presales import promote_presales_to_lifecycle
from crm_svc_finance import (
    COST_PHASE_PRESALES,
    ExpenseValidationError,
    create_presales_expense,
    ensure_schema as finance_schema,
    get_summary,
    link_presales_expenses_to_lifecycle,
    list_presales_expenses,
)
from crm_svc_presales import get_am_lead_metrics, get_presales_cost_summary_by_presales


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO crm_staff (id, name) VALUES (1, 'AM One');

        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            owner_id INTEGER,
            care_stage_current TEXT NOT NULL DEFAULT 'first_contact',
            care_stages_done_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '2026-06-01 08:00:00'
        );
        INSERT INTO crm_leads (id, full_name, owner_id, care_stage_current, care_stages_done_json)
        VALUES (10, 'Lead A', 1, 'first_contact', '{"first_contact":"2026-06-01 11:00:00"}');

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            customer_id INTEGER,
            contract_id INTEGER,
            service_slug TEXT,
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            assigned_am INTEGER,
            stage_entered_at TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE crm_service_lifecycle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER,
            from_stage TEXT,
            to_stage TEXT,
            actor_type TEXT,
            notes TEXT,
            created_at TEXT
        );

        CREATE TABLE crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER,
            stage TEXT,
            step_index INTEGER,
            title TEXT,
            description TEXT,
            form_fields TEXT,
            form_data TEXT,
            ai_output TEXT,
            ai_prompt_key TEXT,
            is_done INTEGER,
            done_at TEXT,
            done_by INTEGER,
            notes TEXT,
            is_custom INTEGER,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE crm_lead_intake_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            lifecycle_id INTEGER,
            service_slug TEXT,
            mode TEXT,
            status TEXT,
            decision TEXT,
            started_at TEXT,
            completed_at TEXT
        );
        """
    )
    presales_schema(conn)
    finance_schema(conn)
    ensure_presales(conn, 10, "dich-vu-aeo", suggested_by="test")
    conn.commit()
    return conn


class TestPresalesExpenseOnLead(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.get("PTT_PRESALES_ON_LEAD")
        os.environ["PTT_PRESALES_ON_LEAD"] = "1"

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop("PTT_PRESALES_ON_LEAD", None)
        else:
            os.environ["PTT_PRESALES_ON_LEAD"] = self._env

    def test_migration_adds_lead_presales_columns(self) -> None:
        conn = _setup_conn()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_svc_expenses)").fetchall()}
        self.assertIn("lead_id", cols)
        self.assertIn("presales_id", cols)

    def test_create_presales_expense_without_lifecycle(self) -> None:
        conn = _setup_conn()
        ps = conn.execute("SELECT id FROM crm_lead_presales WHERE lead_id = 10").fetchone()
        eid = create_presales_expense(
            conn,
            lead_id=10,
            title="Gọi qualify",
            category="dien_thoai",
            amount_vnd=150_000,
            expense_on="2026-06-03",
        )
        row = conn.execute(
            "SELECT lifecycle_id, lead_id, presales_id, cost_phase FROM crm_svc_expenses WHERE id = ?",
            (eid,),
        ).fetchone()
        self.assertIsNone(row["lifecycle_id"])
        self.assertEqual(int(row["lead_id"]), 10)
        self.assertEqual(int(row["presales_id"]), int(ps["id"]))
        self.assertEqual(row["cost_phase"], COST_PHASE_PRESALES)

    def test_summary_by_presales(self) -> None:
        conn = _setup_conn()
        ps_id = int(conn.execute("SELECT id FROM crm_lead_presales WHERE lead_id = 10").fetchone()[0])
        create_presales_expense(
            conn,
            presales_id=ps_id,
            title="Grab gặp KH",
            category="di_lai",
            amount_vnd=80_000,
            expense_on="2026-06-04",
        )
        summary = get_presales_cost_summary_by_presales(conn, ps_id)
        self.assertEqual(summary["total_presales_vnd"], 80_000)
        self.assertEqual(summary["expense_count"], 1)

    def test_blocked_when_presales_converted(self) -> None:
        conn = _setup_conn()
        ps_id = int(conn.execute("SELECT id FROM crm_lead_presales WHERE lead_id = 10").fetchone()[0])
        conn.execute(
            "UPDATE crm_lead_presales SET status = 'converted' WHERE id = ?", (ps_id,)
        )
        conn.commit()
        with self.assertRaises(ExpenseValidationError):
            create_presales_expense(
                conn,
                presales_id=ps_id,
                title="Late expense",
                category="dien_thoai",
                amount_vnd=10_000,
                expense_on="2026-06-05",
            )

    def test_promote_links_expenses_to_lifecycle(self) -> None:
        conn = _setup_conn()
        from crm_svc_tasks import ensure_schema as task_schema
        from crm_lead_presales import list_presales_tasks, update_presales_task

        task_schema(conn)
        ps_id = int(conn.execute("SELECT id FROM crm_lead_presales WHERE lead_id = 10").fetchone()[0])
        for stage_tasks in list_presales_tasks(conn, ps_id).values():
            for task in stage_tasks:
                update_presales_task(conn, int(task["id"]), is_done=True)
        from crm_lead_presales_marketing_plan import ensure_r5_schema, update_preliminary_plan

        ensure_r5_schema(conn)
        update_preliminary_plan(
            conn,
            ps_id,
            {
                "name": "Plan promote",
                "north_star": "NS",
                "strategy_framework": {
                    "market_message": "m",
                    "media_reach": "r",
                    "conversion_strategy": "c",
                },
            },
        )
        conn.execute("UPDATE crm_lead_presales SET stage = 'proposal' WHERE id = ?", (ps_id,))
        conn.commit()
        create_presales_expense(
            conn,
            presales_id=ps_id,
            title="Gọi",
            category="dien_thoai",
            amount_vnd=100_000,
            expense_on="2026-06-03",
        )
        lc_id = promote_presales_to_lifecycle(
            conn, ps_id, customer_id=1, contract_id=99, actor="test"
        )
        rows = list_presales_expenses(conn, ps_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(int(rows[0]["lifecycle_id"]), lc_id)
        s = get_summary(conn, lc_id, 5_000_000)
        self.assertEqual(s["presales_expenses"], 100_000)

    def test_am_lead_metrics_counts_presales_cost_on_lead(self) -> None:
        conn = _setup_conn()
        create_presales_expense(
            conn,
            lead_id=10,
            title="SIM",
            category="dien_thoai",
            amount_vnd=200_000,
            expense_on="2026-06-05",
        )
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertEqual(m["presales_cost_vnd"], 200_000)


if __name__ == "__main__":
    unittest.main()
