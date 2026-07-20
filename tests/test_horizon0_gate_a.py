#!/usr/bin/env python3
"""Unit tests — Horizon 0 Gate A aggregator."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.horizon0_gate_a_signoff import bootstrap_soak_records, merge_signoff_artifacts


class Horizon0BootstrapTests(unittest.TestCase):
    def test_bootstrap_soak_skipped_by_default(self) -> None:
        with patch.dict(os.environ, {"HORIZON0_BOOTSTRAP_SOAK": "0"}, clear=False):
            out = bootstrap_soak_records(days=7)
        self.assertTrue(out.get("skipped"))

    def test_bootstrap_soak_writes_seven_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            with patch.dict(
                os.environ,
                {
                    "HORIZON0_BOOTSTRAP_SOAK": "1",
                    "PTT_ARTIFACTS_DIR": str(art),
                    "EM5_SKIP_SOAK": "0",
                    "PHASE5_SKIP_SOAK": "0",
                },
                clear=False,
            ):
                out = bootstrap_soak_records(days=7)
                self.assertTrue(out["ok"])
                seo_lines = (art / "phase5-soak-evidence.jsonl").read_text().strip().splitlines()
                email_lines = (art / "em5-soak-evidence.jsonl").read_text().strip().splitlines()
                self.assertEqual(len(seo_lines), 8)
                self.assertEqual(len(email_lines), 8)


class Horizon0SignoffMergeTests(unittest.TestCase):
    def test_merge_signoff_with_gate_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            (art / "phase5-gate-report.json").write_text(json.dumps({"ok": True, "checks": [{"id": "P5-G01", "ok": True}]}))
            (art / "phase5-email-pilot-gate-report.json").write_text(
                json.dumps({"ok": True, "checks": [{"id": "EM5-G01", "ok": True}, {"id": "EM5-G05", "ok": True}]})
            )
            (art / "phase5-delivery-admin-retirement-gate-report.json").write_text(json.dumps({"ok": True}))
            with patch.dict(
                os.environ,
                {
                    "PTT_ARTIFACTS_DIR": str(art),
                    "HORIZON0_BOOTSTRAP_SOAK": "1",
                    "EM5_SKIP_SOAK": "0",
                    "PHASE5_SKIP_SOAK": "0",
                },
                clear=False,
            ):
                bootstrap_soak_records(days=7)
                horizon = merge_signoff_artifacts()
            self.assertTrue(horizon.get("seo_gate_ok"))
            self.assertTrue(horizon.get("email_gate_ok"))
            self.assertTrue(horizon.get("seo_soak_ok"))
            self.assertTrue(horizon.get("email_soak_ok"))


if __name__ == "__main__":
    unittest.main()
