"""Tests for Phase 5 Flask retirement gates."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class Phase5FlaskRetirementGatesTest(unittest.TestCase):
    def test_run_gates_with_skip_prior(self) -> None:
        env = {
            **os.environ,
            "PTT_LEADS_WRITE_SOURCE": "pg",
            "PTT_LEAD_INGEST_RULES_SOURCE": "pg",
            "PTT_WEBHOOKS_FLASK_FALLBACK": "0",
            "PTT_WEBHOOKS_NEST_META": "1",
            "PTT_PORTAL_SEO_ENABLED": "1",
            "PTT_FLASK_MONOLITH_MODE": "retired",
            "PHASE5_EXPECT_FLASK_MODE": "retired",
            "PHASE5_SKIP_PRIOR_GATES": "1",
            "PTT_ARTIFACTS_DIR": str(ROOT / ".local-dev"),
        }
        with patch.dict(os.environ, env, clear=False):
            from ptt_crm.phase5_flask_retirement_gates import run_gates

            report = run_gates()
        self.assertIn("checks", report)
        self.assertTrue(report.get("ok"), report.get("failed_ids"))
        dest = ROOT / ".local-dev" / "phase5-flask-retirement-gate-report.json"
        self.assertTrue(dest.is_file())
        data = json.loads(dest.read_text(encoding="utf-8"))
        self.assertTrue(data.get("ok"))


if __name__ == "__main__":
    unittest.main()
