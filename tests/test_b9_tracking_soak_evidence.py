"""Unit tests for B9 tracking soak evidence."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ptt_crm.b9_tracking_soak_evidence import (
    append_soak_record,
    evaluate_soak_gate,
    load_soak_records,
)


class TestB9TrackingSoakEvidence(unittest.TestCase):
    def test_evaluate_fails_without_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            result = evaluate_soak_gate(path=path, required_days=30, min_samples=28)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "no_records")

    def test_evaluate_passes_with_span_and_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            now = datetime.now(timezone.utc)
            for i in range(31):
                ts = (now - timedelta(days=30 - i)).replace(microsecond=0).isoformat()
                append_soak_record(
                    {"recorded_at": ts, "ok": True, "metrics": {"capi_sent_24h": 2}},
                    path=path,
                )
            result = evaluate_soak_gate(path=path, required_days=30, min_samples=28)
            self.assertTrue(result["ok"], msg=json.dumps(result))

    def test_load_soak_records_filters_by_since_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            old = (datetime.now(timezone.utc) - timedelta(days=40)).replace(microsecond=0).isoformat()
            recent = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            path.write_text(
                json.dumps({"recorded_at": old, "ok": True}) + "\n"
                + json.dumps({"recorded_at": recent, "ok": True}) + "\n",
                encoding="utf-8",
            )
            rows = load_soak_records(path=path, since_days=7)
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
