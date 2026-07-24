"""Tests for Meta statistical anomaly (B11)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_meta.anomaly_stat import (
    compute_zscore,
    detect_campaign_stat_anomalies,
    meta_anomaly_stat_enabled,
)


class TestAnomalyStatConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_ANOMALY_STAT_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_anomaly_stat_enabled())


class TestAnomalyStatMath(unittest.TestCase):
    def test_zscore_spike(self) -> None:
        baseline = [100_000, 110_000, 95_000, 105_000, 98_000, 102_000]
        z = compute_zscore(250_000, baseline)
        self.assertIsNotNone(z)
        assert z is not None
        self.assertGreater(z, 2.0)

    def test_detect_spend_zscore(self) -> None:
        items = detect_campaign_stat_anomalies(
            spend_today=300_000,
            leads_today=3,
            spend_history=[100_000, 110_000, 95_000, 105_000, 98_000],
            cpl_history=[50_000, 55_000, 48_000, 52_000],
            zscore_threshold=2.0,
        )
        types = {i["alert_type"] for i in items}
        self.assertIn("spend_zscore", types)


if __name__ == "__main__":
    unittest.main()
