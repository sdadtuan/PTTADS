"""Backfill quyền HDSD cho menu sidebar."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest

from admin_page_permissions import migrate_hdsd_position_permissions


class TestHdsdPermissionsMigration(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE crm_positions (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE crm_position_section_permissions (
                position_id INTEGER NOT NULL,
                section_id TEXT NOT NULL,
                action TEXT NOT NULL,
                PRIMARY KEY (position_id, section_id, action)
            );
            INSERT INTO crm_positions (id, code, active) VALUES (1, 'MKT-01', 1);
            INSERT INTO crm_position_section_permissions (position_id, section_id, action)
            VALUES (1, 'crm_leads', 'view');
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_backfills_hdsd_for_existing_position(self) -> None:
        migrate_hdsd_position_permissions(self.conn)
        rows = self.conn.execute(
            """
            SELECT action FROM crm_position_section_permissions
            WHERE position_id = 1 AND section_id = 'crm_hdsd'
            ORDER BY action
            """
        ).fetchall()
        self.assertEqual(["export", "view"], [r["action"] for r in rows])


if __name__ == "__main__":
    unittest.main()
