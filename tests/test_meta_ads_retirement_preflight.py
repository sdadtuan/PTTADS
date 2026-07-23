#!/usr/bin/env python3
"""Unit tests — Meta Ads retirement dry-run preflight (B3.5 / M1-G11)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.meta_ads_retirement_preflight import (
    PLANNED_ENV,
    planned_env_diff,
    retirement_apply_plan,
    run_dry_run_preflight,
    verify_dry_run_artifact,
)


class EnvDiffTests(unittest.TestCase):
    def test_empty_env_pending_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            out = planned_env_diff(env_path=env_path)
            self.assertFalse(out["env_file_exists"])
            self.assertEqual(out["pending_changes"], len(PLANNED_ENV))
            self.assertTrue(out["ok"])
            self.assertFalse(out["already_applied"])

    def test_matching_env_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            lines = [f"{k}={v}" for k, v in PLANNED_ENV.items()]
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            out = planned_env_diff(env_path=env_path)
            self.assertTrue(out["ok"])
            self.assertEqual(out["pending_changes"], 0)
            self.assertTrue(out["already_applied"])


class ApplyPlanTests(unittest.TestCase):
    def test_partial_retire(self) -> None:
        plan = retirement_apply_plan()
        self.assertTrue(plan["partial_retire"])
        self.assertFalse(plan["stop_ptt_service"])
        self.assertIn("PTT_FLASK_META_ADS_ADMIN_RETIRED", plan["env_updates"])


class DryRunPreflightTests(unittest.TestCase):
    def test_run_writes_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            with patch.dict(
                os.environ,
                {
                    "PTT_ARTIFACTS_DIR": str(art),
                    "HORIZON1_SKIP_SOAK": "1",
                    "HORIZON1_SKIP_NEST_SMOKE": "1",
                    "HORIZON1_SKIP_NGINX_REDIRECT_VERIFY": "1",
                    "HORIZON1_SKIP_SYSTEMD": "1",
                },
                clear=False,
            ), patch(
                "ptt_crm.meta_ads_retirement_preflight.run_horizon1_gates",
                return_value={"ok": True, "failed_ids": []},
            ):
                report = run_dry_run_preflight()
            self.assertTrue(report["dry_run"])
            self.assertTrue(report["ok"])
            artifact = art / "horizon1-meta-ads-retirement-dry-run.json"
            self.assertTrue(artifact.is_file())
            data = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])

    def test_verify_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "horizon1-meta-ads-retirement-dry-run.json"
            art.write_text(
                json.dumps({"ok": True, "dry_run": True, "generated_at": "2026-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            out = verify_dry_run_artifact(art)
            self.assertTrue(out["ok"])

    def test_horizon1_gate_m1_g11_skipped(self) -> None:
        from ptt_crm.horizon1_meta_ads_gates import _check_meta_retirement_dry_run

        with patch.dict(os.environ, {"HORIZON1_EXPECT_META_RETIREMENT_DRY_RUN": "0"}, clear=False):
            check = _check_meta_retirement_dry_run()
        self.assertTrue(check["ok"])
        self.assertTrue(check.get("skipped"))

    def test_retirement_dry_run_status(self) -> None:
        from ptt_crm.meta_ads_retirement_preflight import retirement_dry_run_status

        out = retirement_dry_run_status()
        self.assertIn("gate_m1_g11", out)
        self.assertIn("next_apply_command", out)

    def test_horizon1_gate_m1_g11_with_artifact(self) -> None:
        from ptt_crm.horizon1_meta_ads_gates import _check_meta_retirement_dry_run

        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "horizon1-meta-ads-retirement-dry-run.json"
            art.write_text(json.dumps({"ok": True, "dry_run": True}), encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "HORIZON1_EXPECT_META_RETIREMENT_DRY_RUN": "1",
                    "PTT_ARTIFACTS_DIR": str(tmp),
                },
                clear=False,
            ):
                check = _check_meta_retirement_dry_run()
            self.assertTrue(check["ok"])
            self.assertEqual(check["id"], "M1-G11")


if __name__ == "__main__":
    unittest.main()
