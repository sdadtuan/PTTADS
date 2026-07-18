"""Tests for Phase 2 ops gate pack."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ptt_crm.phase2_ops_gates import (
    build_signoff_template,
    parse_client_codes,
    run_multi_client_closed_loop,
    run_uat_automated_checks,
)
from ptt_crm.write_soak_evidence import seed_soak_records_for_staging, evaluate_soak_gate


class TestPhase2OpsGates(unittest.TestCase):
    def test_parse_client_codes(self) -> None:
        with patch.dict("os.environ", {"PTT_CLOSED_LOOP_CLIENT_CODES": "A,B,C"}, clear=False):
            codes = parse_client_codes()
        self.assertEqual(codes, ["A", "B", "C"])

    @patch("ptt_agency.closed_loop_pilot.run_closed_loop_pilot")
    def test_multi_client_closed_loop(self, mock_pilot: MagicMock) -> None:
        mock_pilot.return_value = {"ok": True, "client_code": "X"}
        with patch.dict("os.environ", {"PTT_CLOSED_LOOP_MIN_CLIENTS": "3"}, clear=False):
            out = run_multi_client_closed_loop(["A", "B", "C"], run_sync=False)
        self.assertTrue(out["ok"])
        self.assertEqual(mock_pilot.call_count, 3)

    @patch("ptt_agency.closed_loop_pilot.run_closed_loop_pilot")
    def test_multi_client_fail(self, mock_pilot: MagicMock) -> None:
        mock_pilot.side_effect = [{"ok": True}, {"ok": False}, {"ok": True}]
        with patch.dict("os.environ", {"PTT_CLOSED_LOOP_MIN_CLIENTS": "3"}, clear=False):
            out = run_multi_client_closed_loop(["A", "B", "C"], run_sync=False)
        self.assertFalse(out["ok"])
        self.assertIn("B", out["failed_clients"])

    def test_signoff_template_w5_deferred(self) -> None:
        tpl = build_signoff_template(gate_report={"ok": True, "failed_steps": []})
        self.assertEqual(tpl["w5_prod_create"]["status"], "deferred")

    @patch("ptt_crm.phase2_ops_gates.pg_v3_ready", create=True)
    def test_uat_automated_subset(self, _v3: MagicMock) -> None:
        with patch("ptt_crm.staging_write_pilot.fetch_nest_health", return_value={"ok": True, "body": {"leads_write_enabled": True}}):
            with patch("ptt_meta.insights_sync.pg_meta_insights_ready", return_value=True):
                with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                    with patch("ptt_crm.pg_schema.pg_v3_ready", return_value=True):
                        with patch("ptt_crm.pg_schema.pg_domain_events_idempotency_ready", return_value=True):
                            out = run_uat_automated_checks()
        self.assertIn("steps", out)


class TestSoakSeed(unittest.TestCase):
    def test_seed_soak_passes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "soak.jsonl"
            out = seed_soak_records_for_staging(path=log, sample_count=25)
            self.assertTrue(out.get("ok"), out)
            gate = evaluate_soak_gate(path=log)
            self.assertTrue(gate.get("ok"), gate)


if __name__ == "__main__":
    unittest.main()
