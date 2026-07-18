"""SLA notification sync tests (P0-07)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ptt_agency.notifications import sync_sla_notifications


class TestSlaNotificationSync(unittest.TestCase):
    @patch("ptt_agency.notifications.create_notification")
    @patch("crm_lead_sla.sync_lead_sla_reminders", return_value=2)
    def test_per_owner_inbox(self, _sync, mock_create) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            conn.execute(
                """
                CREATE TABLE crm_reminders (
                    id INTEGER PRIMARY KEY,
                    scope TEXT, ref_id INTEGER, reminder_kind TEXT,
                    title TEXT, body TEXT, remind_at TEXT,
                    status TEXT, staff_id INTEGER, meta_json TEXT,
                    created_at TEXT, updated_at TEXT
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO crm_reminders (
                    scope, ref_id, reminder_kind, title, body, remind_at,
                    status, staff_id, meta_json, created_at, updated_at
                ) VALUES ('lead', ?, 'sla_overdue', 't', 'b', 'now', 'pending', ?, '{}', 'now', 'now')
                """,
                [(1, 10), (2, 10), (3, 11)],
            )
            conn.commit()
            conn.close()

            out = sync_sla_notifications(sqlite_path=tmp.name, ts="2026-07-17T10:00:00Z")
            self.assertEqual(out["overdue_count"], 2)
            self.assertEqual(len(out["owners_notified"]), 2)
            self.assertGreaterEqual(mock_create.call_count, 3)


if __name__ == "__main__":
    unittest.main()
