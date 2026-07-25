import unittest
from unittest.mock import patch


class TestZaloAlerts(unittest.TestCase):
    @patch("ptt_zalo.alerts.zalo_alerts_enabled", return_value=False)
    def test_skips_when_disabled(self, _enabled):
        from ptt_zalo.alerts import evaluate_zalo_alerts

        out = evaluate_zalo_alerts()
        self.assertTrue(out.get("skipped"))

    @patch("ptt_zalo.alerts.pg_zalo_alerts_ready", return_value=False)
    @patch("ptt_zalo.alerts.zalo_alerts_enabled", return_value=True)
    def test_not_ready(self, _enabled, _ready):
        from ptt_zalo.alerts import evaluate_zalo_alerts

        out = evaluate_zalo_alerts()
        self.assertEqual(out.get("error"), "meta_alerts_table_not_ready")


if __name__ == "__main__":
    unittest.main()
