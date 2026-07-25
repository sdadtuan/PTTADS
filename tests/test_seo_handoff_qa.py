"""QA wiring + domain checks for SPEC_UI_UX_SEO_AEO.md §12 (ops-web, no Flask)."""
from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoHandoffQaTests(unittest.TestCase):
    def test_handoff_scripts_exist(self) -> None:
        for rel in (
            "scripts/playwright_ops_seo_handoff_e2e.sh",
            "scripts/seed_ops_seo_handoff_e2e.py",
            "scripts/seo_handoff_gate.sh",
            "services/ops-web/e2e/seo-handoff.spec.ts",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_playwright_spec_covers_s12_items(self) -> None:
        spec = (ROOT / "services/ops-web/e2e/seo-handoff.spec.ts").read_text(encoding="utf-8")
        for fragment in (
            "executive drill-down",
            "client settings",
            "Capture CWV",
            "attribution API",
            "mobile smoke",
            "Gate A",
        ):
            self.assertIn(fragment, spec)

    def test_governance_blocks_publish_without_metadata(self) -> None:
        import os

        from ptt_seo import schema as seo_schema
        from ptt_seo.db import SeoDB
        from ptt_seo.governance import evaluate_content_publish, seed_default_policies
        from ptt_seo.workflow import record_approval

        os.environ["PTT_SEO_GOVERNANCE_ENABLED"] = "1"
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        seo_schema.ensure_schema(conn)
        db = SeoDB(conn, "sqlite")
        seed_default_policies(db)
        cur = conn.execute(
            """
            INSERT INTO seo_content (
                customer_id, title, slug, workflow_status, target_keyword_id,
                brief_json, outline_json, body_html, content_type, intent, funnel_stage,
                created_at, updated_at
            ) VALUES (1, 'Handoff', '/handoff', 'approved', 1, ?, '{}', '<p>x</p>',
                      'blog', '', '', ?, ?)
            """,
            (
                json.dumps(
                    {"primary_topic": "x", "meta_description": "d", "checklist": ["Schema phù hợp"]},
                    ensure_ascii=False,
                ),
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        cid = int(cur.lastrowid)
        for stage in ("seo_review", "aeo_review", "technical_review"):
            record_approval(db, content_id=cid, stage=stage, status="approved")
            db.commit()
        result = evaluate_content_publish(conn, content_id=cid)
        self.assertFalse(result["ok"])
        self.assertTrue(any(v["policy_key"] == "metadata_required" for v in result["violations"]))
        os.environ.pop("PTT_SEO_GOVERNANCE_ENABLED", None)

    def test_attribution_module_importable(self) -> None:
        from ptt_seo import attribution

        self.assertTrue(callable(getattr(attribution, "organic_attribution_summary", None)))


if __name__ == "__main__":
    unittest.main()
