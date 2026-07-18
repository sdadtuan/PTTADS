"""Tests for rollback drill evidence (Phase 2 P1 #9)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_crm.rollback_drill_evidence import (
    ROLLBACK_TARGET_SEC,
    build_drill_report,
    simulate_flag_cutover,
    simulate_flag_rollback,
)


class TestRollbackDrillEvidence(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "PTT_LEADS_WRITE_ENABLED": "0",
            "PTT_LEADS_WRITE_UPSTREAM": "flask",
        },
        clear=False,
    )
    def test_simulate_flag_cutover(self) -> None:
        out = simulate_flag_cutover()
        self.assertTrue(out["ok"])
        self.assertEqual(out["write_upstream"], "nest")

    @patch.dict(
        "os.environ",
        {
            "PTT_LEADS_WRITE_ENABLED": "1",
            "PTT_LEADS_WRITE_UPSTREAM": "nest",
        },
        clear=False,
    )
    def test_simulate_flag_rollback(self) -> None:
        out = simulate_flag_rollback()
        self.assertTrue(out["ok"])
        self.assertEqual(out["write_upstream"], "flask")
        self.assertLessEqual(out["elapsed_sec"], ROLLBACK_TARGET_SEC)

    def test_build_drill_report(self) -> None:
        report = build_drill_report(
            cutover={"ok": True, "elapsed_sec": 0.1},
            rollback={"ok": True, "elapsed_sec": 0.2},
            shell={"ok": True, "rollback_elapsed_sec": 0.2},
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["rollback_within_target"])

    @patch("ptt_crm.rollback_drill_evidence.subprocess.run")
    def test_run_shell_drill(self, mock_run: MagicMock) -> None:
        from ptt_crm.rollback_drill_evidence import run_shell_drill

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Rollback flag simulation: 2s\nTotal drill: 10s\n",
            stderr="",
        )
        out = run_shell_drill()
        self.assertTrue(out["ok"])
        self.assertEqual(out["rollback_elapsed_sec"], 2.0)


if __name__ == "__main__":
    unittest.main()
