# tests/test_crm_svc_tasks.py
"""Tests cho crm_svc_tasks module."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_tasks import (
    SERVICE_LABELS,
    create_custom_task,
    delete_task,
    ensure_schema,
    get_progress,
    list_tasks,
    seed_tasks,
    update_task,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS crm_staff (id INTEGER PRIMARY KEY)")
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
        VALUES (1, 'dich-vu-seo-tong-the', 'lead', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_table_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_tasks", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)  # gọi lần 2 không lỗi
        ensure_schema(conn)


class TestSeedTasks(unittest.TestCase):
    def test_seeds_correct_count(self):
        conn = _setup_conn()
        count = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count, 0)
        db_count = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = 1"
        ).fetchone()[0]
        self.assertEqual(db_count, count)
        # 6 stage × 1 task + deliver 12 tháng = 18
        self.assertEqual(db_count, 18)

    def test_project_slug_single_deliver_task(self):
        conn = _setup_conn()
        count = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-audit")
        deliver_count = conn.execute(
            "SELECT COUNT(*) FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'deliver'"
        ).fetchone()[0]
        self.assertEqual(deliver_count, 1)
        self.assertEqual(count, 7)

    def test_idempotent_second_call_returns_zero(self):
        conn = _setup_conn()
        count1 = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        count2 = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        self.assertGreater(count1, 0)
        self.assertEqual(count2, 0)

    def test_unknown_slug_returns_zero(self):
        conn = _setup_conn()
        count = seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-khong-ton-tai")
        self.assertEqual(count, 0)

    def test_form_fields_stored_as_json(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        row = conn.execute(
            "SELECT form_fields FROM crm_svc_tasks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()
        import json
        fields = json.loads(row["form_fields"])
        self.assertIsInstance(fields, list)


class TestListTasks(unittest.TestCase):
    def test_returns_dict_by_stage(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        result = list_tasks(conn, lifecycle_id=1)
        self.assertIsInstance(result, dict)
        self.assertIn("lead", result)
        self.assertIsInstance(result["lead"], list)
        self.assertGreater(len(result["lead"]), 0)

    def test_form_data_is_dict(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        result = list_tasks(conn, lifecycle_id=1)
        task = result["lead"][0]
        self.assertIsInstance(task["form_data"], dict)

    def test_form_fields_is_list(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        result = list_tasks(conn, lifecycle_id=1)
        task = result["lead"][0]
        self.assertIsInstance(task["form_fields"], list)

    def test_empty_lifecycle_returns_empty(self):
        conn = _setup_conn()
        result = list_tasks(conn, lifecycle_id=999)
        self.assertEqual(result, {})


class TestUpdateTask(unittest.TestCase):
    def _get_task_id(self, conn):
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        return conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 LIMIT 1"
        ).fetchone()["id"]

    def test_mark_done(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, is_done=True)
        row = conn.execute(
            "SELECT is_done, done_at FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["is_done"], 1)
        self.assertTrue(len(row["done_at"]) > 0)

    def test_mark_undone_clears_done_at(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, is_done=True)
        update_task(conn, tid, is_done=False)
        row = conn.execute(
            "SELECT is_done, done_at FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["is_done"], 0)
        self.assertEqual(row["done_at"], "")

    def test_save_notes(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, notes="Ghi chú test")
        row = conn.execute(
            "SELECT notes FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["notes"], "Ghi chú test")

    def test_save_form_data(self):
        conn = _setup_conn()
        tid = self._get_task_id(conn)
        update_task(conn, tid, form_data={"niche": "bất động sản", "budget": 5000000})
        result = list_tasks(conn, lifecycle_id=1)
        task = next(t for s in result.values() for t in s if t["id"] == tid)
        self.assertEqual(task["form_data"]["niche"], "bất động sản")
        self.assertEqual(task["form_data"]["budget"], 5000000)


class TestCustomTask(unittest.TestCase):
    def test_create_custom_task(self):
        conn = _setup_conn()
        tid = create_custom_task(
            conn, lifecycle_id=1, stage="deliver", title="Task tuỳ chỉnh"
        )
        self.assertIsInstance(tid, int)
        row = conn.execute(
            "SELECT * FROM crm_svc_tasks WHERE id = ?", (tid,)
        ).fetchone()
        self.assertEqual(row["is_custom"], 1)
        self.assertEqual(row["title"], "Task tuỳ chỉnh")
        self.assertEqual(row["stage"], "deliver")

    def test_delete_custom_task(self):
        conn = _setup_conn()
        tid = create_custom_task(
            conn, lifecycle_id=1, stage="deliver", title="Task xoá"
        )
        ok = delete_task(conn, tid)
        self.assertTrue(ok)
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_tasks WHERE id = ?", (tid,)
            ).fetchone()
        )

    def test_cannot_delete_template_task(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        tid = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE is_custom = 0 LIMIT 1"
        ).fetchone()["id"]
        ok = delete_task(conn, tid)
        self.assertFalse(ok)

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        ok = delete_task(conn, 99999)
        self.assertFalse(ok)


class TestGetProgress(unittest.TestCase):
    def test_returns_all_stages(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        progress = get_progress(conn, lifecycle_id=1)
        from crm_service_lifecycle import VALID_STAGES
        for stage in VALID_STAGES:
            self.assertIn(stage, progress)

    def test_lead_stage_has_tasks(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        progress = get_progress(conn, lifecycle_id=1)
        self.assertGreater(progress["lead"]["total"], 0)
        self.assertEqual(progress["lead"]["done"], 0)
        self.assertEqual(progress["lead"]["pct"], 0)

    def test_pct_100_when_all_done(self):
        conn = _setup_conn()
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        tasks = list_tasks(conn, lifecycle_id=1)
        for t in tasks.get("lead", []):
            update_task(conn, t["id"], is_done=True)
        progress = get_progress(conn, lifecycle_id=1)
        self.assertEqual(progress["lead"]["pct"], 100)


class TestServiceLabels(unittest.TestCase):
    def test_all_12_slugs_in_labels(self):
        from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS
        for slug in SERVICE_WORKFLOW_STEPS:
            self.assertIn(slug, SERVICE_LABELS, f"Missing label for {slug}")


if __name__ == "__main__":
    unittest.main()
