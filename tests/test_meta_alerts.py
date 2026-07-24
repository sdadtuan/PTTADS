"""Tests for Meta alerts engine (B8)."""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch


class TestMetaAlertsConfig(unittest.TestCase):
    def test_alerts_disabled_by_default(self) -> None:
        from ptt_meta.alerts import meta_alerts_enabled

        with patch.dict(os.environ, {"PTT_META_ALERTS_ENABLED": "0"}, clear=False):
            self.assertFalse(meta_alerts_enabled())

    def test_alerts_enabled_truthy(self) -> None:
        from ptt_meta.alerts import meta_alerts_enabled

        with patch.dict(os.environ, {"PTT_META_ALERTS_ENABLED": "1"}, clear=False):
            self.assertTrue(meta_alerts_enabled())


class TestMetaAlertsEval(unittest.TestCase):
    @patch("ptt_meta.alerts.pg_meta_alerts_ready", return_value=True)
    @patch("ptt_meta.alerts.meta_alerts_enabled", return_value=False)
    def test_eval_skipped_when_disabled(self, _enabled: MagicMock, _ready: MagicMock) -> None:
        from ptt_meta.alerts import evaluate_meta_alerts

        out = evaluate_meta_alerts(client_id="550e8400-e29b-41d4-a716-446655440000")
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("skipped"))

    @patch("ptt_meta.alerts.pg_meta_alerts_ready", return_value=False)
    @patch("ptt_meta.alerts.meta_alerts_enabled", return_value=True)
    def test_eval_not_ready(self, _enabled: MagicMock, _ready: MagicMock) -> None:
        from ptt_meta.alerts import evaluate_meta_alerts

        out = evaluate_meta_alerts()
        self.assertFalse(out["ok"])
        self.assertEqual(out.get("error"), "meta_alerts_table_not_ready")

    @patch("ptt_meta.alerts._insert_alert", return_value=True)
    @patch("ptt_meta.alerts.pg_connection")
    @patch("ptt_meta.alerts.pg_meta_alerts_ready", return_value=True)
    @patch("ptt_meta.alerts.meta_alerts_enabled", return_value=True)
    def test_cpl_high_dedupe_insert(
        self,
        _enabled: MagicMock,
        _ready: MagicMock,
        mock_pg: MagicMock,
        mock_insert: MagicMock,
    ) -> None:
        from ptt_meta.alerts import evaluate_meta_alerts

        cur = MagicMock()
        cur.fetchall.side_effect = [
            [
                (
                    "550e8400-e29b-41d4-a716-446655440000",
                    "camp_1",
                    200_000.0,
                    1,
                    100_000,
                )
            ],
            [],
            [],
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        out = evaluate_meta_alerts(
            client_id="550e8400-e29b-41d4-a716-446655440000",
            performance_date=date(2026, 7, 21),
        )
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out.get("alerts_created", 0), 1)
        mock_insert.assert_called()
        dedupe = mock_insert.call_args.kwargs.get("dedupe_key") or mock_insert.call_args[1].get("dedupe_key")
        if dedupe is None and mock_insert.call_args.kwargs:
            dedupe = mock_insert.call_args.kwargs["dedupe_key"]
        self.assertIn("cpl_high:", str(dedupe))


class TestMetaAlertsDedupeKey(unittest.TestCase):
    def test_dedupe_key_format(self) -> None:
        from ptt_meta.alerts import _dedupe_key

        key = _dedupe_key("sync_failed", "abc", "act_1", date(2026, 7, 21))
        self.assertEqual(key, "sync_failed:abc:act_1:2026-07-21")


if __name__ == "__main__":
    unittest.main()
