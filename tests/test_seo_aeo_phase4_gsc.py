
import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
from ptt_seo.db import SeoDB


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


@contextmanager
def _fake_pg(db: SeoDB):
    yield db


class TestGscOAuthState(unittest.TestCase):
    def test_state_roundtrip(self) -> None:
        state = build_oauth_state(customer_id=42, site_url="https://example.com/")
        parsed = parse_oauth_state(state)
        self.assertEqual(parsed["customer_id"], 42)
        self.assertEqual(parsed["site_url"], "https://example.com/")


class TestGscApiStub(unittest.TestCase):
    def test_stub_rows(self) -> None:
        with patch.dict(os.environ, {"PTT_GSC_SYNC_STUB": "1"}):
            self.assertTrue(gsc_stub_mode())
            from datetime import date

            rows = fetch_search_analytics(
                "stub",
                "https://example.com/",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 2),
            )
            self.assertGreaterEqual(len(rows), 1)


class TestGscSyncStub(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_GSC_SYNC_STUB": "1"})
    @patch("ptt_seo.integrations.seo_pg_only")
    @patch("ptt_seo.connectors.gsc_sync.seo_pg_only")
    @patch("ptt_seo.connectors.gsc_sync.patch_integrations")
    @patch("ptt_seo.connectors.gsc_sync.get_gsc_integration")
    @patch("ptt_seo.connectors.gsc_sync.resolve_gsc_refresh_token")
    def test_sync_stub_writes_stats(
        self,
        mock_refresh,
        mock_get_gsc,
        mock_patch,
        mock_sync_pg,
        mock_int_pg,
    ) -> None:
        db = _mem_db()

        @contextmanager
        def fake_pg():
            yield db

        mock_sync_pg.side_effect = fake_pg
        mock_int_pg.side_effect = fake_pg
        mock_refresh.return_value = None
        mock_get_gsc.return_value = {"site_url": "https://example.com/", "status": "connected"}
        mock_patch.return_value = {}

        outcome = sync_gsc_for_customer(1, days=7)
        self.assertTrue(outcome.get("ok"))
        row = db.execute("SELECT COUNT(*) AS c FROM seo_gsc_daily_stats WHERE customer_id = ?", (1,)).fetchone()
        self.assertGreater(int(row["c"]), 0)

    @patch.dict(os.environ, {"PTT_GSC_SYNC_STUB": "1"})
    @patch("ptt_seo.connectors.gsc_sync.sync_gsc_for_customer")
    def test_process_payload(self, mock_sync) -> None:
        mock_sync.return_value = {"ok": True, "rows_imported": 2}
        out = process_seo_gsc_sync_payload({"customer_id": 5, "days": 28})
        self.assertTrue(out["ok"])
        mock_sync.assert_called_once()


class TestGscBatchSync(unittest.TestCase):
    def test_gsc_sync_enabled_flag(self) -> None:
        with patch.dict(os.environ, {"PTT_GSC_SYNC_ENABLED": "1"}, clear=False):
            self.assertTrue(gsc_sync_enabled())
        with patch.dict(os.environ, {"PTT_GSC_SYNC_ENABLED": "0"}, clear=False):
            self.assertFalse(gsc_sync_enabled())

    @patch.dict(os.environ, {"PTT_GSC_SYNC_ENABLED": "0", "PTT_GSC_SYNC_STUB": "0"}, clear=False)
    def test_sync_all_skipped_when_disabled(self) -> None:
        out = sync_all_gsc_customers()
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "PTT_GSC_SYNC_ENABLED=0")

    @patch.dict(os.environ, {"PTT_GSC_SYNC_ENABLED": "1", "PTT_GSC_SYNC_STUB": "0"}, clear=False)
    @patch("ptt_seo.connectors.gsc_sync.list_gsc_connected_customer_ids")
    def test_sync_all_no_customers(self, mock_list) -> None:
        mock_list.return_value = []
        out = sync_all_gsc_customers()
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "no_gsc_connected_customers")

    @patch.dict(os.environ, {"PTT_GSC_SYNC_ENABLED": "1", "PTT_GSC_SYNC_STUB": "1"}, clear=False)
    @patch("ptt_seo.connectors.gsc_sync.sync_gsc_for_customer")
    @patch("ptt_seo.connectors.gsc_sync.list_gsc_connected_customer_ids")
    def test_sync_all_batch(self, mock_list, mock_sync) -> None:
        mock_list.return_value = [1, 2]
        mock_sync.side_effect = [{"ok": True, "rows_imported": 3}, {"ok": False, "error": "fail"}]
        out = sync_all_gsc_customers(days=14)
        self.assertFalse(out["ok"])
        self.assertEqual(out["customers"], 2)
        self.assertEqual(out["ok_count"], 1)
        self.assertEqual(out["failed"], 1)
        self.assertEqual(mock_sync.call_count, 2)
        mock_sync.assert_any_call(1, days=14)
        mock_sync.assert_any_call(2, days=14)


if __name__ == "__main__":
    unittest.main()
