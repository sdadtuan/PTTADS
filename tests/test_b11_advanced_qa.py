"""QA helpers for Wave B11 advanced."""
from __future__ import annotations

import unittest


class TestB11AdvancedQa(unittest.TestCase):
    def test_anomaly_stat_types_distinct(self) -> None:
        from ptt_meta.anomaly import ANOMALY_TYPES
        from ptt_meta.anomaly_stat import STAT_ANOMALY_TYPES

        self.assertFalse(ANOMALY_TYPES & STAT_ANOMALY_TYPES)

    def test_forecast_projection_days_default(self) -> None:
        from ptt_meta.forecast import build_forecast

        out = build_forecast(
            historical=[
                {"performance_date": "2026-07-17", "value": 100},
                {"performance_date": "2026-07-18", "value": 110},
                {"performance_date": "2026-07-19", "value": 120},
            ]
        )
        self.assertEqual(len(out["projection"]), 7)


if __name__ == "__main__":
    unittest.main()
