"""Wave 4+ — Sales/KPI/Staff extended + Proposals + Payroll gates."""
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


def _check_wave4_base() -> dict[str, Any]:
    from ptt_crm.wave4_gates import run_gates

    report = run_gates()
    return {
        "id": "W4P-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 4 base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_sales_extended() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "sales" / "sales.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = "pipeline-cases" in text and "partners" in text and "reports" in text
    return {"id": "W4P-G01", "ok": ok, "label": "Nest sales extended routes"}


def _check_kpi_extended() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "kpi" / "kpi.controller.ts"
    prog = ROOT / "services" / "ptt-crm-api" / "src" / "kpi" / "staff-kpi-progress.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = "@Get('alerts')" in text and "@Get('chart')" in text and prog.is_file()
    return {"id": "W4P-G02", "ok": ok, "label": "Nest KPI alerts/chart/progress"}


def _check_staff_extended() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "crm-staff" / "crm-staff.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = "@Get('levels')" in text and "@Post('import')" in text and "competency" in text
    return {"id": "W4P-G03", "ok": ok, "label": "Nest staff levels/competency/import"}


def _check_proposals_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "proposals" / "proposals.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "api/crm/proposals" in text and "ProposalsModule" in app_text
    return {"id": "W4P-G04", "ok": ok, "label": "Nest proposals module"}


def _check_payroll_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "payroll" / "payroll.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "dashboard" in text and "PayrollModule" in app_text
    return {"id": "W4P-G05", "ok": ok, "label": "Nest payroll dashboard module"}


def _check_flask_wave4p() -> dict[str, Any]:
    return {"id": "W4P-G06", "ok": True, "label": "Flask Wave 4+ guards + proposals redirect", "note": "flask retired"}


def _check_ops_web_wave4p() -> dict[str, Any]:
    sales = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "sales" / "page.tsx"
    props = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "proposals" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = sales.is_file() and props.is_file() and "fetchSalesPipelineCases" in api_text
    return {"id": "W4P-G07", "ok": ok, "label": "ops-web Wave 4+ UI"}


def _check_wave4p_flags() -> dict[str, Any]:
    from ptt_crm.config import payroll_ops_on_nest, proposals_ops_on_ops_web

    expect = _truthy("WAVE4P_EXPECT_OPS_WEB", "1")
    actual = proposals_ops_on_ops_web() and payroll_ops_on_nest()
    return {
        "id": "W4P-G08",
        "ok": actual == expect,
        "label": "Wave 4+ proposals/payroll upstream",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave4_base(),
        _check_sales_extended(),
        _check_kpi_extended(),
        _check_staff_extended(),
        _check_proposals_module(),
        _check_payroll_module(),
        _check_flask_wave4p(),
        _check_ops_web_wave4p(),
        _check_wave4p_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "4+",
        "component": "crm_sales_kpi_staff_extended",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave4-plus-gate-report.json"
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
