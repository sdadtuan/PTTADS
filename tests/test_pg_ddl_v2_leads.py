"""Tests for PostgreSQL DDL v2 — crm_leads read replica (Phase 1b Bước 5)."""
from __future__ import annotations

import unittest

from ptt_crm.pg_schema import (
    CRM_LEADS_COLUMNS,
    MIGRATION_VERSION,
    ddl_v2_path,
    pg_leads_migration_applied,
    pg_leads_replica_ready,
    pg_row_to_v1,
)


class TestPgDdlV2Artifacts(unittest.TestCase):
    def test_ddl_file_exists(self) -> None:
        self.assertTrue(ddl_v2_path().is_file())
        text = ddl_v2_path().read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS crm_leads", text)
        self.assertIn("crm_leads_sync_state", text)
        self.assertIn(MIGRATION_VERSION, text)

    def test_pg_row_to_v1_maps_sqlite_id(self) -> None:
        row = {
            "sqlite_lead_id": 42,
            "full_name": "A",
            "phone": "090",
            "email": "",
            "status": "new",
            "source": "facebook",
            "channel": "meta",
            "agency_client_id": "550e8400-e29b-41d4-a716-446655440000",
            "campaign_id": None,
            "external_lead_id": "fb-1",
            "owner_id": None,
            "created_at": "2026-07-17",
            "received_at": "2026-07-17",
            "is_duplicate": False,
        }
        v1 = pg_row_to_v1(row)
        self.assertEqual(v1["id"], 42)
        self.assertEqual(v1["channel"], "meta")
        self.assertEqual(len(CRM_LEADS_COLUMNS), 17)


@unittest.skipUnless(
    __import__("ptt_jobs.db", fromlist=["pg_available"]).pg_available(),
    "PostgreSQL unavailable",
)
class TestPgDdlV2Apply(unittest.TestCase):
    def test_apply_idempotent(self) -> None:
        from ptt_crm.pg_schema import apply_ddl_v2, pg_leads_stats

        apply_ddl_v2()
        apply_ddl_v2()
        self.assertTrue(pg_leads_replica_ready())
        self.assertTrue(pg_leads_migration_applied())
        stats = pg_leads_stats()
        self.assertTrue(stats["ready"])
        self.assertGreaterEqual(stats["rows"], 0)


if __name__ == "__main__":
    unittest.main()
