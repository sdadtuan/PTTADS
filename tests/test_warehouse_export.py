"""Unit tests for B14 Meta warehouse export."""
from __future__ import annotations

import os
import unittest


class TestWarehouseExport(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        from ptt_meta.warehouse_export import export_meta_facts_to_clickhouse

        old = os.environ.get("PTT_META_WAREHOUSE_EXPORT")
        os.environ["PTT_META_WAREHOUSE_EXPORT"] = "0"
        try:
            out = export_meta_facts_to_clickhouse(stub=False, skip_if_no_ch=True)
        finally:
            if old is None:
                os.environ.pop("PTT_META_WAREHOUSE_EXPORT", None)
            else:
                os.environ["PTT_META_WAREHOUSE_EXPORT"] = old
        self.assertTrue(out.get("skipped"))

    def test_stub_collect_shape(self) -> None:
        from ptt_meta.warehouse_export import export_meta_facts_to_clickhouse

        out = export_meta_facts_to_clickhouse(fact_date="2026-07-20", stub=True)
        self.assertTrue(out["ok"])
        self.assertTrue(out["stub"])
        self.assertEqual(out["fact_date"], "2026-07-20")

    def test_compare_parity_structure(self) -> None:
        from ptt_meta.warehouse_export import compare_export_parity

        out = compare_export_parity(days=7)
        self.assertIn("pg_count", out)
        self.assertIn("ch_count", out)
        self.assertIn("date_from", out)

    def test_hourly_allowlist_filter(self) -> None:
        from ptt_meta.insights_sync import _filter_hourly_accounts, meta_insights_hourly_enabled

        old_flag = os.environ.get("PTT_META_INSIGHTS_HOURLY")
        old_clients = os.environ.get("PTT_META_INSIGHTS_HOURLY_CLIENTS")
        os.environ["PTT_META_INSIGHTS_HOURLY"] = "1"
        os.environ["PTT_META_INSIGHTS_HOURLY_CLIENTS"] = "client-a"
        try:
            self.assertTrue(meta_insights_hourly_enabled())
            accounts = [
                {"client_id": "client-a", "external_account_id": "act_1"},
                {"client_id": "client-b", "external_account_id": "act_2"},
            ]
            filtered = _filter_hourly_accounts(accounts)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["client_id"], "client-a")
        finally:
            if old_flag is None:
                os.environ.pop("PTT_META_INSIGHTS_HOURLY", None)
            else:
                os.environ["PTT_META_INSIGHTS_HOURLY"] = old_flag
            if old_clients is None:
                os.environ.pop("PTT_META_INSIGHTS_HOURLY_CLIENTS", None)
            else:
                os.environ["PTT_META_INSIGHTS_HOURLY_CLIENTS"] = old_clients


if __name__ == "__main__":
    unittest.main()
