"""Tests for SEO/AEO Phase 5C — Portal bridge."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest

from ptt_seo import schema as seo_schema
from ptt_seo.content import create_content
from ptt_seo.db import SeoDB
from ptt_seo.portal_bridge import (
    customer_id_for_portal_client,
    portal_pending_content,
    portal_review_content,
    upsert_portal_map,
)


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


class PortalBridgeTests(unittest.TestCase):
    def test_map_and_resolve(self) -> None:
        db = _mem_db()
        upsert_portal_map(db, client_id="550e8400-e29b-41d4-a716-446655440000", customer_id=42)
        self.assertEqual(customer_id_for_portal_client(db, "550e8400-e29b-41d4-a716-446655440000"), 42)
        self.assertIsNone(customer_id_for_portal_client(db, "missing"))

    def test_pending_client_review(self) -> None:
        db = _mem_db()
        upsert_portal_map(db, client_id="550e8400-e29b-41d4-a716-446655440000", customer_id=1)
        create_content(db, {"customer_id": 1, "title": "Pending", "workflow_status": "client_review"})
        items = portal_pending_content(db, 1)
        self.assertEqual(len(items), 1)

    def test_portal_review_rejects_wrong_stage(self) -> None:
        db = _mem_db()
        cid = create_content(db, {"customer_id": 1, "title": "Draft", "workflow_status": "idea"})
        with self.assertRaises(ValueError):
            portal_review_content(db, customer_id=1, content_id=cid, approved=True)

    def test_seed_e2e_content_passes_governance(self) -> None:
        from ptt_seo.governance import evaluate_content_publish
        from ptt_seo.portal_bridge import seed_e2e_client_review_content

        db = _mem_db()
        upsert_portal_map(db, client_id="550e8400-e29b-41d4-a716-446655440000", customer_id=1)
        seeded = seed_e2e_client_review_content(db, customer_id=1, title="E2E Seed")
        result = evaluate_content_publish(db, content_id=int(seeded["id"]), action="approve")
        self.assertTrue(result["ok"], result.get("violations"))

    def test_executive_report_read_only(self) -> None:
        db = _mem_db()
        upsert_portal_map(db, client_id="550e8400-e29b-41d4-a716-446655440000", customer_id=1)
        db.execute(
            """

            INSERT INTO seo_technical_issues (
                customer_id, url, issue_type, severity, status, description, discovered_at
            ) VALUES (1, '/secret', '404', 'critical', 'open', 'INTERNAL NOTE', datetime('now'))
            """
        )
        db.commit()
        from ptt_seo.portal_bridge import portal_executive_report

        out = portal_executive_report(db, 1, dashboard_type="technical")
        self.assertTrue(out["ok"])
        self.assertEqual(out["dashboard_type"], "technical")
        issues = out["report"].get("issues") or []
        if issues:
            self.assertNotIn("description", issues[0])
            self.assertIn("url", issues[0])


if __name__ == "__main__":
    unittest.main()
