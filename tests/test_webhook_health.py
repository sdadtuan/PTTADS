"""Tests for webhook health monitor (PROD-H-MON)."""
from __future__ import annotations

import unittest


class TestWebhookHealth(unittest.TestCase):
    def test_evaluate_skips_when_ok(self) -> None:
        from ptt_crm.webhook_health import evaluate_webhook_health

        out = evaluate_webhook_health(dry_run=True)
        self.assertIn("ok", out)

    def test_webhook_health_enabled_default_off(self) -> None:
        from ptt_crm.webhook_health import webhook_health_enabled

        self.assertFalse(webhook_health_enabled())


if __name__ == "__main__":
    unittest.main()
