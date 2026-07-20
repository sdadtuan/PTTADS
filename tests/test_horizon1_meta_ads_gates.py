#!/usr/bin/env python3
"""Unit tests — Horizon 1 Meta Ads migration gates."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from ptt_crm.horizon1_meta_ads_signoff import bootstrap_soak_records, merge_signoff
from ptt_crm.horizon1_meta_ads_soak_evidence import (
    append_soak_record,
    evaluate_soak_gate,
    load_soak_records,
)


class Horizon1SoakTests(unittest.TestCase):
    def test_evaluate_soak_no_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            out = evaluate_soak_gate(path=path)
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "no_records")

    def test_evaluate_soak_span_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            base = datetime.now(timezone.utc)
            for i in range(8):
                ts = (base - timedelta(days=7 - i)).replace(microsecond=0)
                append_soak_record(
                    {"recorded_at": ts.isoformat(), "ok": True, "metrics": {}},
                    path=path,
                )
            out = evaluate_soak_gate(path=path, required_days=7, min_samples=7)
            self.assertTrue(out["ok"])
            self.assertGreaterEqual(out["span_days"], 7.0)

    def test_load_soak_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            append_soak_record({"recorded_at": datetime.now(timezone.utc).isoformat(), "ok": True}, path=path)
            rows = load_soak_records(path=path)
            self.assertEqual(len(rows), 1)


class Horizon1BootstrapTests(unittest.TestCase):
    def test_bootstrap_skipped_by_default(self) -> None:
        with patch.dict(os.environ, {"HORIZON1_BOOTSTRAP_SOAK": "0"}, clear=False):
            out = bootstrap_soak_records(days=7)
        self.assertTrue(out.get("skipped"))

    def test_bootstrap_writes_eight_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            with patch.dict(
                os.environ,
                {"HORIZON1_BOOTSTRAP_SOAK": "1", "PTT_ARTIFACTS_DIR": str(art)},
                clear=False,
            ):
                out = bootstrap_soak_records(days=7)
                self.assertTrue(out["ok"])
                lines = (art / "horizon1-meta-ads-soak-evidence.jsonl").read_text().strip().splitlines()
                self.assertEqual(len(lines), 8)


class Horizon1SignoffMergeTests(unittest.TestCase):
    def test_merge_signoff_with_gate_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            art = root / ".local-dev"
            art.mkdir(parents=True)
            evidence = root / "docs" / "evidence"
            evidence.mkdir(parents=True)
            shutil_copy = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "horizon1-meta-ads-signoff.template.json"
            (evidence / "horizon1-meta-ads-signoff.template.json").write_text(
                shutil_copy.read_text(encoding="utf-8")
            )
            (art / "horizon1-meta-ads-gate-report.json").write_text(
                json.dumps(
                    {
                        "ok": True,
                        "checks": [
                            {"id": "M1-G04", "ok": True},
                            {"id": "M1-G05", "ok": True},
                            {"id": "M1-G06", "ok": True},
                        ],
                    }
                )
            )
            with patch.dict(
                os.environ,
                {"HORIZON1_BOOTSTRAP_SOAK": "1", "PTT_ARTIFACTS_DIR": str(art)},
                clear=False,
            ), patch("ptt_crm.horizon1_meta_ads_signoff.ROOT", root):
                bootstrap_soak_records(days=7)
                merged = merge_signoff()
            self.assertTrue(merged.get("gate_ok"))
            self.assertTrue(merged.get("soak_ok"))


if __name__ == "__main__":
    unittest.main()
