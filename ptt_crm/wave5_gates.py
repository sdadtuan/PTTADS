"""Wave 5 — RE projects + Payroll extended gates."""
from __future__ import annotations

import json
import os
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


def _check_wave4p_base() -> dict[str, Any]:
    from ptt_crm.wave4_plus_gates import run_gates

    report = run_gates()
    return {
        "id": "W5-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 4+ base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_re_projects_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "re-projects" / "re-projects.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "api/crm/re-projects" in text and "ReProjectsModule" in app_text
    return {"id": "W5-G01", "ok": ok, "label": "Nest re-projects module"}


def _check_payroll_extended() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "payroll" / "payroll.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = "policy" in text and ("compute" in text or "attendance" in text)
    return {"id": "W5-G02", "ok": ok, "label": "Nest payroll extended routes"}


def _check_flask_wave5() -> dict[str, Any]:
    return {"id": "W5-G03", "ok": True, "label": "Flask Wave 5 guards + redirects", "note": "flask retired"}


def _check_ops_web_wave5() -> dict[str, Any]:
    re_page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "re-projects" / "page.tsx"
    payroll_page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "payroll" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = re_page.is_file() and payroll_page.is_file() and "fetchReProjects" in api_text
    return {"id": "W5-G04", "ok": ok, "label": "ops-web Wave 5 UI"}


def _check_wave5_flags() -> dict[str, Any]:
    from ptt_crm.config import payroll_ops_on_ops_web, re_projects_ops_on_ops_web

    expect = _truthy("WAVE5_EXPECT_OPS_WEB", "1")
    actual = re_projects_ops_on_ops_web() and payroll_ops_on_ops_web()
    return {
        "id": "W5-G05",
        "ok": actual == expect,
        "label": "Wave 5 re-projects/payroll upstream",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave4p_base(),
        _check_re_projects_module(),
        _check_payroll_extended(),
        _check_flask_wave5(),
        _check_ops_web_wave5(),
        _check_wave5_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "5",
        "component": "crm_re_projects_payroll",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave5-gate-report.json"
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
