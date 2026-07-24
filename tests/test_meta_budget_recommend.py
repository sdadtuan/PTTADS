"""Tests for Meta budget recommendations (B10)."""
from __future__ import annotations

import unittest

from ptt_meta.budget_recommend import recommend_budget_change


class TestBudgetRecommendLogic(unittest.TestCase):
    def test_decrease_when_cpl_over_target(self) -> None:
        rec = recommend_budget_change(
            avg_daily_spend=1_000_000,
            cpl=150_000,
            target_cpl=100_000,
            leads=3,
            roas=1.5,
            decrease_pct=15,
            increase_pct=10,
            cpl_over_ratio=1.15,
            cpl_under_ratio=0.85,
        )
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertEqual(rec["recommendation_type"], "decrease_budget")
        self.assertEqual(rec["suggested_daily_budget_vnd"], 850_000)
        self.assertEqual(rec["write_request"]["change_type"], "daily_budget")

    def test_increase_when_cpl_under_target(self) -> None:
        rec = recommend_budget_change(
            avg_daily_spend=500_000,
            cpl=70_000,
            target_cpl=100_000,
            leads=4,
            roas=2.0,
            decrease_pct=15,
            increase_pct=10,
            cpl_over_ratio=1.15,
            cpl_under_ratio=0.85,
        )
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertEqual(rec["recommendation_type"], "increase_budget")
        self.assertEqual(rec["suggested_daily_budget_vnd"], 550_000)

    def test_no_recommend_without_target(self) -> None:
        rec = recommend_budget_change(
            avg_daily_spend=500_000,
            cpl=70_000,
            target_cpl=None,
            leads=4,
            roas=2.0,
            decrease_pct=15,
            increase_pct=10,
            cpl_over_ratio=1.15,
            cpl_under_ratio=0.85,
        )
        self.assertIsNone(rec)
