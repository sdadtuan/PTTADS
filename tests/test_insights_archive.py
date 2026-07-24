"""Tests for B9 insights archive."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.insights_archive import archive_daily_performance, count_archive_candidates


class TestInsightsArchive(unittest.TestCase):
    @patch("ptt_meta.insights_archive.pg_connection")
    @patch("ptt_meta.insights_archive.insights_archive_enabled", return_value=True)
    def test_dry_run_returns_count(self, _enabled: MagicMock, mock_conn: MagicMock) -> None:
        cursor = MagicMock()
        cursor.description = [
            ("client_id",),
            ("channel",),
            ("external_campaign_id",),
            ("performance_date",),
            ("spend",),
            ("leads_crm",),
            ("leads_platform",),
            ("impressions",),
            ("clicks",),
        ]
        cursor.fetchall.return_value = [
            ("c1", "meta", "camp1", "2024-01-01", 100, 1, 1, 10, 1),
        ]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = ctx
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        out = archive_daily_performance(dry_run=True)
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("dry_run"))
        self.assertEqual(out.get("candidate_count"), 1)

    @patch("ptt_meta.insights_archive.pg_connection")
    def test_count_archive_candidates(self, mock_conn: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = (42,)
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=cursor)
        ctx.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = ctx
        mock_conn.return_value.__enter__ = MagicMock(return_value=conn)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        self.assertEqual(count_archive_candidates(), 42)


if __name__ == "__main__":
    unittest.main()
