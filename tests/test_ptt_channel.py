"""Tests for ptt_channel multi-channel adapter layer."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_channel.adapters.meta import MetaAdapter
from ptt_channel.adapters.zalo import ZaloAdapter
from ptt_channel.enums import ChannelCode, StandardEventName
from ptt_channel.registry import ChannelAdapterRegistry, register_default_adapters

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "channels"


class TestChannelAdapterRegistry(unittest.TestCase):
    def test_default_adapters_registered(self) -> None:
        reg = ChannelAdapterRegistry()
        register_default_adapters(reg)
        self.assertEqual(
            set(reg.list_channels()),
            {ChannelCode.META, ChannelCode.ZALO, ChannelCode.GOOGLE, ChannelCode.EMAIL},
        )

    def test_capabilities_meta(self) -> None:
        reg = ChannelAdapterRegistry()
        register_default_adapters(reg)
        caps = reg.get(ChannelCode.META).capabilities
        self.assertTrue(caps.supports_webhooks)
        self.assertTrue(caps.supports_lead_ingest)


class TestMetaAdapterWebhook(unittest.TestCase):
    def test_verify_challenge(self) -> None:
        adapter = MetaAdapter()
        with patch("ptt_channel.adapters.meta.facebook_verify_token", return_value="test-token"):
            result = adapter.parse_webhook(
                {},
                b"",
                {"hub.mode": "subscribe", "hub.verify_token": "test-token", "hub.challenge": "999"},
            )
        self.assertTrue(result.verified)
        self.assertEqual(result.challenge_response, "999")

    def test_leadgen_payload_normalized(self) -> None:
        payload = json.loads((FIXTURES / "meta" / "webhook_leadgen.json").read_text(encoding="utf-8"))
        body = json.dumps(payload).encode("utf-8")
        adapter = MetaAdapter()
        with patch("ptt_channel.adapters.meta.verify_facebook_signature", return_value=True):
            with patch("ptt_channel.adapters.meta.parse_facebook_webhook") as mock_parse:
                mock_parse.return_value = [
                    {
                        "full_name": "Test User",
                        "phone": "0901111222",
                        "email": "a@example.com",
                        "source": "facebook",
                        "meta": {"facebook_leadgen_id": "9876543210"},
                    }
                ]
                result = adapter.parse_webhook({}, body, client_id="client-1")
        self.assertTrue(result.verified)
        self.assertEqual(len(result.leads), 1)
        lead = result.leads[0]
        self.assertEqual(lead.channel, ChannelCode.META)
        self.assertEqual(lead.client_id, "client-1")
        self.assertEqual(lead.external_lead_id, "9876543210")
        d = lead.to_dict()
        self.assertEqual(d["channel"], "meta")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].event_name, StandardEventName.LEAD)


class TestZaloAdapterWebhook(unittest.TestCase):
    def test_zalo_lead_normalized(self) -> None:
        payload = json.loads((FIXTURES / "zalo" / "webhook_lead.json").read_text(encoding="utf-8"))
        body = json.dumps(payload).encode("utf-8")
        adapter = ZaloAdapter()
        with patch("ptt_channel.adapters.zalo.verify_zalo_signature", return_value=True):
            result = adapter.parse_webhook({}, body, client_id="client-zalo")
        self.assertTrue(result.verified)
        self.assertGreaterEqual(len(result.leads), 1)
        self.assertEqual(result.leads[0].channel, ChannelCode.ZALO)


class TestSchemasExist(unittest.TestCase):
    def test_schema_files(self) -> None:
        root = Path(__file__).resolve().parents[1] / "schemas" / "channel"
        for name in (
            "normalized-lead.schema.json",
            "normalized-event.schema.json",
            "normalized-daily-performance.schema.json",
            "webhook-ingest.openapi.yaml",
        ):
            self.assertTrue((root / name).is_file(), msg=name)


if __name__ == "__main__":
    unittest.main()
