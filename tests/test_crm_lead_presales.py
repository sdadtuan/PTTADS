"""Tests: pre-sales trên Lead (Phương án A)."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path


class LeadPresalesTests(unittest.TestCase):
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
                owner_id INTEGER,
                care_stage_current TEXT NOT NULL DEFAULT 'intake',
                care_stages_done_json TEXT NOT NULL DEFAULT '{}'
            );
            INSERT INTO crm_leads (id, full_name, owner_id) VALUES (1, 'Test Lead', 5);

            CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1);
            INSERT INTO crm_staff (id, name, active) VALUES (5, 'AM Test', 1), (2, 'Trần SP', 1);

            CREATE TABLE crm_service_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                customer_id INTEGER,
                contract_id INTEGER,
                service_slug TEXT,
                stage TEXT,
                status TEXT,
                assigned_am INTEGER,
                assigned_sp INTEGER,
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
                decision_reason TEXT DEFAULT '',
                lead_temperature TEXT DEFAULT '',
                ai_summary TEXT DEFAULT '',
                next_meeting_at TEXT DEFAULT '',
                proposal_date TEXT DEFAULT '',
                completed_at TEXT DEFAULT '',
                bant_json TEXT DEFAULT '{}',
                answers_json TEXT DEFAULT '{}',
                stakeholders_json TEXT DEFAULT '[]',
                commitments_json TEXT DEFAULT '[]',
                updated_at TEXT DEFAULT ''
            );

            CREATE TABLE crm_customers (
                id INTEGER PRIMARY KEY,
                name TEXT
            );
            INSERT INTO crm_customers (id, name) VALUES (10, 'KH Test');

            CREATE TABLE crm_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                lead_id INTEGER,
                title TEXT,
                status TEXT DEFAULT 'draft',
                service_slug TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.commit()
        conn.close()

    def _complete_presales_care_prereq(self, conn: sqlite3.Connection, lead_id: int = 1) -> None:
        import json

        done = {"first_contact": "2026-01-01 11:00:00"}
        conn.execute(
            """
            UPDATE crm_leads
            SET care_stage_current = 'first_contact',
                care_stages_done_json = ?
            WHERE id = ?
            """,
            (json.dumps(done, ensure_ascii=False), int(lead_id)),
        )
        conn.commit()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

    def test_ensure_presales_creates_and_seeds_tasks(self) -> None:
        from crm_lead_presales import ensure_presales, ensure_schema, list_presales_tasks

        with self._conn() as conn:
            ensure_schema(conn)
            self._complete_presales_care_prereq(conn)
            ps = ensure_presales(conn, 1, "dich-vu-seo-local")
            self.assertEqual(ps["lead_id"], 1)
            self.assertEqual(ps["stage"], "lead")
            self.assertEqual(ps["status"], "active")
            self.assertEqual(ps["assigned_am"], 5)
            tasks = list_presales_tasks(conn, int(ps["id"]))
            self.assertIn("lead", tasks)
            self.assertIn("consult", tasks)
            self.assertIn("proposal", tasks)
            self.assertTrue(len(tasks["lead"]) >= 1)

    def test_advance_requires_tasks_done(self) -> None:
        from crm_lead_presales import (
            PresalesAdvanceError,
            advance_presales_stage,
            ensure_presales,
            ensure_schema,
            list_presales_tasks,
            update_presales_task,
        )

        with self._conn() as conn:
            ensure_schema(conn)
            self._complete_presales_care_prereq(conn)
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
            with self.assertRaises(PresalesAdvanceError):
                advance_presales_stage(conn, pid, "consult")
            for task in list_presales_tasks(conn, pid).get("lead", []):
                update_presales_task(conn, int(task["id"]), is_done=True)
            conn.execute(
                """
                INSERT INTO crm_lead_intake_sessions (
                    lead_id, service_slug, mode, status, bant_total, decision, updated_at, completed_at
                ) VALUES (1, 'dich-vu-aeo', 'phone', 'completed', 26, 'go', '2026-01-01', '2026-01-01')
                """
            )
            conn.commit()
            advance_presales_stage(conn, pid, "consult")
            row = conn.execute(
                "SELECT stage FROM crm_lead_presales WHERE id = ?", (pid,)
            ).fetchone()
            self.assertEqual(row["stage"], "consult")

    def test_ensure_presales_blocked_until_b1_b3_done(self) -> None:
        from crm_lead_presales import ensure_presales, ensure_schema

        with self._conn() as conn:
            ensure_schema(conn)
            with self.assertRaises(ValueError) as ctx:
                ensure_presales(conn, 1, "dich-vu-aeo")
            self.assertIn("B2", str(ctx.exception))
            self._complete_presales_care_prereq(conn)
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            self.assertEqual(ps["lead_id"], 1)

    def test_require_presales_care_gate_blocks_task_update(self) -> None:
        from crm_lead_presales import (
            ensure_schema,
            list_presales_tasks,
            require_presales_care_gate,
            update_presales_task,
        )

        with self._conn() as conn:
            ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO crm_lead_presales
                    (lead_id, service_slug, stage, status, stage_entered_at, notes, created_at, updated_at)
                VALUES (1, 'dich-vu-aeo', 'lead', 'active', '2026-01-01', '', '2026-01-01', '2026-01-01')
                """
            )
            conn.commit()
            pid = int(conn.execute("SELECT id FROM crm_lead_presales WHERE lead_id = 1").fetchone()["id"])
            from crm_lead_presales import seed_presales_tasks

            seed_presales_tasks(conn, pid, "dich-vu-aeo")
            task_id = int(list_presales_tasks(conn, pid)["lead"][0]["id"])
            with self.assertRaises(ValueError):
                require_presales_care_gate(conn, 1)
            self._complete_presales_care_prereq(conn)
            require_presales_care_gate(conn, 1)
            update_presales_task(conn, task_id, is_done=True)

    def test_presales_mutation_allowed_after_care_gate(self) -> None:
        from crm_lead_presales import (
            ensure_schema,
            list_presales_tasks,
            require_presales_care_gate,
            seed_presales_tasks,
            update_presales_task,
        )

        with self._conn() as conn:
            ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO crm_lead_presales
                    (lead_id, service_slug, stage, status, stage_entered_at, notes, created_at, updated_at)
                VALUES (1, 'dich-vu-aeo', 'lead', 'active', '2026-01-01', '', '2026-01-01', '2026-01-01')
                """
            )
            conn.commit()
            pid = int(conn.execute("SELECT id FROM crm_lead_presales WHERE lead_id = 1").fetchone()["id"])
            seed_presales_tasks(conn, pid, "dich-vu-aeo")
            task_id = int(list_presales_tasks(conn, pid)["lead"][0]["id"])
            with self.assertRaises(ValueError):
                require_presales_care_gate(conn, 1)
            self._complete_presales_care_prereq(conn)
            require_presales_care_gate(conn, 1)
            update_presales_task(conn, task_id, is_done=True)
            row = conn.execute(
                "SELECT is_done FROM crm_lead_presales_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            self.assertEqual(int(row["is_done"]), 1)

    def test_promote_creates_lifecycle_onboard_with_done_presales_tasks(self) -> None:
        from crm_lead_presales import (
            ensure_presales,
            ensure_schema,
            list_presales_tasks,
            promote_presales_to_lifecycle,
            update_presales_task,
        )

        with self._conn() as conn:
            ensure_schema(conn)
            from crm_svc_tasks import ensure_schema as ensure_svc_tasks

            ensure_svc_tasks(conn)
            self._complete_presales_care_prereq(conn)
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
            for stage_tasks in list_presales_tasks(conn, pid).values():
                for task in stage_tasks:
                    update_presales_task(conn, int(task["id"]), is_done=True)
            from crm_lead_presales_marketing_plan import ensure_r5_schema, update_preliminary_plan

            ensure_r5_schema(conn)
            update_preliminary_plan(
                conn,
                pid,
                {
                    "name": "KH test promote",
                    "north_star": "Demo",
                    "strategy_framework": {
                        "market_message": "msg",
                        "media_reach": "reach",
                        "conversion_strategy": "conv",
                    },
                },
            )
            conn.execute(
                """
                UPDATE crm_lead_presales SET stage = 'proposal' WHERE id = ?
                """,
                (pid,),
            )
            conn.commit()
            lc_id = promote_presales_to_lifecycle(
                conn, pid, customer_id=10, contract_id=99
            )
            lc = conn.execute(
                "SELECT stage, status, customer_id, contract_id FROM crm_service_lifecycle WHERE id = ?",
                (lc_id,),
            ).fetchone()
            self.assertEqual(lc["stage"], "onboard")
            self.assertEqual(lc["status"], "active")
            self.assertEqual(int(lc["customer_id"]), 10)
            presales_row = conn.execute(
                "SELECT status, lifecycle_id FROM crm_lead_presales WHERE id = ?",
                (pid,),
            ).fetchone()
            self.assertEqual(presales_row["status"], "converted")
            self.assertEqual(int(presales_row["lifecycle_id"]), lc_id)
            done_lead = conn.execute(
                """
                SELECT COUNT(*) AS c FROM crm_svc_tasks
                WHERE lifecycle_id = ? AND stage = 'lead' AND is_done = 1
                """,
                (lc_id,),
            ).fetchone()["c"]
            self.assertGreater(int(done_lead), 0)

    def test_promote_syncs_assigned_sp_from_lead_task(self) -> None:
        from crm_lead_presales import (
            ensure_presales,
            ensure_schema,
            list_presales_tasks,
            promote_presales_to_lifecycle,
            update_presales_task,
        )

        with self._conn() as conn:
            ensure_schema(conn)
            from crm_svc_tasks import ensure_schema as ensure_svc_tasks

            ensure_svc_tasks(conn)
            self._complete_presales_care_prereq(conn)
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
            lead_task_id = None
            for stage_tasks in list_presales_tasks(conn, pid).values():
                for task in stage_tasks:
                    tid = int(task["id"])
                    if task.get("stage") == "lead":
                        lead_task_id = tid
                        update_presales_task(
                            conn,
                            tid,
                            form_data={"assigned_sp": "Trần SP"},
                        )
                    update_presales_task(conn, tid, is_done=True)
            self.assertIsNotNone(lead_task_id)
            from crm_lead_presales_marketing_plan import ensure_r5_schema, update_preliminary_plan

            ensure_r5_schema(conn)
            update_preliminary_plan(
                conn,
                pid,
                {
                    "name": "KH test promote SP",
                    "north_star": "Demo",
                    "strategy_framework": {
                        "market_message": "msg",
                        "media_reach": "reach",
                        "conversion_strategy": "conv",
                    },
                },
            )
            conn.execute(
                "UPDATE crm_lead_presales SET stage = 'proposal' WHERE id = ?",
                (pid,),
            )
            conn.commit()
            lc_id = promote_presales_to_lifecycle(
                conn, pid, customer_id=10, contract_id=99
            )
            row = conn.execute(
                "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = ?",
                (lc_id,),
            ).fetchone()
            self.assertEqual(int(row["assigned_sp"]), 2)

    def test_presales_on_lead_flag(self) -> None:
        from crm_lead_presales import presales_on_lead_enabled

        os.environ.pop("PTT_PRESALES_ON_LEAD", None)
        self.assertFalse(presales_on_lead_enabled())
        os.environ["PTT_PRESALES_ON_LEAD"] = "1"
        self.assertTrue(presales_on_lead_enabled())
        os.environ.pop("PTT_PRESALES_ON_LEAD", None)


if __name__ == "__main__":
    unittest.main()
