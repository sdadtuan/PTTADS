"""Tests for ROAS metrics (Phase 2 P2 #11)."""
from __future__ import annotations

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from ptt_agency.performance import compute_roas
from ptt_metrics.compute import compute_roas as compute_roas_metrics
from ptt_metrics.compute import compute_roas_snapshots


class TestComputeRoas(unittest.TestCase):
    def test_roas_formula(self) -> None:
        self.assertEqual(compute_roas(200_000, 100_000), 2.0)
        self.assertEqual(compute_roas_metrics(Decimal("500"), Decimal("250")), 2.0)

    def test_roas_stub_when_no_conversion_value(self) -> None:
        self.assertIsNone(compute_roas(0, 100_000))
        self.assertIsNone(compute_roas(0, 0))

    @patch("ptt_metrics.compute.pg_connection")
    def test_compute_roas_snapshots(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.description = [
            ("id",),
            ("client_id",),
            ("external_campaign_id",),
            ("hub_campaign_map_id",),
            ("spend",),
            ("conversion_value",),
            ("currency",),
        ]
        cur.fetchall.return_value = [
            ("p1", "c1", "camp1", None, Decimal("1000"), Decimal("0"), "VND"),
            ("p2", "c1", "camp2", None, Decimal("2000"), Decimal("4000"), "VND"),
        ]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = compute_roas_snapshots(target_date="2026-07-16", client_id="c1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["roas_snapshots"], 1)
        self.assertEqual(out["roas_stub_count"], 1)


if __name__ == "__main__":
    unittest.main()
