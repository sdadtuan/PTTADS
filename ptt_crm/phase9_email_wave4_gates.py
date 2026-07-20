"""EM-9 / Wave 4 — prod pilot gate pack (Waves 1–3b + EM-5 Gate A)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

WAVE_GATE_REPORTS: tuple[tuple[str, str], ...] = (
    ("em-6", "phase6-email-send-platform-report.json"),
    ("em-7", "phase7-email-wave2-report.json"),
    ("em-8", "phase8-email-wave3-report.json"),
    ("em-8b", "phase8b-email-wave3b-report.json"),
)


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _check_wave_reports() -> dict[str, Any]:
    skip = os.environ.get("WAVE4_SKIP_WAVE_REPORTS", "0") == "1"
    artifacts = _artifacts_dir()
    missing: list[str] = []
    failed: list[str] = []
    found: list[str] = []
    for phase, name in WAVE_GATE_REPORTS:
        path = artifacts / name
        if not path.is_file():
            missing.append(name)
            continue
        found.append(name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("ok"):
                failed.append(name)
        except json.JSONDecodeError:
            failed.append(name)
    ok = skip or (not missing and not failed)
    return {
        "id": "W4-G01",
        "ok": ok,
        "label": "Wave 1–3b gate reports (EM-6..EM-8b)",
        "skipped": skip,
        "found": found,
        "missing": missing,
        "failed": failed,
        "artifacts_dir": str(artifacts),
    }


def _run_phase5_gate() -> dict[str, Any]:
    skip = os.environ.get("WAVE4_SKIP_PHASE5", "0") == "1"
    if skip:
        return {"id": "W4-G02", "ok": True, "label": "EM-5 prod pilot gate", "skipped": True}
    env = {**os.environ, "EM5_SKIP_PRIOR_REPORTS": os.environ.get("EM5_SKIP_PRIOR_REPORTS", "0")}
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.phase5_email_gates"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    report_path = _artifacts_dir() / "phase5-email-pilot-gate-report.json"
    phase5_ok = False
    if report_path.is_file():
        try:
            phase5_ok = json.loads(report_path.read_text(encoding="utf-8")).get("ok") is True
        except json.JSONDecodeError:
            phase5_ok = False
    ok = proc.returncode == 0 and phase5_ok
    return {
        "id": "W4-G02",
        "ok": ok,
        "label": "EM-5 prod pilot gate",
        "returncode": proc.returncode,
        "phase5_report_ok": phase5_ok,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def run_gates(*, refresh_wave: bool = False) -> dict[str, Any]:
    if refresh_wave or os.environ.get("WAVE4_REFRESH_WAVE_GATES", "0") == "1":
        scripts = [
            "phase6_email_send_platform_gate.sh",
            "phase7_email_wave2_gate.sh",
            "phase8_email_wave3_gate.sh",
            "phase8b_email_wave3b_gate.sh",
        ]
        for script in scripts:
            path = ROOT / "scripts" / script
            if path.is_file():
                subprocess.run(["bash", str(path)], cwd=str(ROOT), check=False)

    checks = [_check_wave_reports(), _run_phase5_gate()]
    ok = all(c.get("ok") for c in checks)
    report = {
        "gate": "phase9_email_wave4",
        "phase": "em-9",
        "component": "email_prod_pilot_wave4",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "env_hint": "deploy/env.em9-wave4.example",
        "runbook": "docs/runbooks/email-marketing-prod-pilot-checklist.md",
    }
    out = _artifacts_dir() / "phase9-email-wave4-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    refresh = "--refresh-wave" in sys.argv
    report = run_gates(refresh_wave=refresh)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
