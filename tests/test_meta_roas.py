"""Tests for Meta ROAS engine (B10)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.roas import compute_roas, compute_roas_summary, meta_roas_enabled


class TestRoasMath(unittest.TestCase):
    def test_compute_roas(self) -> None:
        self.assertEqual(compute_roas(300_000, 150_000), 2.0)
        self.assertIsNone(compute_roas(0, 150_000))

    def test_summary_stub(self) -> None:
        summary = compute_roas_summary(total_spend=100_000, total_conversion_value=0)
        self.assertTrue(summary["roas_stub"])
        self.assertIsNone(summary["avg_roas"])


class TestRoasConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_ROAS_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_roas_enabled())

    @patch("ptt_meta.roas.pg_connection")
    def test_fetch_disabled(self, mock_pg: MagicMock) -> None:
        from ptt_meta.roas import fetch_roas_series

        with patch.dict(os.environ, {"PTT_META_ROAS_ENABLED": "0"}, clear=False):
            out = fetch_roas_series()
        self.assertTrue(out.get("disabled"))
        mock_pg.assert_not_called()
