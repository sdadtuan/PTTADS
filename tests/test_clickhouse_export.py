"""Unit tests for ClickHouse domain_events export (Phase 4 F4)."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ptt_analytics.clickhouse_export import (
    _client_id_from_correlation,
    export_to_clickhouse,
    fetch_domain_events,
)


class TestClickHouseExport(unittest.TestCase):
    def test_client_id_from_correlation_uuid(self) -> None:
        cid = "550e8400-e29b-41d4-a716-446655440000"
        self.assertEqual(_client_id_from_correlation(cid), cid)

    def test_client_id_from_correlation_non_uuid(self) -> None:
        self.assertIsNone(_client_id_from_correlation("campaign-write:abc"))

    @patch("ptt_jobs.db.pg_connection")
    def test_fetch_domain_events_maps_rows(self, mock_pg) -> None:
        conn = MagicMock()
        cur = MagicMock()
        ts = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
        cur.fetchall.return_value = [
            (
                "e1",
                "CampaignWriteSubmitted",
                "campaign_write",
                "req-1",
                '{"k":1}',
                "idem-1",
                "550e8400-e29b-41d4-a716-446655440000",
                ts,
            )
        ]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        rows = fetch_domain_events(since=ts)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "CampaignWriteSubmitted")
        self.assertEqual(rows[0]["client_id"], "550e8400-e29b-41d4-a716-446655440000")

    @patch("ptt_analytics.clickhouse_export._ch_request")
    def test_export_to_clickhouse_json_each_row(self, mock_ch) -> None:
        mock_ch.return_value = b""
        with patch("ptt_analytics.clickhouse_export.fetch_domain_events") as mock_fetch:
            mock_fetch.return_value = [
                {
                    "event_id": "e1",
                    "event_type": "TestEvent",
                    "aggregate_type": "test",
                    "aggregate_id": "a1",
                    "client_id": None,
                    "payload": "{}",
                    "idempotency_key": "",
                    "created_at": "2026-07-17 10:00:00.000",
                }
            ]

            out = export_to_clickhouse(since="2026-07-17T00:00:00Z")
            self.assertTrue(out["ok"])
            self.assertEqual(out["exported"], 1)
            call_args = mock_ch.call_args
            self.assertIn("JSONEachRow", call_args[0][0])
            body = call_args[1]["data"].decode("utf-8")
            row = json.loads(body.splitlines()[0])
            self.assertEqual(row["event_type"], "TestEvent")


if __name__ == "__main__":
    unittest.main()
