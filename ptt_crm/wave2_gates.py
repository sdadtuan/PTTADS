"""Wave 2 — CRM Customers + Intake migration gates."""
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


def _check_nest_customers_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "customers" / "customers.controller.ts"
    mod = ROOT / "services" / "ptt-crm-api" / "src" / "customers" / "customers.module.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = (
        ctrl.is_file()
        and mod.is_file()
        and "api/crm/customers" in text
        and "CustomersModule" in app_text
    )
    return {"id": "W2-G01", "ok": ok, "label": "Nest customers module"}


def _check_nest_intake_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "intake" / "intake.controller.ts"
    mod = ROOT / "services" / "ptt-crm-api" / "src" / "intake" / "intake.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = ctrl.is_file() and mod.is_file() and "api/crm/intake" in text and "/complete" in text
    return {"id": "W2-G02", "ok": ok, "label": "Nest intake module"}


def _check_ops_web_customers() -> dict[str, Any]:
    list_page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "customers" / "page.tsx"
    detail = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "customers" / "[id]" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = list_page.is_file() and detail.is_file() and "fetchCustomers" in api_text
    return {"id": "W2-G03", "ok": ok, "label": "ops-web /crm/customers"}


def _check_ops_web_intake() -> dict[str, Any]:
    page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "intake" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = page.is_file() and "createIntakeSession" in api_text
    return {"id": "W2-G04", "ok": ok, "label": "ops-web /crm/intake"}


def _check_nginx_wave2_redirects() -> dict[str, Any]:
    nginx = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = "/crm/customers" in text and "/crm/intake" in text and "ops.pttads.vn" in text
    return {"id": "W2-G05", "ok": ok, "label": "nginx customers + intake redirect"}


def _check_flask_wave2_redirects() -> dict[str, Any]:
    return {"id": "W2-G06", "ok": True, "label": "Flask Wave 2 redirect + guards", "note": "flask retired"}


def _check_customers_upstream_flag() -> dict[str, Any]:
    from ptt_crm.config import customers_ops_on_ops_web

    expect = _truthy("WAVE2_EXPECT_CUSTOMERS_OPS_WEB", "1")
    actual = customers_ops_on_ops_web()
    return {
        "id": "W2-G07",
        "ok": actual == expect,
        "label": "Customers ops-web upstream",
        "actual": actual,
        "expected": expect,
    }


def _check_intake_upstream_flag() -> dict[str, Any]:
    from ptt_crm.config import intake_ops_on_ops_web

    expect = _truthy("WAVE2_EXPECT_INTAKE_OPS_WEB", "1")
    actual = intake_ops_on_ops_web()
    return {
        "id": "W2-G08",
        "ok": actual == expect,
        "label": "Intake ops-web upstream",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_nest_customers_module(),
        _check_nest_intake_module(),
        _check_ops_web_customers(),
        _check_ops_web_intake(),
        _check_nginx_wave2_redirects(),
        _check_flask_wave2_redirects(),
        _check_customers_upstream_flag(),
        _check_intake_upstream_flag(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": 2,
        "component": "crm_customers_intake",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave2-gate-report.json"
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
