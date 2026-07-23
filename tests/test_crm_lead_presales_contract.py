"""Tests: HĐ draft + ký HĐ → lifecycle (Phương án A P3)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class LeadPresalesContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE crm_leads (
                id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                email TEXT,
                owner_id INTEGER,
                source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'qualified',
                need TEXT,
                product_interest TEXT,
                lead_score INTEGER DEFAULT 0,
                lead_level TEXT DEFAULT 'warm',
                converted_customer_id INTEGER,
                converted_case_id INTEGER,
                updated_at TEXT,
                updated_by TEXT,
                meta_json TEXT DEFAULT '{}',
                re_project_id INTEGER,
                re_product_id INTEGER,
                care_stage_current TEXT DEFAULT 'advise',
                care_stages_done_json TEXT DEFAULT '{"intake":"2026-01-01","first_contact":"2026-01-01","qualify":"2026-01-01"}'
            );
            INSERT INTO crm_leads (id, full_name, phone, email, owner_id)
            VALUES (1, 'Nguyễn Test', '0901234567', 'a@test.com', 5);

            CREATE TABLE crm_re_projects (
                id INTEGER PRIMARY KEY, name TEXT, code TEXT
            );
            CREATE TABLE crm_re_project_products (
                id INTEGER PRIMARY KEY,
                unit_code TEXT,
                zone TEXT,
                product_line TEXT,
                status TEXT
            );
            CREATE TABLE crm_lead_assignment_logs (
                id INTEGER PRIMARY KEY,
                lead_id INTEGER,
                to_user_id INTEGER,
                created_at TEXT
            );

            CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1, internal_code TEXT DEFAULT '', email TEXT DEFAULT '', phone TEXT DEFAULT '');
            INSERT INTO crm_staff (id, name) VALUES (5, 'AM Test');

            CREATE TABLE crm_customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                company TEXT DEFAULT '',
                created_at TEXT,
                is_placeholder INTEGER DEFAULT 0,
                placeholder_lead_id INTEGER
            );

            CREATE TABLE crm_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                title TEXT,
                description TEXT DEFAULT '',
                channel TEXT DEFAULT 'khac',
                priority TEXT DEFAULT 'binh_thuong',
                status TEXT DEFAULT 'tiep_nhan',
                assigned_to TEXT DEFAULT '',
                assigned_staff_id INTEGER,
                assigned_at TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT,
                pipeline_stage TEXT DEFAULT 'moi',
                stage_entered_at TEXT DEFAULT '',
                lead_source TEXT DEFAULT ''
            );

            CREATE TABLE crm_case_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                kind TEXT DEFAULT 'ghi_chu',
                body TEXT,
                created_at TEXT
            );

            CREATE TABLE crm_lead_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                activity_type TEXT,
                content TEXT,
                result TEXT,
                next_action TEXT,
                next_action_at TEXT,
                created_at TEXT,
                created_by TEXT,
                user_id INTEGER
            );

            CREATE TABLE crm_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL,
                ref_id INTEGER NOT NULL DEFAULT 0,
                reminder_kind TEXT NOT NULL DEFAULT 'manual',
                title TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                remind_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                staff_id INTEGER,
                meta_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE crm_service_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                customer_id INTEGER,
                contract_id INTEGER,
                service_slug TEXT,
                stage TEXT,
                status TEXT,
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
                bant_total INTEGER DEFAULT 0,
                decision TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                completed_at TEXT DEFAULT '',
                bant_json TEXT DEFAULT '{}',
                answers_json TEXT DEFAULT '{}',
                stakeholders_json TEXT DEFAULT '[]',
                commitments_json TEXT DEFAULT '[]'
            );

            CREATE TABLE crm_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                lead_id INTEGER,
                case_id INTEGER,
                campaign_id INTEGER,
                reference_code TEXT DEFAULT '',
                title TEXT,
                status TEXT DEFAULT 'draft',
                signed_on TEXT DEFAULT '',
                starts_on TEXT DEFAULT '',
                ends_on TEXT DEFAULT '',
                amount_vnd INTEGER DEFAULT 0,
                renewal_reminder_days INTEGER DEFAULT 30,
                notes TEXT DEFAULT '',
                service_slug TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

    def _seed_presales_ready(self, conn: sqlite3.Connection) -> int:
        from crm_lead_presales import (
            ensure_presales,
            ensure_schema,
            list_presales_tasks,
            update_presales_task,
        )
        from crm_svc_tasks import ensure_schema as ensure_svc_tasks

        ensure_schema(conn)
        ensure_svc_tasks(conn)
        ps = ensure_presales(conn, 1, "dich-vu-aeo")
        pid = int(ps["id"])
        for stage_tasks in list_presales_tasks(conn, pid).values():
            for task in stage_tasks:
                update_presales_task(conn, int(task["id"]), is_done=True)
        conn.execute(
            "UPDATE crm_lead_presales SET stage = 'proposal' WHERE id = ?", (pid,)
        )
        from crm_lead_presales_marketing_plan import update_preliminary_plan

        update_preliminary_plan(
            conn,
            pid,
            {
                "name": "KH MKT sơ bộ Test",
                "north_star": "Tăng lead chất lượng",
                "strategy_framework": {
                    "market_message": "USP",
                    "media_reach": "Facebook",
                    "conversion_strategy": "Landing",
                },
            },
        )
        conn.commit()
        return pid

    def test_create_draft_contract_placeholder(self) -> None:
        from crm_lead_presales_contract import (
            create_draft_contract_from_lead,
            get_draft_contract_for_lead,
            placeholder_customer_name,
        )

        with self._conn() as conn:
            self._seed_presales_ready(conn)
            ct = create_draft_contract_from_lead(conn, 1, actor="test")
            self.assertEqual(ct["status"], "draft")
            self.assertEqual(int(ct["lead_id"]), 1)
            self.assertEqual(ct["service_slug"], "dich-vu-aeo")
            ph = conn.execute(
                "SELECT is_placeholder, placeholder_lead_id, name FROM crm_customers WHERE id = ?",
                (int(ct["customer_id"]),),
            ).fetchone()
            self.assertEqual(int(ph["is_placeholder"]), 1)
            self.assertEqual(int(ph["placeholder_lead_id"]), 1)
            self.assertIn("[Lead #1]", ph["name"])
            self.assertEqual(
                ph["name"], placeholder_customer_name(1, "Nguyễn Test")
            )
            ct2 = create_draft_contract_from_lead(conn, 1)
            self.assertEqual(int(ct2["id"]), int(ct["id"]))
            self.assertIsNotNone(get_draft_contract_for_lead(conn, 1))

    def test_on_contract_signed_promotes_and_removes_placeholder(self) -> None:
        from crm_lead_presales_contract import (
            create_draft_contract_from_lead,
            on_presales_contract_signed,
        )

        with self._conn() as conn:
            self._seed_presales_ready(conn)
            ct = create_draft_contract_from_lead(conn, 1, actor="test")
            contract_id = int(ct["id"])
            placeholder_id = int(ct["customer_id"])
            conn.execute(
                "INSERT INTO crm_customers (id, name, phone, email, address, company, created_at) "
                "VALUES (42, 'KH thật', '0909999888', '', '', '', '2026-01-01')"
            )
            conn.commit()
            with patch("crm_lead_convert.convert_lead_to_crm") as mock_convert:
                mock_convert.return_value = {
                    "customer_id": 42,
                    "case_id": 7,
                    "already_converted": False,
                }
                result = on_presales_contract_signed(
                    conn, contract_id, actor="director"
                )
            self.assertEqual(int(result["customer_id"]), 42)
            self.assertEqual(int(result["case_id"]), 7)
            self.assertGreater(int(result["lifecycle_id"]), 0)

            ct_row = conn.execute(
                "SELECT customer_id FROM crm_contracts WHERE id = ?",
                (contract_id,),
            ).fetchone()
            self.assertEqual(int(ct_row["customer_id"]), 42)

            ph = conn.execute(
                "SELECT id FROM crm_customers WHERE id = ?", (placeholder_id,)
            ).fetchone()
            self.assertIsNone(ph)

            lead = conn.execute("SELECT status FROM crm_leads WHERE id = 1").fetchone()
            self.assertEqual(lead["status"], "won")

            lc = conn.execute(
                "SELECT stage, status FROM crm_service_lifecycle WHERE id = ?",
                (int(result["lifecycle_id"]),),
            ).fetchone()
            self.assertEqual(lc["stage"], "onboard")
            self.assertEqual(lc["status"], "active")


if __name__ == "__main__":
    unittest.main()
