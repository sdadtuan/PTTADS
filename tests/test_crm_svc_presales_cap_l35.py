"""Tests L3.5 — cap pre-sales thống nhất lead/lifecycle + promote sync."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_lead_presales import ensure_schema as presales_schema
from crm_lead_presales import promote_presales_to_lifecycle
from crm_svc_finance import (
    ExpenseValidationError,
    create_presales_expense,
    ensure_schema as finance_schema,
)
from crm_svc_presales import (
    PresalesCapExceededError,
    get_presales_cap_alert,
    get_presales_cap_alert_for_presales,
    get_presales_cost_cap,
    get_presales_cost_summary_by_presales,
    resolve_presales_cost_cap,
    set_presales_cost_cap_for_presales,
    transfer_presales_cap_to_lifecycle,
)


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
        INSERT INTO crm_leads (id, full_name, owner_id) VALUES (10, 'Lead A', 1);

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
            notes TEXT NOT NULL DEFAULT '',
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
        """
    )
    presales_schema(conn)
    finance_schema(conn)
    intake_schema(conn)
    conn.execute(
        """
        INSERT INTO crm_lead_presales
            (id, lead_id, service_slug, stage, status, assigned_am,
             lifecycle_id, stage_entered_at, notes, created_at, updated_at)
        VALUES
            (1, 10, 'dich-vu-aeo', 'proposal', 'active', 1,
             NULL, '2026-06-08', '', '2026-06-02', '2026-06-08')
        """
    )
    conn.commit()
    return conn


class TestPresalesCapL35(unittest.TestCase):
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

    def test_cap_on_presales_summary_and_alert(self) -> None:
        conn = _setup_conn()
        set_presales_cost_cap_for_presales(conn, 1, 500_000)
        create_presales_expense(
            conn,
            lead_id=10,
            title="Gọi",
            category="dien_thoai",
            amount_vnd=600_000,
            expense_on="2026-06-03",
        )
        summary = get_presales_cost_summary_by_presales(conn, 1)
        self.assertEqual(summary["presales_cost_cap_vnd"], 500_000)
        self.assertTrue(summary["over_cap"])
        self.assertEqual(summary["cap_source"], "presales")
        self.assertEqual(summary["cap_remaining_vnd"], 0)
        self.assertEqual(summary["cap_utilization_pct"], 120.0)

    def test_lifecycle_fallback_to_presales_cap(self) -> None:
        conn = _setup_conn()
        set_presales_cost_cap_for_presales(conn, 1, 300_000)
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, lead_id, service_slug, stage, status, notes, created_at, updated_at)
            VALUES (50, 10, 'dich-vu-aeo', 'lead', 'draft', 'Draft LC', '2026-06-01', '2026-06-01')
            """
        )
        conn.commit()
        cap, source = resolve_presales_cost_cap(conn, lifecycle_id=50)
        self.assertEqual(cap, 300_000)
        self.assertEqual(source, "presales")
        alert = get_presales_cap_alert(conn, 50)
        self.assertEqual(alert["presales_cost_cap_vnd"], 300_000)
        self.assertEqual(alert["cap_source"], "presales")

    def test_transfer_cap_on_promote(self) -> None:
        conn = _setup_conn()
        from crm_svc_tasks import ensure_schema as task_schema
        from crm_lead_presales import list_presales_tasks, update_presales_task

        task_schema(conn)
        set_presales_cost_cap_for_presales(conn, 1, 2_000_000)
        for stage_tasks in list_presales_tasks(conn, 1).values():
            for task in stage_tasks:
                update_presales_task(conn, int(task["id"]), is_done=True)
        from crm_lead_presales_marketing_plan import ensure_r5_schema, update_preliminary_plan

        ensure_r5_schema(conn)
        update_preliminary_plan(
            conn,
            1,
            {
                "name": "Plan",
                "north_star": "NS",
                "strategy_framework": {
                    "market_message": "m",
                    "media_reach": "r",
                    "conversion_strategy": "c",
                },
            },
        )
        conn.commit()
        lc_id = promote_presales_to_lifecycle(
            conn, 1, customer_id=1, contract_id=99, actor="test"
        )
        self.assertEqual(get_presales_cost_cap(conn, lc_id), 2_000_000)
        cap, source = resolve_presales_cost_cap(conn, lifecycle_id=lc_id)
        self.assertEqual(cap, 2_000_000)
        self.assertEqual(source, "lifecycle")

    def test_transfer_presales_cap_helper(self) -> None:
        conn = _setup_conn()
        set_presales_cost_cap_for_presales(conn, 1, 800_000)
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, lead_id, service_slug, stage, status, notes, created_at, updated_at)
            VALUES (60, 10, 'dich-vu-aeo', 'onboard', 'active', 'Promoted', '2026-06-10', '2026-06-10')
            """
        )
        conn.execute(
            "UPDATE crm_lead_presales SET lifecycle_id = 60, status = 'converted' WHERE id = 1"
        )
        conn.commit()
        copied = transfer_presales_cap_to_lifecycle(conn, 1, 60)
        self.assertEqual(copied, 800_000)

    def test_default_env_cap_when_no_explicit(self) -> None:
        os.environ["PTT_PRESALES_COST_CAP_VND"] = "1500000"
        conn = _setup_conn()
        cap, source = resolve_presales_cost_cap(conn, presales_id=1)
        self.assertEqual(cap, 1_500_000)
        self.assertEqual(source, "default")

    def test_strict_blocks_expense_over_cap(self) -> None:
        os.environ["PTT_PRESALES_CAP_STRICT"] = "1"
        conn = _setup_conn()
        set_presales_cost_cap_for_presales(conn, 1, 100_000)
        create_presales_expense(
            conn,
            lead_id=10,
            title="OK",
            category="dien_thoai",
            amount_vnd=50_000,
            expense_on="2026-06-03",
        )
        with self.assertRaises(PresalesCapExceededError):
            create_presales_expense(
                conn,
                lead_id=10,
                title="Over",
                category="dien_thoai",
                amount_vnd=60_000,
                expense_on="2026-06-04",
            )

    def test_non_strict_allows_over_cap(self) -> None:
        conn = _setup_conn()
        set_presales_cost_cap_for_presales(conn, 1, 100_000)
        create_presales_expense(
            conn,
            lead_id=10,
            title="Over",
            category="dien_thoai",
            amount_vnd=150_000,
            expense_on="2026-06-03",
        )
        alert = get_presales_cap_alert_for_presales(conn, 1)
        self.assertTrue(alert["over_cap"])


if __name__ == "__main__":
    unittest.main()
