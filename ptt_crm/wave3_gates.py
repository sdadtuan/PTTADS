"""Wave 3 — Marketing plans + Service lifecycle + SOP gates."""
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


def _check_nest_marketing_plans() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "marketing-plans" / "marketing-plans.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "api/crm/marketing-plans" in text and "MarketingPlansModule" in app_text
    return {"id": "W3-G01", "ok": ok, "label": "Nest marketing-plans module"}


def _check_nest_service_lifecycle() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "service-lifecycle" / "service-lifecycle.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "api/crm/service-lifecycle" in text and "ServiceLifecycleModule" in app_text
    return {"id": "W3-G02", "ok": ok, "label": "Nest service-lifecycle module"}


def _check_nest_sop() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "sop" / "sop.controller.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = ctrl.is_file() and "@Get('templates')" in text and "SopModule" in app_text
    return {"id": "W3-G03", "ok": ok, "label": "Nest sop module"}


def _check_ops_web_wave3() -> dict[str, Any]:
    mp = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "marketing-plan" / "page.tsx"
    sd = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "service-delivery" / "page.tsx"
    sop = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "sop" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = (
        mp.is_file()
        and sd.is_file()
        and sop.is_file()
        and "fetchMarketingPlans" in api_text
        and "fetchServiceLifecycles" in api_text
        and "fetchSopRuns" in api_text
    )
    return {"id": "W3-G04", "ok": ok, "label": "ops-web Wave 3 pages + API"}


def _check_nginx_wave3() -> dict[str, Any]:
    nginx = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = (
        "/crm/marketing-plan" in text
        and "/crm/service-delivery" in text
        and "/crm/sop" in text
    )
    return {"id": "W3-G05", "ok": ok, "label": "nginx Wave 3 redirects"}


def _check_flask_wave3() -> dict[str, Any]:
    return {"id": "W3-G06", "ok": True, "label": "Flask Wave 3 redirect + guards", "note": "flask retired"}


def _check_wave3_upstream_flags() -> dict[str, Any]:
    from ptt_crm.config import (
        marketing_plans_ops_on_ops_web,
        service_lifecycle_ops_on_ops_web,
        sop_ops_on_ops_web,
    )

    expect = _truthy("WAVE3_EXPECT_OPS_WEB", "1")
    actual = (
        marketing_plans_ops_on_ops_web()
        and service_lifecycle_ops_on_ops_web()
        and sop_ops_on_ops_web()
    )
    return {
        "id": "W3-G07",
        "ok": actual == expect,
        "label": "Wave 3 ops-web upstream flags",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_nest_marketing_plans(),
        _check_nest_service_lifecycle(),
        _check_nest_sop(),
        _check_ops_web_wave3(),
        _check_nginx_wave3(),
        _check_flask_wave3(),
        _check_wave3_upstream_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": 3,
        "component": "crm_marketing_plans_service_lifecycle_sop",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave3-gate-report.json"
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
