"""R5 — Kế hoạch MKT sơ bộ @ Proposal; TMMT @ lifecycle Deliver."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path


def _fill_preliminary(conn: sqlite3.Connection, presales_id: int) -> None:
    from crm_lead_presales_marketing_plan import update_preliminary_plan

    update_preliminary_plan(
        conn,
        presales_id,
        {
            "name": "KH MKT sơ bộ Demo",
            "north_star": "Tăng lead chất lượng Q3",
            "strategy_framework": {
                "market_message": "USP rõ ràng cho ICP",
                "media_reach": "Facebook + Google Ads",
                "conversion_strategy": "Landing + retarget 7 ngày",
            },
        },
    )


def _fill_official_tmmt(conn: sqlite3.Connection, lifecycle_id: int) -> None:
    from crm_lead_presales_marketing_plan import update_official_plan

    update_official_plan(
        conn,
        lifecycle_id,
        {
            "strategy_framework": {
                "target_market": "Gia đình trẻ thu nhập trung bình-khá tại TP.HCM",
            },
            "target_market_prof": {
                "market_context": "Thị trường F&B tăng trưởng",
                "segmentation_icp": "Quán cafe 50-150m2",
                "personas_roles": "Chủ quán 28-40 tuổi",
                "pains_desired_outcomes": "Thiếu lead ổn định",
                "buy_triggers_obstacles": "Mùa cao điểm cần nhanh",
                "segment_priorities": "Quận 1-7 trước",
            },
        },
    )


class PresalesMarketingPlanR5Tests(unittest.TestCase):
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
                care_stage_current TEXT NOT NULL DEFAULT 'first_contact',
                care_stages_done_json TEXT NOT NULL DEFAULT '{}'
            );
            INSERT INTO crm_leads (id, full_name, owner_id) VALUES (1, 'Test Lead', 5);

            CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1);
            INSERT INTO crm_staff (id, name) VALUES (5, 'AM Test');

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
                updated_at TEXT,
                marketing_plan_id INTEGER
            );

            CREATE TABLE crm_service_lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lifecycle_id INTEGER,
                from_stage TEXT,
                to_stage TEXT,
                actor_id INTEGER,
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
                completed_at TEXT DEFAULT ''
            );

            CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO crm_customers (id, name) VALUES (10, 'KH Test');
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

    def _complete_all_presales_tasks(self, conn: sqlite3.Connection, pid: int) -> None:
        from crm_lead_presales import list_presales_tasks, update_presales_task

        for stage_tasks in list_presales_tasks(conn, pid).values():
            for task in stage_tasks:
                update_presales_task(conn, int(task["id"]), is_done=True)

    def test_preliminary_plan_blocks_proposal_advance(self) -> None:
        from crm_lead_presales import (
            PresalesAdvanceError,
            advance_presales_stage,
            ensure_presales,
            ensure_schema,
            list_presales_tasks,
            update_presales_task,
        )
        from crm_lead_presales_marketing_plan import ensure_r5_schema

        with self._conn() as conn:
            ensure_schema(conn)
            ensure_r5_schema(conn)
            import json

            conn.execute(
                "UPDATE crm_leads SET care_stages_done_json = ? WHERE id = 1",
                (json.dumps({"first_contact": "2026-01-01"}, ensure_ascii=False),),
            )
            conn.commit()
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
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
            for task in list_presales_tasks(conn, pid).get("consult", []):
                update_presales_task(conn, int(task["id"]), is_done=True)
            conn.commit()
            with self.assertRaises(PresalesAdvanceError) as ctx:
                advance_presales_stage(conn, pid, "proposal")
            self.assertIn("North Star", str(ctx.exception))

    def test_preliminary_plan_allows_proposal_advance(self) -> None:
        from crm_lead_presales import (
            advance_presales_stage,
            ensure_presales,
            ensure_schema,
            list_presales_tasks,
            update_presales_task,
        )
        from crm_lead_presales_marketing_plan import ensure_r5_schema

        with self._conn() as conn:
            ensure_schema(conn)
            ensure_r5_schema(conn)
            import json

            conn.execute(
                "UPDATE crm_leads SET care_stages_done_json = ? WHERE id = 1",
                (json.dumps({"first_contact": "2026-01-01"}, ensure_ascii=False),),
            )
            conn.commit()
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
            for stage in ("lead", "consult"):
                if stage == "lead":
                    for task in list_presales_tasks(conn, pid).get("lead", []):
                        update_presales_task(conn, int(task["id"]), is_done=True)
                    conn.execute(
                        """
                        INSERT INTO crm_lead_intake_sessions (
                            lead_id, service_slug, mode, status, bant_total, decision,
                            updated_at, completed_at
                        ) VALUES (1, 'dich-vu-aeo', 'phone', 'completed', 26, 'go', '2026-01-01', '2026-01-01')
                        """
                    )
                    conn.commit()
                    advance_presales_stage(conn, pid, "consult")
                for task in list_presales_tasks(conn, pid).get(stage, []):
                    update_presales_task(conn, int(task["id"]), is_done=True)
            _fill_preliminary(conn, pid)
            conn.commit()
            advance_presales_stage(conn, pid, "proposal")
            row = conn.execute(
                "SELECT stage FROM crm_lead_presales WHERE id = ?", (pid,)
            ).fetchone()
            self.assertEqual(row["stage"], "proposal")

    def test_promote_clones_official_marketing_plan(self) -> None:
        from crm_lead_presales import ensure_presales, ensure_schema, promote_presales_to_lifecycle
        from crm_lead_presales_marketing_plan import (
            ensure_r5_schema,
            get_official_plan_for_lifecycle,
        )
        from crm_svc_tasks import ensure_schema as ensure_svc_tasks

        with self._conn() as conn:
            ensure_schema(conn)
            ensure_r5_schema(conn)
            ensure_svc_tasks(conn)
            import json

            conn.execute(
                "UPDATE crm_leads SET care_stages_done_json = ? WHERE id = 1",
                (json.dumps({"first_contact": "2026-01-01"}, ensure_ascii=False),),
            )
            conn.commit()
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
            self._complete_all_presales_tasks(conn, pid)
            _fill_preliminary(conn, pid)
            conn.execute("UPDATE crm_lead_presales SET stage = 'proposal' WHERE id = ?", (pid,))
            conn.commit()
            lc_id = promote_presales_to_lifecycle(conn, pid, customer_id=10, contract_id=99)
            lc = conn.execute(
                "SELECT marketing_plan_id FROM crm_service_lifecycle WHERE id = ?",
                (lc_id,),
            ).fetchone()
            self.assertIsNotNone(lc["marketing_plan_id"])
            official = get_official_plan_for_lifecycle(conn, lc_id)
            self.assertIsNotNone(official)
            self.assertEqual(official.get("plan_kind"), "official")

    def test_deliver_advance_requires_tmmt(self) -> None:
        from crm_lead_presales import ensure_presales, ensure_schema, promote_presales_to_lifecycle
        from crm_lead_presales_marketing_plan import ensure_r5_schema
        from crm_service_lifecycle import StageAdvanceError, advance_stage, ensure_schema as ensure_lc
        from crm_svc_tasks import ensure_schema as ensure_svc_tasks, is_stage_complete

        with self._conn() as conn:
            ensure_schema(conn)
            ensure_r5_schema(conn)
            ensure_lc(conn)
            ensure_svc_tasks(conn)
            import json

            conn.execute(
                "UPDATE crm_leads SET care_stages_done_json = ? WHERE id = 1",
                (json.dumps({"first_contact": "2026-01-01"}, ensure_ascii=False),),
            )
            conn.commit()
            ps = ensure_presales(conn, 1, "dich-vu-aeo")
            pid = int(ps["id"])
            self._complete_all_presales_tasks(conn, pid)
            _fill_preliminary(conn, pid)
            conn.execute("UPDATE crm_lead_presales SET stage = 'proposal' WHERE id = ?", (pid,))
            conn.commit()
            lc_id = promote_presales_to_lifecycle(conn, pid, customer_id=10, contract_id=99)
            if not is_stage_complete(conn, lc_id, "onboard"):
                conn.execute(
                    """
                    UPDATE crm_svc_tasks SET is_done = 1
                    WHERE lifecycle_id = ? AND stage = 'onboard'
                    """,
                    (lc_id,),
                )
                conn.commit()
            with self.assertRaises(StageAdvanceError) as ctx:
                advance_stage(conn, lc_id, "deliver")
            self.assertIn("TMMT", str(ctx.exception))
            _fill_official_tmmt(conn, lc_id)
            conn.commit()
            advance_stage(conn, lc_id, "deliver")
            row = conn.execute(
                "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lc_id,)
            ).fetchone()
            self.assertEqual(row["stage"], "deliver")


if __name__ == "__main__":
    unittest.main()
