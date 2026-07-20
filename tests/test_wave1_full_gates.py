#!/usr/bin/env python3
"""Unit tests — Wave 1 full CRM gates."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.wave1_full_gates import run_gates
from ptt_crm.wave1_full_signoff import bootstrap_soak_records, merge_signoff_artifacts
from ptt_crm.wave1_leads_soak_evidence import evaluate_soak_gate


class Wave1FullGateTests(unittest.TestCase):
    def test_wave1_full_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_CATALOG_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_CATALOG_RETIRED": "1",
                "WAVE1_EXPECT_CATALOG_OPS_WEB": "1",
                "WAVE1_SKIP_JEST": "1",
                "PTT_CRM_LEADS_LEGACY_UPSTREAM": "nest",
                "PTT_FLASK_CRM_LEADS_LEGACY_RETIRED": "1",
                "WAVE1B_EXPECT_LEADS_LEGACY_NEST": "1",
                "WAVE1B_SKIP_BUILD": "1",
                "PTT_CRM_LEADS_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_LEADS_UI_RETIRED": "1",
                "WAVE1F_EXPECT_LEADS_OPS_WEB": "1",
                "WAVE1F_SKIP_SOAK": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W1F-G01", ids)
        self.assertIn("W1F-G05", ids)

    def test_bootstrap_soak_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            with patch.dict(
                os.environ,
                {
                    "PTT_ARTIFACTS_DIR": str(art),
                    "WAVE1_BOOTSTRAP_SOAK": "1",
                },
                clear=False,
            ):
                out = bootstrap_soak_records(days=7)
            self.assertTrue(out.get("ok"))
            soak = evaluate_soak_gate(path=art / "wave1-leads-soak-evidence.jsonl")
            self.assertTrue(soak.get("ok"), soak)
            self.assertGreaterEqual(soak.get("span_days", 0), 7)


class Wave1FullSignoffTests(unittest.TestCase):
    def test_merge_signoff_with_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            env = {
                "PTT_ARTIFACTS_DIR": str(art),
                "WAVE1_BOOTSTRAP_SOAK": "1",
                "WAVE1F_SKIP_SOAK": "0",
                "PTT_CRM_CATALOG_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_CATALOG_RETIRED": "1",
                "WAVE1_EXPECT_CATALOG_OPS_WEB": "1",
                "WAVE1_SKIP_JEST": "1",
                "PTT_CRM_LEADS_LEGACY_UPSTREAM": "nest",
                "PTT_FLASK_CRM_LEADS_LEGACY_RETIRED": "1",
                "WAVE1B_EXPECT_LEADS_LEGACY_NEST": "1",
                "WAVE1B_SKIP_BUILD": "1",
                "PTT_CRM_LEADS_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_LEADS_UI_RETIRED": "1",
                "WAVE1F_EXPECT_LEADS_OPS_WEB": "1",
            }
            with patch.dict(os.environ, env, clear=False):
                bootstrap_soak_records(days=7)
                run_gates()
                signoff = merge_signoff_artifacts()
            self.assertTrue(signoff.get("ok"))


if __name__ == "__main__":
    unittest.main()
