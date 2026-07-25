"""Email Marketing P1 UX parity gates — ops-web + Nest (no Flask)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _check_module_files() -> dict[str, Any]:
    files = [
        ROOT / "services/ops-web/src/components/email/EmailDomainOnboardingWizard.tsx",
        ROOT / "services/ptt-crm-api/src/email-marketing/email-alert-notify.util.ts",
        ROOT / "docs/huong-dan-email-marketing-ops.md",
        ROOT / "docs/forms/email-marketing-ops-checklist-a4.html",
        ROOT / "tests/test_email_p1_qa.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "EM-P1-G01", "ok": not missing, "label": "P1 module files", "missing": missing}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_email_p1_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "EM-P1-G02",
        "ok": proc.returncode == 0,
        "label": "Python P1 domain QA",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _run_handoff_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_email_handoff_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "EM-P1-G03",
        "ok": proc.returncode == 0,
        "label": "Python §13 handoff QA (regression)",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-1500:],
        "stderr_tail": proc.stderr[-1500:],
    }


def run_gates() -> dict[str, Any]:
    checks = [_check_module_files(), _run_python_qa(), _run_handoff_qa()]
    ok = all(c["ok"] for c in checks)
    report = {
        "ok": ok,
        "phase": "P1",
        "generated_at": _now_iso(),
        "checks": checks,
        "notes": "EMAIL_MARKETING_COMPLETION_ROADMAP P1.1–P1.7 — ops-web + Nest (no Flask)",
    }
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "email_p1_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'email_p1_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
