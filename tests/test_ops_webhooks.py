"""Unit tests for B13 Meta ops webhooks."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/channels/meta/webhook_account_disabled.json"


class TestOpsWebhooks(unittest.TestCase):
    def test_parse_account_disabled_fixture(self) -> None:
        from ptt_meta.ops_webhooks import parse_ops_webhook_changes

        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        events = parse_ops_webhook_changes(payload)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "meta_account_disabled")
        self.assertEqual(events[0]["external_account_id"], "act_1234567890")
        self.assertEqual(events[0]["disable_reason"], "policy_violation")

    def test_parse_ad_disapproved(self) -> None:
        from ptt_meta.ops_webhooks import parse_ops_webhook_changes

        payload = {
            "object": "ad_account",
            "entry": [
                {
                    "id": "123",
                    "changes": [
                        {
                            "field": "ads",
                            "value": {
                                "ad_id": "ad_999",
                                "effective_status": "DISAPPROVED",
                                "campaign_id": "camp_1",
                                "account_id": "act_123",
                            },
                        }
                    ],
                }
            ],
        }
        events = parse_ops_webhook_changes(payload)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "ad_disapproved")
        self.assertEqual(events[0]["external_ad_id"], "ad_999")

    def test_dedupe_key_includes_date(self) -> None:
        from datetime import date

        from ptt_meta.ops_webhooks import dedupe_key

        key = dedupe_key("meta_account_disabled", "client-1", None, date(2026, 7, 24))
        self.assertEqual(key, "meta_account_disabled:client-1:_:2026-07-24")

    def test_process_payload_skipped_when_flag_off(self) -> None:
        from ptt_meta.ops_webhooks import process_ops_webhook_payload

        old = os.environ.get("PTT_META_OPS_WEBHOOKS")
        os.environ["PTT_META_OPS_WEBHOOKS"] = "0"
        try:
            out = process_ops_webhook_payload({}, resolve_client_id=lambda _a: "c1")
        finally:
            if old is None:
                os.environ.pop("PTT_META_OPS_WEBHOOKS", None)
            else:
                os.environ["PTT_META_OPS_WEBHOOKS"] = old
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("skipped"))

    def test_process_event_stub(self) -> None:
        from ptt_meta.ops_webhooks import process_ops_webhook_event

        out = process_ops_webhook_event(
            {
                "event_type": "meta_account_disabled",
                "external_account_id": "act_1",
                "disable_reason": "policy_violation",
            },
            client_id="client-1",
            stub=True,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["stub"])
        self.assertIn("disabled", out["message"])


if __name__ == "__main__":
    unittest.main()
