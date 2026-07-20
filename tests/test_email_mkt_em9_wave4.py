"""Tests for EM-9 / Wave 4 prod pilot gate helpers."""
from __future__ import annotations

import json
from pathlib import Path

from ptt_crm.phase9_email_wave4_gates import WAVE_GATE_REPORTS, _check_wave_reports, run_gates


def test_check_wave_reports_passes_when_all_ok(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PTT_ARTIFACTS_DIR", str(tmp_path))
    for _, name in WAVE_GATE_REPORTS:
        (tmp_path / name).write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    result = _check_wave_reports()
    assert result["ok"] is True
    assert result["missing"] == []


def test_check_wave_reports_fails_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PTT_ARTIFACTS_DIR", str(tmp_path))
    result = _check_wave_reports()
    assert result["ok"] is False
    assert result["missing"]


def test_run_gates_skips_phase5_when_flagged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PTT_ARTIFACTS_DIR", str(tmp_path))
    monkeypatch.setenv("WAVE4_SKIP_WAVE_REPORTS", "1")
    monkeypatch.setenv("WAVE4_SKIP_PHASE5", "1")
    report = run_gates(refresh_wave=False)
    assert report["ok"] is True
    assert (tmp_path / "phase9-email-wave4-report.json").is_file()
