"""Tests for Meta anomaly engine (B10)."""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from ptt_meta.anomaly import (
    compute_spike_pct,
    detect_campaign_anomalies,
    is_median_spike,
    meta_anomaly_enabled,
)


class TestAnomalyConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_ANOMALY_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_anomaly_enabled())


class TestAnomalyMath(unittest.TestCase):
    def test_median_spike_detected(self) -> None:
        ok, base = is_median_spike(200_000, [100_000, 110_000, 95_000, 105_000], 50)
        self.assertTrue(ok)
        self.assertEqual(base, 102_500)

    def test_median_spike_not_detected(self) -> None:
        ok, _ = is_median_spike(120_000, [100_000, 110_000, 95_000, 105_000], 50)
        self.assertFalse(ok)

    def test_compute_spike_pct(self) -> None:
        self.assertAlmostEqual(compute_spike_pct(150_000, 100_000) or 0, 50.0)

    def test_detect_spend_and_roas_low(self) -> None:
        items = detect_campaign_anomalies(
            perf_date=date(2026, 7, 21),
            spend_today=300_000,
            leads_today=2,
            conversion_value_today=600_000,
            spend_history=[100_000, 110_000, 95_000],
            cpl_history=[50_000, 55_000],
            spike_pct=50,
            roas_min_target=3,
            roas_min_spend=100_000,
        )
        types = {i["alert_type"] for i in items}
        self.assertIn("spend_spike", types)
        self.assertIn("roas_low", types)


class TestAnomalyEval(unittest.TestCase):
    @patch("ptt_meta.anomaly.meta_anomaly_enabled", return_value=False)
    def test_eval_skipped_when_disabled(self, _enabled: MagicMock) -> None:
        from ptt_meta.anomaly import evaluate_anomaly_alerts

        out = evaluate_anomaly_alerts()
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("skipped"))
