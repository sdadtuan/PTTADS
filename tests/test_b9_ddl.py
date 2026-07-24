"""B9 DDL v5 — static contract checks."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestB9DdlV5(unittest.TestCase):
    def test_ddl_v5_file_exists_with_table_and_seed(self) -> None:
        path = ROOT / "docs/specs/2026-07-24-postgresql-ddl-v5-meta-conversion.sql"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("meta_conversion_rules", text)
        self.assertIn("idx_meta_conversion_rules_uniq", text)
        self.assertIn("CompleteRegistration", text)
        self.assertIn("2026-07-24-v5-meta-conversion", text)

    def test_apply_script_exists(self) -> None:
        path = ROOT / "scripts/apply_pg_ddl_v5_meta_conversion.sh"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("apply_ddl_v5_meta_conversion", text)
        self.assertIn("pg_meta_alerts_ready", text)

    def test_pg_schema_helpers(self) -> None:
        from ptt_crm import pg_schema

        self.assertTrue(hasattr(pg_schema, "apply_ddl_v5_meta_conversion"))
        self.assertTrue(hasattr(pg_schema, "pg_meta_conversion_rules_ready"))
        self.assertTrue(pg_schema.ddl_v5_meta_conversion_path().is_file())

    def test_env_example_exists(self) -> None:
        path = ROOT / "deploy/env.meta-enterprise-b9.example"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("PTT_META_TRACKING_ENABLED", text)
        self.assertIn("PTT_META_CONVERSION_SYNC_ENABLED", text)


if __name__ == "__main__":
    unittest.main()
