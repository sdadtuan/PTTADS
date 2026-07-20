"""Tests for Sprint 0 PG-primary ingest config and sync."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ptt_crm.config import (
    facebook_background_in_gunicorn,
    leads_write_source,
    leads_write_source_pg,
)


class TestLeadsWriteSourceConfig(unittest.TestCase):
    def test_default_pg(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_LEADS_WRITE_SOURCE", None)
            self.assertEqual(leads_write_source(), "pg")
            self.assertTrue(leads_write_source_pg())

    def test_sqlite_rollback(self) -> None:
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "sqlite"}, clear=False):
            self.assertEqual(leads_write_source(), "sqlite")
            self.assertFalse(leads_write_source_pg())

    def test_pg_mode(self) -> None:
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "pg"}, clear=False):
            self.assertEqual(leads_write_source(), "pg")
            self.assertTrue(leads_write_source_pg())

    def test_gunicorn_autosync_default_off(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CRM_FACEBOOK_BACKGROUND_IN_GUNICORN", None)
            self.assertFalse(facebook_background_in_gunicorn())


class TestSyncLeadIdsWorker(unittest.TestCase):
    @patch("ptt_crm.lead_sync._update_sync_state")
    @patch("ptt_crm.lead_sync.upsert_pg_lead")
    @patch("ptt_crm.lead_sync._fetch_sqlite_rows")
    @patch("ptt_crm.lead_sync.pg_leads_replica_ready", return_value=True)
    def test_worker_write_source(
        self,
        _ready: MagicMock,
        mock_fetch: MagicMock,
        mock_upsert: MagicMock,
        _state: MagicMock,
    ) -> None:
        row = MagicMock()
        row.__getitem__ = lambda self, key: {"id": 42}[key]
        mock_fetch.return_value = [row]
        with patch("ptt_crm.lead_sync.sqlite_row_to_pg_record", return_value={"sqlite_lead_id": 42}):
            from ptt_crm.lead_sync import sync_lead_ids_worker

            out = sync_lead_ids_worker([42])
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("write_source"), "worker")
        mock_upsert.assert_called_once()
        self.assertEqual(mock_upsert.call_args.kwargs.get("write_source"), "worker")


class TestIngestLeadPgPrimary(unittest.TestCase):
    def test_pg_primary_rollback_when_sync_fails(self) -> None:
        payload = {
            "channel": "meta",
            "client_id": "550e8400-e29b-41d4-a716-446655440000",
            "lead": {
                "channel": "meta",
                "external_lead_id": "pg-fail-001",
                "contact": {"full_name": "PG Fail", "phone": "0901234567", "email": ""},
                "raw": {
                    "full_name": "PG Fail",
                    "phone": "0901234567",
                    "email": "",
                    "source": "facebook",
                    "meta": {"facebook_leadgen_id": "pg-fail-001"},
                },
            },
        }
        mock_conn = MagicMock()
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "pg"}, clear=False):
            with patch("ptt_jobs.handlers.ingest_lead.leads_write_source_pg", side_effect=[False, True]):
                with patch("ptt_jobs.handlers.ingest_lead.sqlite3.connect", return_value=mock_conn):
                    with patch("crm_lead_webhooks.ingest_webhook_leads") as mock_ingest:
                        mock_ingest.return_value = {"created_count": 1, "created_ids": [99], "skipped": []}
                        with patch("ptt_jobs.db.pg_available", return_value=True):
                            with patch("ptt_crm.lead_sync.sync_lead_ids_worker") as mock_sync:
                                mock_sync.return_value = {"ok": False, "synced": 0, "error": "pg_replica_not_ready"}
                                from ptt_jobs.handlers.ingest_lead import process_ingest_lead_payload

                                result = process_ingest_lead_payload(payload, correlation_id="corr-pg")

        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "pg_primary_sync_failed")
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch("ptt_crm.lead_ingest_pg.process_ingest_lead_payload_pg")
    @patch("ptt_crm.config.leads_write_source_pg", return_value=True)
    def test_pg_primary_routes_to_worker_pg(
        self,
        _cfg: MagicMock,
        mock_pg: MagicMock,
    ) -> None:
        mock_pg.return_value = {"ok": True, "created_ids": [42], "write_path": "pg_primary"}
        from ptt_jobs.handlers.ingest_lead import process_ingest_lead_payload

        out = process_ingest_lead_payload({"channel": "meta", "lead": {}})
        self.assertTrue(out.get("ok"))
        mock_pg.assert_called_once()


if __name__ == "__main__":
    unittest.main()
