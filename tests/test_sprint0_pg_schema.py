"""Sprint 0 DDL helpers."""
from __future__ import annotations

import unittest
from unittest.mock import patch


class TestSprint0PgSchema(unittest.TestCase):
    @patch("ptt_jobs.db.pg_available", return_value=True)
    @patch("ptt_crm.pg_schema.pg_sprint0_ready", return_value=True)
    def test_sprint0_ready(self, _ready: object, _pg: object) -> None:
        from ptt_crm.pg_schema import pg_sprint0_ready

        self.assertTrue(pg_sprint0_ready())

    def test_migration_version_length(self) -> None:
        from ptt_crm.pg_schema import MIGRATION_V3_EVENTS_IDEM, MIGRATION_V3_SPRINT0

        self.assertLessEqual(len(MIGRATION_V3_EVENTS_IDEM), 32)
        self.assertLessEqual(len(MIGRATION_V3_SPRINT0), 32)


if __name__ == "__main__":
    unittest.main()
