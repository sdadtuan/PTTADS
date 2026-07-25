"""Zalo form lead poll unit tests (Wave Z2)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ptt_zalo.form_api import normalize_form_lead_row, stub_form_leads
from ptt_zalo.form_lead_poll import form_row_to_legacy_item, poll_zalo_form_leads


class ZaloFormLeadPollTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_ZALO_ADS_STUB"] = "1"
        os.environ["PTT_ZALO_FORM_POLL"] = "1"

    def test_normalize_form_lead_row_reads_answers(self) -> None:
        row = normalize_form_lead_row(
            {
                "form_data_id": "fd_1",
                "answers": [
                    {"key": "phone", "value": "0901111222"},
                    {"key": "full_name", "value": "Nguyen A"},
                ],
            },
            form_id="form_a",
            oa_id="oa_1",
        )
        self.assertEqual(row["phone"], "0901111222")
        self.assertEqual(row["full_name"], "Nguyen A")

    def test_stub_form_leads_returns_one_row(self) -> None:
        rows = stub_form_leads(oa_id="oa_1", form_id="form_a")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["form_data_id"].startswith("stub_"))

    def test_form_row_to_legacy_item_sets_meta(self) -> None:
        item = form_row_to_legacy_item(
            {"form_data_id": "fd_99", "phone": "0909999888", "full_name": "Test"},
            client_id="550e8400-e29b-41d4-a716-446655440000",
            form_id="form_a",
            oa_id="oa_1",
        )
        self.assertEqual(item["meta"]["zalo_lead_id"], "fd_99")
        self.assertEqual(item["meta"]["ingest_channel"], "zalo_form_poll")

    @patch("ptt_zalo.form_lead_poll.ingest_form_lead")
    @patch("ptt_zalo.form_lead_poll.fetch_form_leads")
    @patch("ptt_zalo.form_lead_poll.resolve_zalo_access_token", return_value="tok")
    @patch("ptt_zalo.form_lead_poll.get_cursor", return_value=None)
    @patch("ptt_zalo.form_lead_poll.upsert_cursor")
    @patch("ptt_zalo.form_lead_poll._load_poll_targets")
    @patch("ptt_zalo.form_lead_poll.pg_zalo_leads_ready", return_value=True)
    def test_poll_form_once_path(
        self,
        _ready: MagicMock,
        load_targets: MagicMock,
        _upsert: MagicMock,
        _cursor: MagicMock,
        _token: MagicMock,
        fetch: MagicMock,
        ingest: MagicMock,
    ) -> None:
        load_targets.return_value = [
            {
                "client_id": "550e8400-e29b-41d4-a716-446655440000",
                "oa_id": "oa_1",
                "form_id": "form_a",
                "account": {"external_account_id": "oa_1", "meta": {}},
            }
        ]
        fetch.return_value = (
            [{"form_data_id": "fd_1", "phone": "0901234567", "full_name": "A", "email": ""}],
            None,
        )
        ingest.return_value = {"status": "created_unassigned", "lead_id": 123}
        out = poll_zalo_form_leads(client_id="550e8400-e29b-41d4-a716-446655440000", form_id="form_a")
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("polled"), 1)


if __name__ == "__main__":
    unittest.main()
