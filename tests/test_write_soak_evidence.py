"""Tests for 48h write soak evidence gate."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ptt_crm.write_soak_evidence import (
    append_soak_record,
    evaluate_soak_gate,
    load_soak_records,
)


def _iso(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).replace(microsecond=0).isoformat()


class TestWriteSoakEvidence(unittest.TestCase):
    def test_append_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            append_soak_record({"ok": True, "sample_size": 10, "pg_sqlite_mismatch_count": 0}, path=path)
            recs = load_soak_records(path=path)
            self.assertEqual(len(recs), 1)
            self.assertTrue(recs[0]["ok"])

    def test_gate_fails_without_enough_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "soak.jsonl"
            lines = [
                json.dumps({"recorded_at": _iso(2), "ok": True, "pg_sqlite_mismatch_count": 0}),
                json.dumps({"recorded_at": _iso(0.5), "ok": True, "pg_sqlite_mismatch_count": 0}),
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            gate = evaluate_soak_gate(path=path, required_hours=48, min_ok_samples=2)
            self.assertFalse(gate["ok"])
            self.assertIn("span_hours", gate["reason"])

    def test_gate_passes_synthetic_48h(self) -> None:
        records = []
        for h in range(49, 0, -1):
            records.append(
                {
                    "recorded_at": _iso(float(h)),
                    "ok": True,
                    "pg_sqlite_mismatch_count": 0,
                    "pg_nest_mismatch_count": 0,
                }
            )
        gate = evaluate_soak_gate(records, required_hours=48, min_ok_samples=24)
        self.assertTrue(gate["ok"], msg=gate)

    def test_gate_fails_on_mismatch_sample(self) -> None:
        records = []
        for h in range(49, 0, -1):
            records.append(
                {
                    "recorded_at": _iso(float(h)),
                    "ok": h != 25,
                    "pg_sqlite_mismatch_count": 0 if h != 25 else 1,
                    "pg_nest_mismatch_count": 0,
                }
            )
        gate = evaluate_soak_gate(records, required_hours=48, min_ok_samples=24, max_failures=0)
        self.assertFalse(gate["ok"])


if __name__ == "__main__":
    unittest.main()
