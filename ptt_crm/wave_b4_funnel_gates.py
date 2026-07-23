"""Wave B4 — CRM lead funnel cutover gates (Nest + ops-web)."""
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


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _check_env_funnel_nest() -> dict[str, Any]:
    actual = _truthy("PTT_CRM_LEADS_FUNNEL_NEST", "0")
    expect = _truthy("WAVE_B4_EXPECT_FUNNEL_NEST", "1")
    ok = actual if expect else True
    return {
        "id": "B4-G01",
        "ok": ok,
        "label": "PTT_CRM_LEADS_FUNNEL_NEST enabled",
        "actual": actual,
        "expected": expect,
    }


def _check_env_presales_on_lead() -> dict[str, Any]:
    actual = _truthy("PTT_PRESALES_ON_LEAD", "1")
    expect = _truthy("WAVE_B4_EXPECT_PRESALES_ON_LEAD", "1")
    ok = actual == expect if expect else True
    return {
        "id": "B4-G02",
        "ok": ok,
        "label": "PTT_PRESALES_ON_LEAD enabled",
        "actual": actual,
        "expected": expect,
    }


def _check_workflow_steps_export() -> dict[str, Any]:
    path = ROOT / "services/ptt-crm-api/src/leads-funnel/presales-workflow-steps.data.json"
    ok = path.is_file() and path.stat().st_size > 1000
    count = 0
    if ok:
        data = json.loads(path.read_text(encoding="utf-8"))
        count = len(data)
    return {
        "id": "B4-G03",
        "ok": ok and count >= 12,
        "label": "Presales workflow steps JSON (12 services)",
        "services": count,
    }


def _check_pg_ddl_file() -> dict[str, Any]:
    path = ROOT / "docs/specs/2026-07-23-wave-b4-funnel-pg-ddl.sql"
    ok = path.is_file()
    return {"id": "B4-G04", "ok": ok, "label": "Wave B4 PG DDL spec present"}


def _check_review_queue_timer_unit() -> dict[str, Any]:
    svc = ROOT / "deploy/ptt-lead-review-queue-sync.service"
    timer = ROOT / "deploy/ptt-lead-review-queue-sync.timer"
    cron = ROOT / "scripts/lead_review_queue_sync_cron.sh"
    ok = svc.is_file() and timer.is_file() and cron.is_file()
    return {"id": "B4-G05", "ok": ok, "label": "Review queue sync systemd units + cron script"}


def _check_pytest_parity() -> dict[str, Any]:
    if _truthy("WAVE_B4_SKIP_PYTEST", "0"):
        return {"id": "B4-G06", "ok": True, "label": "Python funnel pytest parity", "skipped": True}
    tests = [
        "tests/test_lead_review_queue.py",
        "tests/test_lead_care_pipeline.py",
        "tests/test_crm_lead_presales.py",
        "tests/test_crm_lead_presales_marketing_plan.py",
    ]
    cmd = [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B4-G06",
        "ok": ok,
        "label": "Python funnel pytest parity",
        "exit_code": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def _check_nest_unit() -> dict[str, Any]:
    if _truthy("WAVE_B4_SKIP_JEST", "0"):
        return {"id": "B4-G07", "ok": True, "label": "Nest leads-funnel unit tests", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    proc = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=leads-funnel|presales-consult", "--passWithNoTests"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B4-G07",
        "ok": ok,
        "label": "Nest leads-funnel unit tests",
        "exit_code": proc.returncode,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_env_funnel_nest(),
        _check_env_presales_on_lead(),
        _check_workflow_steps_export(),
        _check_pg_ddl_file(),
        _check_review_queue_timer_unit(),
        _check_pytest_parity(),
        _check_nest_unit(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "B4",
        "component": "crm_lead_funnel",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/wave-b4-crm-lead-funnel-dev-plan.md",
    }
    dest = _artifacts_dir() / "wave-b4-gate-report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_gates()
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
