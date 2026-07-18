"""Tests for Meta insights sync (Phase 2 M2/M4)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.graph_insights import normalize_insight_row, stub_campaign_insights


class TestGraphInsights(unittest.TestCase):
    def test_normalize_insight_row(self) -> None:
        row = normalize_insight_row(
            {
                "campaign_id": "123",
                "campaign_name": "Test",
                "date_start": "2026-07-16",
                "spend": "1000",
                "impressions": "5000",
                "clicks": "50",
                "actions": [{"action_type": "lead", "value": "2"}],
            }
        )
        self.assertEqual(row["external_campaign_id"], "123")
        self.assertEqual(row["leads_platform"], 2)
        self.assertEqual(row["spend"], 1000.0)

    def test_stub_insights(self) -> None:
        rows = stub_campaign_insights(since="2026-07-16", until="2026-07-16", ad_account_id="act_1")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["external_campaign_id"])


class TestMetaInsightsSyncJob(unittest.TestCase):
    @patch("ptt_meta.insights_sync._dispatch_insights_sync_alert")
    @patch("ptt_meta.insights_sync._load_meta_accounts")
    @patch("ptt_meta.insights_sync.meta_insights_sync_enabled", return_value=True)
    @patch("ptt_meta.insights_sync.pg_meta_insights_ready", return_value=True)
    @patch("ptt_meta.insights_sync.sync_account_insights")
    @patch("ptt_meta.insights_sync._update_sync_state")
    def test_sync_alert_on_failure(
        self,
        _state: MagicMock,
        mock_account: MagicMock,
        _ready: MagicMock,
        _enabled: MagicMock,
        mock_accounts: MagicMock,
        mock_alert: MagicMock,
    ) -> None:
        from ptt_meta.insights_sync import sync_meta_insights

        mock_accounts.return_value = [{"client_id": "c1", "external_account_id": "act_1"}]
        mock_account.return_value = {"ok": False, "error": "token_expired", "upserted": 0}
        out = sync_meta_insights(target_date="2026-07-16", compute_metrics=False)
        self.assertFalse(out["ok"])
        mock_alert.assert_called_once()

    @patch("ptt_jobs.handlers.meta_insights_sync.sync_meta_insights")
    @patch("ptt_jobs.handlers.meta_insights_sync.mark_job_done")
    def test_job_success(self, mock_done: MagicMock, mock_sync: MagicMock) -> None:
        from ptt_jobs.handlers.meta_insights_sync import run_meta_insights_sync_job

        mock_sync.return_value = {"ok": True, "rows_upserted": 3}
        run_meta_insights_sync_job(
            {"id": "j1", "payload": {"target_date": "2026-07-16"}, "attempts": 1, "max_attempts": 3}
        )
        mock_done.assert_called_once()


@unittest.skipUnless(
    __import__("ptt_jobs.db", fromlist=["pg_available"]).pg_available()
    and __import__("ptt_meta.insights_sync", fromlist=["pg_meta_insights_ready"]).pg_meta_insights_ready(),
    "PostgreSQL daily_performance unavailable",
)
class TestMetaInsightsIntegration(unittest.TestCase):
    def test_stub_sync_upserts_row(self) -> None:
        import uuid
        from datetime import date

        from ptt_jobs.db import pg_connection
        from ptt_meta.insights_sync import sync_meta_insights

        client_id = None
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM clients ORDER BY created_at LIMIT 1")
                row = cur.fetchone()
                if not row:
                    self.skipTest("no clients in PG")
                client_id = str(row[0])
                cur.execute(
                    """
                    INSERT INTO client_channel_accounts (
                        client_id, channel, external_account_id, display_name, status, meta
                    ) VALUES (%s::uuid, 'meta', %s, 'Stub Account', 'active', '{}'::jsonb)
                    ON CONFLICT (client_id, channel, external_account_id)
                    DO UPDATE SET status = 'active', updated_at = NOW()
                    """,
                    (client_id, f"act_stub_{uuid.uuid4().hex[:8]}"),
                )
            conn.commit()

        target = date(2026, 7, 16)
        with patch("ptt_meta.insights_sync.meta_insights_sync_enabled", return_value=True):
            with patch("ptt_meta.insights_sync.meta_insights_stub_mode", return_value=True):
                with patch("ptt_metrics.compute.compute_cpl_snapshots", return_value={"ok": True, "cpl_snapshots": 0}):
                    out = sync_meta_insights(target_date=target, client_id=client_id, compute_metrics=True)
        self.assertTrue(out.get("ok"), out)
        self.assertGreaterEqual(out.get("rows_upserted", 0), 1)


if __name__ == "__main__":
    unittest.main()
