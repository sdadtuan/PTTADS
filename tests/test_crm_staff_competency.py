"""Test chấm điểm năng lực nhân viên."""
from __future__ import annotations

import sqlite3
import unittest

from crm_staff_competency import (
    DEFAULT_COMPETENCY_CLASSIFICATION,
    DEFAULT_COMPETENCY_GROUPS,
    band_matches_value,
    classify_competency_score,
    default_competency_config,
    normalize_competency_config,
    score_metric_value,
    score_staff_competency,
)
from crm_staff_settings import fetch_staff_config, save_staff_config

TS = "2026-05-30 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


class StaffCompetencyTests(unittest.TestCase):
    def test_default_config_structure(self) -> None:
        cfg = default_competency_config()
        self.assertEqual(len(cfg["groups"]), 3)
        total_crit = sum(len(g["criteria"]) for g in cfg["groups"])
        self.assertEqual(total_crit, 8)
        self.assertEqual(len(cfg["classification"]), 4)

    def test_a1_close_rate_bands(self) -> None:
        a1 = DEFAULT_COMPETENCY_GROUPS[0]["criteria"][0]
        self.assertEqual(score_metric_value(40, a1), 20)
        self.assertEqual(score_metric_value(30, a1), 17)
        self.assertEqual(score_metric_value(2, a1), 0)

    def test_b1_response_lower_is_better(self) -> None:
        b1 = DEFAULT_COMPETENCY_GROUPS[1]["criteria"][0]
        self.assertEqual(score_metric_value(1, b1), 10)
        self.assertEqual(score_metric_value(20, b1), 0)

    def test_classify_score(self) -> None:
        self.assertEqual(classify_competency_score(90, DEFAULT_COMPETENCY_CLASSIFICATION), "s")
        self.assertEqual(classify_competency_score(70, DEFAULT_COMPETENCY_CLASSIFICATION), "a")
        self.assertEqual(classify_competency_score(50, DEFAULT_COMPETENCY_CLASSIFICATION), "b")
        self.assertEqual(classify_competency_score(30, DEFAULT_COMPETENCY_CLASSIFICATION), "c")

    def test_score_staff_competency_full(self) -> None:
        metrics = {
            "close_rate_pct": 40,
            "kpi_achievement_pct": 210,
            "avg_deal_value_billion": 9,
            "avg_response_minutes": 1,
            "lead_coverage_pct": 100,
            "appointment_conversion_pct": 65,
            "customer_rating": 9.6,
            "referrals_per_month": 7,
        }
        out = score_staff_competency(metrics)
        self.assertEqual(out["total_score"], 100)
        self.assertEqual(out["level_id"], "s")
        self.assertEqual(len(out["breakdown"]), 8)

    def test_band_exclusive_min(self) -> None:
        band = {"min_value": 35, "min_exclusive": True, "max_value": None, "max_exclusive": False}
        self.assertFalse(band_matches_value(35, band))
        self.assertTrue(band_matches_value(35.1, band))

    def test_save_competency_config(self) -> None:
        conn = _setup_conn()
        cfg = save_staff_config(
            conn,
            config={"competency": default_competency_config()},
            updated_by="tester",
            ts=TS,
        )
        comp = cfg["competency"]
        self.assertEqual(len(comp["groups"]), 3)
        loaded = fetch_staff_config(conn)
        self.assertEqual(len(loaded["competency"]["classification"]), 4)

    def test_normalize_rejects_overlap_classification(self) -> None:
        raw = default_competency_config()
        raw["classification"] = [
            {"id": "x1", "min_score": 0, "max_score": 60, "level_id": "c", "label": "C"},
            {"id": "x2", "min_score": 50, "max_score": 100, "level_id": "b", "label": "B"},
        ]
        with self.assertRaises(ValueError):
            normalize_competency_config(raw)


if __name__ == "__main__":
    unittest.main()
