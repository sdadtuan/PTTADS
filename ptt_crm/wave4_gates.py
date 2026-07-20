"""Wave 4 — Sales + KPI + Staff gates."""
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


def _check_nest_sales() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "sales" / "sales.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "summary" in text and "SalesModule" in app_text
    return {"id": "W4-G01", "ok": ok, "label": "Nest sales module"}


def _check_nest_kpi() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "kpi" / "kpi.controller.ts"
    sk = ROOT / "services" / "ptt-crm-api" / "src" / "kpi" / "staff-kpi.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and sk.is_file() and "KpiModule" in app_text
    return {"id": "W4-G02", "ok": ok, "label": "Nest kpi module"}


def _check_nest_crm_staff() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "crm-staff" / "crm-staff.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "workspace" in text and "CrmStaffModule" in app_text
    return {"id": "W4-G03", "ok": ok, "label": "Nest crm-staff module"}


def _check_ops_web_wave4() -> dict[str, Any]:
    sales = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "sales" / "page.tsx"
    kpi = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "kpi" / "page.tsx"
    staff = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "staff" / "page.tsx"
    staff_kpi = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "staff-kpi" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = (
        sales.is_file()
        and kpi.is_file()
        and staff.is_file()
        and staff_kpi.is_file()
        and "fetchSalesSummary" in api_text
        and "fetchCrmStaffList" in api_text
    )
    return {"id": "W4-G04", "ok": ok, "label": "ops-web Wave 4 pages + API"}


def _check_nginx_wave4() -> dict[str, Any]:
    nginx = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = "/crm/sales" in text and "/crm/kpi" in text and "/crm/staff" in text
    return {"id": "W4-G05", "ok": ok, "label": "nginx Wave 4 redirects"}


def _check_flask_wave4() -> dict[str, Any]:
    return {"id": "W4-G06", "ok": True, "label": "Flask Wave 4 redirect + guards", "note": "flask retired"}


def _check_wave4_upstream_flags() -> dict[str, Any]:
    from ptt_crm.config import kpi_ops_on_ops_web, sales_ops_on_ops_web, staff_roster_ops_on_ops_web

    expect = _truthy("WAVE4_EXPECT_OPS_WEB", "1")
    actual = sales_ops_on_ops_web() and kpi_ops_on_ops_web() and staff_roster_ops_on_ops_web()
    return {
        "id": "W4-G07",
        "ok": actual == expect,
        "label": "Wave 4 ops-web upstream flags",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_nest_sales(),
        _check_nest_kpi(),
        _check_nest_crm_staff(),
        _check_ops_web_wave4(),
        _check_nginx_wave4(),
        _check_flask_wave4(),
        _check_wave4_upstream_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": 4,
        "component": "crm_sales_kpi_staff",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave4-gate-report.json"
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
