"""Unit tests for Hub/SOP PG migration paths (Phase 3 Track D)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestHubPgRead(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_HUB_READ_SOURCE": "0", "PTT_HUB_PG_PRIMARY": "0"}, clear=False)
    @patch("ptt_crm.hub_pg_read.pg_hub_campaigns_ready", return_value=True)
    def test_list_returns_empty_when_flag_off(self, _ready: MagicMock) -> None:
        from ptt_crm.hub_pg_read import list_hub_campaigns

        self.assertEqual(list_hub_campaigns(), [])

    @patch.dict(os.environ, {"PTT_HUB_READ_SOURCE": "1"}, clear=False)
    @patch("ptt_crm.hub_pg_read.pg_connection")
    @patch("ptt_crm.hub_pg_read.pg_hub_campaigns_ready", return_value=True)
    def test_list_maps_sqlite_id(self, _ready: MagicMock, mock_pg: MagicMock) -> None:
        from datetime import datetime, timezone

        from ptt_crm.hub_pg_read import list_hub_campaigns

        cur = MagicMock()
        cur.description = [
            ("id",),
            ("sqlite_campaign_id",),
            ("code",),
            ("name",),
            ("channel",),
            ("external_ref",),
            ("utm_campaign",),
            ("notes",),
            ("active",),
            ("created_at",),
            ("updated_at",),
        ]
        now = datetime.now(timezone.utc)
        cur.fetchall.return_value = [
            (10, 42, "DEMO", "Demo Camp", "meta", "ext1", "utm1", "", True, now, now),
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        rows = list_hub_campaigns(active_only=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], 42)
        self.assertEqual(rows[0]["pg_id"], 10)
        self.assertEqual(rows[0]["channel"], "meta")


class TestHubPgWrite(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_HUB_PG_PRIMARY": "0"}, clear=False)
    @patch("ptt_crm.hub_pg_write.pg_hub_campaigns_ready", return_value=True)
    def test_upsert_skipped_when_flag_off(self, _ready: MagicMock) -> None:
        from ptt_crm.hub_pg_write import upsert_hub_campaign_from_sqlite

        self.assertIsNone(upsert_hub_campaign_from_sqlite({"id": 1, "name": "x"}))

    @patch.dict(os.environ, {"PTT_HUB_PG_PRIMARY": "1"}, clear=False)
    @patch("ptt_crm.hub_pg_write.pg_connection")
    @patch("ptt_crm.hub_pg_write.pg_hub_campaigns_ready", return_value=True)
    def test_upsert_returns_pg_id(self, _ready: MagicMock, mock_pg: MagicMock) -> None:
        from ptt_crm.hub_pg_write import upsert_hub_campaign_from_sqlite

        cur = MagicMock()
        cur.fetchone.return_value = (99, 7)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        out = upsert_hub_campaign_from_sqlite(
            {
                "id": 7,
                "code": "C1",
                "name": "Camp",
                "channel": "meta",
                "external_ref": "123",
                "utm_campaign": "u",
                "notes": "",
                "active": 1,
            }
        )
        self.assertEqual(out, {"pg_id": 99, "sqlite_campaign_id": 7})


class TestSopPgRead(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_SOP_READ_SOURCE": "0"}, clear=False)
    @patch("ptt_crm.sop_pg_read.pg_sop_ready", return_value=True)
    def test_templates_empty_when_flag_off(self, _ready: MagicMock) -> None:
        from ptt_crm.sop_pg_read import list_sop_templates

        self.assertEqual(list_sop_templates(), [])


class TestLeadShadowSunset(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_LEAD_SHADOW_SYNC": "0"}, clear=False)
    def test_shadow_sync_disabled_by_default(self) -> None:
        from ptt_crm.config import lead_shadow_sync_enabled
        from ptt_crm.lead_shadow_sync import sync_shadow_incremental

        self.assertFalse(lead_shadow_sync_enabled())
        out = sync_shadow_incremental()
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "disabled")


if __name__ == "__main__":
    unittest.main()
