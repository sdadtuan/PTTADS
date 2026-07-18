"""Tests for Hub → PG hub_campaign_map sync (P0)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_agency.hub_campaign_sync import (
    campaign_sync_payload,
    normalize_meta_campaign_id,
    pg_channel_for_campaign,
    sync_campaign_row,
)


class TestHubCampaignHelpers(unittest.TestCase):
    def test_normalize_meta_campaign_id(self) -> None:
        self.assertEqual(normalize_meta_campaign_id("120330123456789012"), "120330123456789012")
        self.assertEqual(normalize_meta_campaign_id("camp_12345"), "12345")

    def test_pg_channel_meta(self) -> None:
        self.assertEqual(pg_channel_for_campaign(channel="meta", external_ref="120330123456789012"), "meta")
        self.assertEqual(pg_channel_for_campaign(channel="ads", external_ref="120330123456789012"), "meta")
        self.assertIsNone(pg_channel_for_campaign(channel="email", external_ref=""))

    @patch("ptt_agency.hub_campaign_sync._client_exists", return_value=True)
    def test_campaign_sync_payload(self, _mock_client: MagicMock) -> None:
        payload = campaign_sync_payload(
            {
                "id": 42,
                "name": "Demo Campaign",
                "channel": "meta",
                "external_ref": "120330123456789012",
                "agency_client_id": "550e8400-e29b-41d4-a716-446655440000",
                "target_cpl_vnd": 80000,
                "active": 1,
                "code": "DEMO",
                "utm_campaign": "demo_q2",
            }
        )
        assert payload is not None
        self.assertEqual(payload["hub_campaign_id"], 42)
        self.assertEqual(payload["external_campaign_id"], "120330123456789012")
        self.assertEqual(payload["target_cpl_vnd"], 80000.0)


class TestSyncCampaignRow(unittest.TestCase):
    @patch("ptt_agency.hub_campaign_sync.pg_hub_map_ready", return_value=False)
    def test_not_ready(self, _mock: MagicMock) -> None:
        out = sync_campaign_row({"id": 1})
        self.assertTrue(out.get("skipped"))

    @patch("ptt_agency.hub_campaign_sync._stamp_sqlite_sync")
    @patch("ptt_agency.hub_campaign_sync.upsert_hub_campaign_map")
    @patch("ptt_agency.hub_campaign_sync.campaign_sync_payload")
    @patch("ptt_agency.hub_campaign_sync.pg_hub_map_ready", return_value=True)
    def test_sync_ok(
        self,
        _ready: MagicMock,
        mock_payload: MagicMock,
        mock_upsert: MagicMock,
        _stamp: MagicMock,
    ) -> None:
        mock_payload.return_value = {
            "client_id": "c1",
            "hub_campaign_id": 1,
            "channel": "meta",
            "external_campaign_id": "12345678901",
        }
        mock_upsert.return_value = {"ok": True, "map_id": "m1"}
        out = sync_campaign_row({"id": 1, "agency_client_id": "c1", "external_ref": "12345678901"})
        self.assertTrue(out.get("ok"))


if __name__ == "__main__":
    unittest.main()
