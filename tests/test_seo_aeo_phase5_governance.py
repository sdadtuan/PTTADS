"""Tests for SEO/AEO Phase 5A — Governance."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import json
import os
import sqlite3
import unittest
from datetime import datetime

from ptt_seo import schema as seo_schema
from ptt_seo.content import approve_stage, create_content, transition_status
from ptt_seo.db import SeoDB
from ptt_seo.governance import (
    GovernanceBlockError,
    evaluate_content_publish,
    list_policies,
    record_override,
    seed_default_policies,
)
from ptt_seo.workflow import record_approval


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


def _insert_content(conn: SeoDB, *, brief: dict | None = None, status: str = "approved") -> int:
    brief = brief or {
        "primary_topic": "seo local",
        "meta_title": "Meta title",
        "meta_description": "Meta desc",
        "checklist": ["Schema phù hợp"],
    }
    cur = conn.execute(
        """

        INSERT INTO seo_content (
            customer_id, title, slug, workflow_status, target_keyword_id,
            brief_json, outline_json, body_html, content_type, intent, funnel_stage,
            created_at, updated_at
        ) VALUES (1, 'Test', '/test', ?, 1, ?, '{}', '<p>body</p>', 'blog', '', '', ?, ?)
        """,
        (
            status,
            json.dumps(brief, ensure_ascii=False),
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


class GovernancePolicyTests(unittest.TestCase):
    def test_seed_default_policies(self) -> None:
        db = _mem_db()
        seed_default_policies(db)
        pols = list_policies(db, customer_id=1)
        keys = {p["policy_key"] for p in pols}
        self.assertIn("metadata_required", keys)
        self.assertIn("qa_complete", keys)

    def test_blocks_publish_without_meta_title(self) -> None:
        db = _mem_db()
        seed_default_policies(db)
        cid = _insert_content(
            db,
            brief={"primary_topic": "x", "meta_description": "d", "checklist": ["Schema phù hợp"]},
        )
        for stage in ("seo_review", "aeo_review", "technical_review"):
            record_approval(db, content_id=cid, stage=stage, status="approved")
            db.commit()
        result = evaluate_content_publish(db, content_id=cid)
        self.assertFalse(result["ok"])
        self.assertTrue(any(v["policy_key"] == "metadata_required" for v in result["violations"]))


class GovernancePublishGateTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_SEO_GOVERNANCE_ENABLED"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("PTT_SEO_GOVERNANCE_ENABLED", None)

    def test_transition_to_published_blocked(self) -> None:
        db = _mem_db()
        seed_default_policies(db)
        cid = _insert_content(db, brief={"primary_topic": "only topic"})
        with self.assertRaises(GovernanceBlockError) as ctx:
            transition_status(db, cid, "published")
        self.assertIn("Governance block", str(ctx.exception))
        self.assertFalse(ctx.exception.result["ok"])

    def test_override_allows_publish_after_metadata_override(self) -> None:
        db = _mem_db()
        seed_default_policies(db)
        cid = _insert_content(
            db,
            brief={
                "primary_topic": "kw",
                "meta_description": "desc",
                "checklist": ["Schema phù hợp"],
            },
            status="approved",
        )
        for stage in ("seo_review", "aeo_review", "technical_review"):
            record_approval(db, content_id=cid, stage=stage, status="approved")
            db.commit()
        blocked = evaluate_content_publish(db, content_id=cid)
        self.assertFalse(blocked["ok"])
        self.assertTrue(any(v["policy_key"] == "metadata_required" for v in blocked["violations"]))
        record_override(
            db,
            evaluation_id=int(blocked["evaluation_id"]),
            policy_key="metadata_required",
            actor_id="admin@test",
            reason="Pilot UAT exception",
        )
        allowed = evaluate_content_publish(db, content_id=cid)
        self.assertTrue(allowed["ok"])
        item = transition_status(db, cid, "published")
        self.assertEqual(item["workflow_status"], "published")

    def test_client_review_approve_blocked_without_qa(self) -> None:
        db = _mem_db()
        seed_default_policies(db)
        cid = create_content(
            db,
            {
                "customer_id": 1,
                "title": "Client review item",
                "workflow_status": "client_review",
                "brief": {
                    "primary_topic": "kw",
                    "meta_title": "t",
                    "meta_description": "d",
                    "checklist": ["Schema phù hợp"],
                },
            },
        )
        with self.assertRaises(GovernanceBlockError) as ctx:
            approve_stage(db, cid, "client_review", approved=True)
        self.assertIn("Governance block", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
