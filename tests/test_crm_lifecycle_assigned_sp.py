"""Tests L3.3 — gán Specialist (assigned_sp) trên lifecycle."""
from __future__ import annotations

import json
import sqlite3
import unittest

from crm_service_lifecycle import (
    resolve_staff_id_by_name,
    set_assigned_sp,
    suggest_sp_from_tasks,
    sync_assigned_sp_from_tasks,
)
from crm_svc_kpi import get_lifecycle_staff_metrics
from crm_svc_tasks import ensure_schema as task_schema, update_task


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1);
        INSERT INTO crm_staff (id, name, active) VALUES (1, 'Nguyễn AM', 1), (2, 'Trần SP', 1);

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            assigned_am INTEGER,
            assigned_sp INTEGER,
            stage TEXT NOT NULL DEFAULT 'deliver',
            status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO crm_service_lifecycle (id, assigned_am, assigned_sp, stage, status)
        VALUES (1, 1, NULL, 'deliver', 'active');
        """
    )
    task_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_svc_risks (
            id INTEGER PRIMARY KEY,
            lifecycle_id INTEGER,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO crm_svc_tasks
            (lifecycle_id, stage, step_index, title, form_fields, form_data, is_done, created_at, updated_at)
        VALUES (1, 'lead', 0, 'Lead setup', '[]', ?, 0, '2026-06-01', '2026-06-01')
        """,
        (json.dumps({"assigned_sp": "Trần SP"}, ensure_ascii=False),),
    )
    conn.commit()
    return conn


class TestAssignedSp(unittest.TestCase):
    def test_resolve_staff_by_name(self) -> None:
        conn = _setup_conn()
        self.assertEqual(resolve_staff_id_by_name(conn, "Trần SP"), 2)
        self.assertIsNone(resolve_staff_id_by_name(conn, "Không tồn tại"))

    def test_set_assigned_sp(self) -> None:
        conn = _setup_conn()
        self.assertTrue(set_assigned_sp(conn, 1, 2))
        row = conn.execute(
            "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = 1"
        ).fetchone()
        self.assertEqual(int(row["assigned_sp"]), 2)
        name = conn.execute(
            "SELECT name FROM crm_staff WHERE id = ?", (2,)
        ).fetchone()[0]
        self.assertEqual(name, "Trần SP")

    def test_set_assigned_sp_rejects_inactive(self) -> None:
        conn = _setup_conn()
        conn.execute("UPDATE crm_staff SET active = 0 WHERE id = 2")
        conn.commit()
        with self.assertRaises(ValueError):
            set_assigned_sp(conn, 1, 2)

    def test_suggest_and_sync_from_task(self) -> None:
        conn = _setup_conn()
        self.assertEqual(suggest_sp_from_tasks(conn, 1), 2)
        self.assertTrue(sync_assigned_sp_from_tasks(conn, 1))
        row = conn.execute(
            "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = 1"
        ).fetchone()
        self.assertEqual(int(row["assigned_sp"]), 2)

    def test_sync_does_not_overwrite_existing_sp(self) -> None:
        conn = _setup_conn()
        set_assigned_sp(conn, 1, 1)
        conn.execute(
            """
            UPDATE crm_svc_tasks SET form_data = ?
            WHERE lifecycle_id = 1 AND stage = 'lead'
            """,
            (json.dumps({"assigned_sp": "Trần SP"}, ensure_ascii=False),),
        )
        conn.commit()
        self.assertFalse(sync_assigned_sp_from_tasks(conn, 1, overwrite=False))
        row = conn.execute(
            "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = 1"
        ).fetchone()
        self.assertEqual(int(row["assigned_sp"]), 1)

    def test_task_patch_sync_via_update_task(self) -> None:
        conn = _setup_conn()
        task_id = int(
            conn.execute("SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1").fetchone()[0]
        )
        update_task(
            conn,
            task_id,
            form_data={"assigned_sp": "Trần SP"},
        )
        sync_assigned_sp_from_tasks(conn, 1, overwrite=False)
        row = conn.execute(
            "SELECT assigned_sp FROM crm_service_lifecycle WHERE id = 1"
        ).fetchone()
        self.assertEqual(int(row["assigned_sp"]), 2)

    def test_lifecycle_staff_metrics_reflects_assigned_sp(self) -> None:
        conn = _setup_conn()
        conn.execute("UPDATE crm_service_lifecycle SET assigned_am = NULL WHERE id = 1")
        set_assigned_sp(conn, 1, 2)
        conn.execute(
            "UPDATE crm_svc_tasks SET is_done = 1, done_by = 2 WHERE lifecycle_id = 1"
        )
        conn.commit()
        metrics = get_lifecycle_staff_metrics(conn, 1)
        self.assertIsNotNone(metrics["sp"])
        self.assertEqual(metrics["sp"]["id"], 2)
        self.assertEqual(metrics["sp"]["name"], "Trần SP")
        self.assertEqual(metrics["sp"]["tasks_done"], 1)

    def test_sp_metrics_pending_uses_assigned_sp(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_svc_tasks
                (lifecycle_id, stage, step_index, title, is_done, created_at, updated_at)
            VALUES (1, 'deliver', 0, 'Pending task', 0, '2026-06-01', '2026-06-01')
            """
        )
        conn.execute(
            "UPDATE crm_svc_tasks SET is_done = 1 WHERE lifecycle_id = 1 AND stage = 'lead'"
        )
        conn.commit()
        set_assigned_sp(conn, 1, 2)
        pending = conn.execute(
            """
            SELECT COUNT(*) FROM crm_svc_tasks t
            JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
            WHERE lc.assigned_sp = ? AND t.is_done = 0
            """,
            (2,),
        ).fetchone()[0]
        self.assertEqual(int(pending), 1)


if __name__ == "__main__":
    unittest.main()
