"""Test rubric chấm điểm lead D1–D6."""
from __future__ import annotations

import unittest

from crm_lead_scoring import score_lead
from crm_lead_scoring_rubric import (
    DEFAULT_LEAD_SCORING_RUBRIC,
    default_scoring_rubric,
    normalize_scoring_rubric,
    score_lead_rubric,
)
from crm_lead_rules import fetch_lead_config, save_lead_config

TS = "2026-05-30 10:00:00"


class LeadScoringRubricTests(unittest.TestCase):
    def test_default_rubric_has_six_groups(self) -> None:
        rubric = default_scoring_rubric()
        self.assertEqual(len(rubric["groups"]), 6)
        total_max = sum(int(g["max_points"]) for g in rubric["groups"])
        self.assertEqual(total_max, 100)

    def test_d1_info_completeness(self) -> None:
        rubric = default_scoring_rubric()
        ctx = {
            "source": "referral",
            "phone": "0901234567",
            "email": "a@test.com",
            "full_name": "Nguyen Van A",
            "product_interest": "Can ho A",
            "need": "Ngan sach 3.5 ty",
            "meta": {"budget_text": "3.5 tỷ"},
            "activities": [],
            "activity_count": 0,
        }
        out = score_lead_rubric(rubric, ctx)
        d1 = [b for b in out["breakdown"] if b.get("group_code") == "D1"]
        self.assertGreater(sum(b["points"] for b in d1), 0)

    def test_d4_referral_source(self) -> None:
        rubric = default_scoring_rubric()
        ctx = {
            "source": "referral",
            "phone": "",
            "email": "",
            "need": "",
            "product_interest": "",
            "full_name": "",
            "meta": {},
            "activities": [],
            "activity_count": 0,
        }
        out = score_lead_rubric(rubric, ctx)
        d4 = next(b for b in out["breakdown"] if b["id"] == "d4_source")
        self.assertEqual(d4["points"], 15)

    def test_score_lead_uses_rubric(self) -> None:
        low = score_lead(
            None,
            source="other",
            phone="",
            email="",
            need="",
            product_interest="",
            full_name="",
        )
        high = score_lead(
            None,
            source="referral",
            phone="0909999888",
            email="vip@test.com",
            need="Muon mua ngay trong tuan nay, ngan sach 3.5 ty",
            product_interest="Can ho cao cap",
            full_name="Tran VIP",
            meta={
                "budget_text": "3.5 tỷ",
                "budget_vs_price_pct": 100,
                "site_time_minutes": 12,
                "web_behavior_tier": 6,
                "purchase_timeline_tier": 5,
                "urgency_reason_tier": 8,
                "last_interaction_tier": 6,
                "age": 35,
                "occupation_tier": 5,
            },
            activity_count=6,
        )
        self.assertLess(low["score"], high["score"])
        self.assertGreaterEqual(high["score"], 50)
        self.assertTrue(high.get("rubric"))

    def test_save_scoring_rubric_config(self) -> None:
        import sqlite3

        from crm_lead_store import ensure_lead_schema

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_lead_schema(conn)
        saved = save_lead_config(
            conn,
            config={"scoring_rubric": DEFAULT_LEAD_SCORING_RUBRIC, "scoring_mode": "rubric"},
            updated_by="test",
            ts=TS,
        )
        self.assertEqual(len(saved["scoring_rubric"]["groups"]), 6)
        cfg = fetch_lead_config(conn)
        self.assertEqual(cfg["scoring_mode"], "rubric")

    def test_normalize_rejects_empty_groups(self) -> None:
        with self.assertRaises(ValueError):
            normalize_scoring_rubric({"groups": []})


if __name__ == "__main__":
    unittest.main()
