"""Tests for Meta forecast engine (B11)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_meta.forecast import build_forecast, linear_regression, meta_forecast_enabled


class TestForecastConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_FORECAST_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_forecast_enabled())


class TestForecastMath(unittest.TestCase):
    def test_linear_regression_slope(self) -> None:
        points = [(0, 100.0), (1, 110.0), (2, 120.0), (3, 130.0)]
        slope, intercept = linear_regression(points)
        self.assertAlmostEqual(slope, 10.0, places=1)
        self.assertAlmostEqual(intercept, 100.0, places=1)

    def test_build_forecast_projection(self) -> None:
        historical = [
            {"performance_date": "2026-07-17", "value": 100_000},
            {"performance_date": "2026-07-18", "value": 110_000},
            {"performance_date": "2026-07-19", "value": 120_000},
        ]
        out = build_forecast(historical=historical, projection_days=7)
        self.assertEqual(len(out["projection"]), 7)
        self.assertGreater(out["slope"], 0)


if __name__ == "__main__":
    unittest.main()
