"""Test hệ thống phân cấp nhân viên — Level S/A/B/C."""
from __future__ import annotations

import sqlite3
import unittest

from crm_staff_levels import (
    DEFAULT_STAFF_LEVELS,
    normalize_sales_level,
    normalize_staff_levels,
    staff_level_labels_map,
)
from crm_staff_settings import fetch_staff_config, save_staff_config


TS = "2026-05-30 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sales_level TEXT NOT NULL DEFAULT ''
        )
        """
    )
    return conn


class StaffLevelsTests(unittest.TestCase):
    def test_default_levels_have_four_tiers(self) -> None:
        levels = normalize_staff_levels(DEFAULT_STAFF_LEVELS)
        self.assertEqual(len(levels), 4)
        ids = [str(x["id"]) for x in levels]
        self.assertEqual(ids, ["s", "a", "b", "c"])

    def test_level_s_content(self) -> None:
        s = next(x for x in DEFAULT_STAFF_LEVELS if x["id"] == "s")
        self.assertIn("CHUYÊN GIA", s["label"])
        self.assertEqual(s["max_leads_min"], 10)
        self.assertEqual(s["max_leads_max"], 15)
        self.assertTrue(any("30%" in q for q in s["quantitative"]))

    def test_normalize_rejects_invalid_lead_range(self) -> None:
        raw = [dict(DEFAULT_STAFF_LEVELS[0])]
        raw[0]["max_leads_min"] = 20
        raw[0]["max_leads_max"] = 5
        with self.assertRaises(ValueError):
            normalize_staff_levels(raw)

    def test_save_and_fetch_staff_config(self) -> None:
        conn = _setup_conn()
        cfg = save_staff_config(
            conn,
            config={"staff_levels": DEFAULT_STAFF_LEVELS},
            updated_by="tester",
            ts=TS,
        )
        self.assertEqual(len(cfg["staff_levels"]), 4)
        loaded = fetch_staff_config(conn)
        self.assertEqual(loaded["staff_levels"][0]["id"], "s")

    def test_normalize_sales_level(self) -> None:
        self.assertEqual(normalize_sales_level("S"), "s")
        self.assertEqual(normalize_sales_level(""), "")
        with self.assertRaises(ValueError):
            normalize_sales_level("x")

    def test_staff_level_labels_map(self) -> None:
        labels = staff_level_labels_map(DEFAULT_STAFF_LEVELS)
        self.assertIn("s", labels)
        self.assertIn("CHUYÊN GIA", labels["s"])


if __name__ == "__main__":
    unittest.main()
