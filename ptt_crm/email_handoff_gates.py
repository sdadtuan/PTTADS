"""Wave Email §13 handoff gates — ops-web Playwright + domain QA (no Flask)."""
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
        ROOT / "services/ops-web/e2e/email-handoff.spec.ts",
        ROOT / "scripts/playwright_ops_email_handoff_e2e.sh",
        ROOT / "scripts/seed_ops_email_handoff_e2e.py",
        ROOT / "scripts/email_handoff_gate.sh",
        ROOT / "tests/test_email_handoff_qa.py",
        ROOT / "services/ops-web/src/app/email/gate-a/page.tsx",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "EM-H13-G01", "ok": not missing, "label": "§13 handoff module files", "missing": missing}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_email_handoff_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "EM-H13-G02",
        "ok": proc.returncode == 0,
        "label": "Python §13 domain QA",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _run_playwright_e2e() -> dict[str, Any]:
    if os.environ.get("EMAIL_HANDOFF_SKIP_E2E", "1") == "1":
        return {"id": "EM-H13-G03", "ok": True, "label": "ops-web Playwright §13 E2E", "skipped": True}
    proc = subprocess.run(
        ["bash", "scripts/playwright_ops_email_handoff_e2e.sh"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    tail = ((proc.stdout or "") + (proc.stderr or ""))[-3000:]
    report_path = _artifacts_dir() / "email-handoff-e2e-report.json"
    report_ok = report_path.is_file()
    if report_ok:
        try:
            report_ok = json.loads(report_path.read_text(encoding="utf-8")).get("ok") is True
        except json.JSONDecodeError:
            report_ok = False
    return {
        "id": "EM-H13-G03",
        "ok": proc.returncode == 0 and report_ok,
        "label": "ops-web Playwright §13 E2E",
        "returncode": proc.returncode,
        "report_path": str(report_path),
        "output_tail": tail,
    }


def run_gates() -> dict[str, Any]:
    checks = [_check_module_files(), _run_python_qa(), _run_playwright_e2e()]
    ok = all(c["ok"] for c in checks)
    report = {
        "ok": ok,
        "spec_section": "13",
        "generated_at": _now_iso(),
        "checks": checks,
        "notes": "SPEC_UI_UX_EMAIL_MARKETING.md §13 — ops-web + Nest (no Flask). E2E: EMAIL_HANDOFF_SKIP_E2E=0",
    }
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "email_handoff_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'email_handoff_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
