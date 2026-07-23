#!/usr/bin/env python3
"""Unit tests — Meta Ads retirement prod APPLY (B3.6 / M1-G12)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.meta_ads_retirement_apply import (
    APPLIED_ENV,
    check_apply_prerequisite,
    record_apply_artifact,
    retirement_apply_status,
    verify_apply_artifact,
    verify_env_applied,
)


class ApplyPrerequisiteTests(unittest.TestCase):
    def test_requires_dry_run_or_env_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            with patch.dict(
                os.environ,
                {"PTT_ARTIFACTS_DIR": str(art), "HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED": "0"},
                clear=False,
            ):
                out = check_apply_prerequisite()
            self.assertFalse(out["ok"])

    def test_env_flag_ok(self) -> None:
        with patch.dict(os.environ, {"HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED": "1"}, clear=False):
            out = check_apply_prerequisite()
        self.assertTrue(out["ok"])


class EnvAppliedTests(unittest.TestCase):
    def test_all_keys_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("\n".join(f"{k}={v}" for k, v in APPLIED_ENV.items()) + "\n")
            with patch.dict(os.environ, {"PTT_ENV_FILE": str(env_path)}, clear=False):
                out = verify_env_applied()
            self.assertTrue(out["ok"])


class ApplyArtifactTests(unittest.TestCase):
    def test_record_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            env_path = art / ".env"
            env_path.write_text("\n".join(f"{k}={v}" for k, v in APPLIED_ENV.items()) + "\n")
            dry = art / "horizon1-meta-ads-retirement-dry-run.json"
            dry.write_text(json.dumps({"ok": True, "dry_run": True}), encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "PTT_ARTIFACTS_DIR": str(art),
                    "PTT_ENV_FILE": str(env_path),
                    "HORIZON1_SKIP_NGINX_REDIRECT_VERIFY": "1",
                    "HORIZON1_SKIP_SYSTEMD": "1",
                },
                clear=False,
            ):
                report = record_apply_artifact()
                self.assertTrue(report["ok"])
                verified = verify_apply_artifact()
                self.assertTrue(verified["ok"])
                status = retirement_apply_status()
                self.assertTrue(status["gate_m1_g12"])

    def test_horizon1_gate_m1_g12_skipped(self) -> None:
        from ptt_crm.horizon1_meta_ads_gates import _check_meta_retirement_applied

        with patch.dict(os.environ, {"HORIZON1_EXPECT_META_RETIREMENT_APPLIED": "0"}, clear=False):
            check = _check_meta_retirement_applied()
        self.assertTrue(check["ok"])
        self.assertTrue(check.get("skipped"))

    def test_horizon1_gate_m1_g12_with_artifact(self) -> None:
        from ptt_crm.horizon1_meta_ads_gates import _check_meta_retirement_applied

        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            (art / "horizon1-meta-ads-retirement-applied.json").write_text(
                json.dumps({"ok": True, "applied": True, "generated_at": "2026-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"HORIZON1_EXPECT_META_RETIREMENT_APPLIED": "1", "PTT_ARTIFACTS_DIR": str(art)},
                clear=False,
            ):
                check = _check_meta_retirement_applied()
            self.assertTrue(check["ok"])
            self.assertEqual(check["id"], "M1-G12")


if __name__ == "__main__":
    unittest.main()
