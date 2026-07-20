"""Tests for SEO/AEO Phase 5B — Experimentation."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest
from datetime import date, timedelta

from ptt_seo import schema as seo_schema
from ptt_seo.db import SeoDB
from ptt_seo.experimentation import (
    create_experiment,
    list_experiments,
    record_decision,
    summarize_uplift,
    transition_experiment,
    upsert_observation,
)


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


class ExperimentationTests(unittest.TestCase):
    def test_create_and_list(self) -> None:
        db = _mem_db()
        item = create_experiment(db, 1, {"title": "Title test", "hypothesis": "H1", "target_url": "/a"})
        self.assertGreater(item["id"], 0)
        rows = list_experiments(db, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "draft")

    def test_transition_and_decision(self) -> None:
        db = _mem_db()
        item = create_experiment(db, 1, {"title": "Exp 2", "target_url": "/page"})
        eid = int(item["id"])
        transition_experiment(db, eid, "running")
        finished = record_decision(db, eid, decision="ship", rationale="Winner", decided_by="tester")
        self.assertEqual(finished["status"], "completed")
        self.assertTrue(finished["decisions"])

    def test_pull_gsc_metrics(self) -> None:
        db = _mem_db()
        item = create_experiment(db, 1, {"title": "GSC exp", "target_url": "/blog/x"})
        eid = int(item["id"])
        d = date.today().isoformat()
        db.execute(
            """

            INSERT INTO seo_gsc_daily_stats (
                customer_id, stat_date, query, page, clicks, impressions, created_at
            ) VALUES (1, ?, '', '/blog/x', 10, 100, datetime('now'))
            """,
            (d,),
        )
        db.commit()
        from ptt_seo.experimentation import pull_gsc_metrics

        count = pull_gsc_metrics(db, eid, date_from=d, date_to=d)
        self.assertGreaterEqual(count, 2)

    def test_uplift_summary(self) -> None:
        db = _mem_db()
        item = create_experiment(db, 1, {"title": "Uplift exp", "target_url": "/u"})
        eid = int(item["id"])
        upsert_observation(
            db, eid, variant_key="control", metric_date="2026-07-01", metric_name="clicks", metric_value=100
        )
        upsert_observation(
            db, eid, variant_key="variant_a", metric_date="2026-07-01", metric_name="clicks", metric_value=120
        )
        detail = list_experiments(db, 1)[0]
        self.assertEqual(detail["uplift_pct"], 20.0)
        self.assertEqual(detail["uplift_label"], "+20.0%")
        full = summarize_uplift(
            [
                {"variant_key": "control", "metric_name": "clicks", "metric_value": 100},
                {"variant_key": "variant_a", "metric_name": "clicks", "metric_value": 120},
            ]
        )
        self.assertEqual(full["uplift_pct"], 20.0)


if __name__ == "__main__":
    unittest.main()
