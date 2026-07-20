"""Tests for EM-5 email soak + gate helpers."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ptt_crm.phase5_email_soak_evidence import evaluate_soak_gate, load_soak_records


def test_evaluate_soak_gate_passes_with_enough_samples(tmp_path: Path, monkeypatch) -> None:
    log = tmp_path / "soak.jsonl"
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(8):
        ts = (now - timedelta(days=7 - i)).replace(microsecond=0).isoformat()
        rows.append({"recorded_at": ts, "ok": True, "metrics": {"workspaces": 1}})
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setenv("PTT_EM5_SOAK_DAYS", "7")
    monkeypatch.setenv("PTT_EM5_SOAK_MIN_SAMPLES", "7")
    result = evaluate_soak_gate(path=log, required_days=7, min_samples=7)
    assert result["ok"] is True
    assert result["sample_count"] >= 7


def test_evaluate_soak_gate_fails_without_records(tmp_path: Path) -> None:
    log = tmp_path / "empty.jsonl"
    log.write_text("", encoding="utf-8")
    result = evaluate_soak_gate(path=log, required_days=7, min_samples=7)
    assert result["ok"] is False
    assert result["error"] == "no_records"


def test_load_soak_records_skips_invalid_lines(tmp_path: Path) -> None:
    log = tmp_path / "mixed.jsonl"
    log.write_text('{"recorded_at":"2026-07-19T00:00:00+00:00","ok":true}\nnot-json\n', encoding="utf-8")
    rows = load_soak_records(path=log)
    assert len(rows) == 1
