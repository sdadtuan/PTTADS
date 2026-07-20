"""Wave 6 — Finance / owner-weekly phase gates."""
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


def _check_wave5_ppp_base() -> dict[str, Any]:
    from ptt_crm.wave5_ppp_gates import run_gates

    report = run_gates()
    return {
        "id": "W6-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 5+++ base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_finance_owner_weekly_nest() -> dict[str, Any]:
    finance_ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "finance" / "finance.controller.ts"
    owner_ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "owner-weekly" / "owner-weekly.controller.ts"
    finance_text = finance_ctrl.read_text(encoding="utf-8") if finance_ctrl.is_file() else ""
    owner_text = owner_ctrl.read_text(encoding="utf-8") if owner_ctrl.is_file() else ""
    ok = (
        "business-dashboard" in finance_text
        and "financials" in finance_text
        and "kpi-alerts" in finance_text
        and "cash-snapshots" in owner_text
        and "export" in owner_text
    )
    return {
        "id": "W6-G01",
        "ok": ok,
        "label": "Nest finance + owner-weekly dashboard routes",
    }


def _check_ops_web_finance_pages() -> dict[str, Any]:
    biz = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "business-dashboard" / "page.tsx"
    owner = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "owner-weekly" / "page.tsx"
    fin = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "financials" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = (
        biz.is_file()
        and owner.is_file()
        and fin.is_file()
        and "fetchFinanceBusinessDashboard" in api_text
        and "fetchOwnerWeeklyDashboard" in api_text
        and "fetchFinanceFinancials" in api_text
    )
    return {"id": "W6-G02", "ok": ok, "label": "ops-web finance/owner-weekly UI + API helpers"}


def _check_registry_finance_retired() -> dict[str, Any]:
    from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus

    mod = next((m for m in CRM_MODULES if m.id == "finance"), None)
    ok = (
        mod is not None
        and mod.status == CrmModuleStatus.RETIRED
        and mod.nest_module is not None
        and "finance/" in mod.nest_module
        and mod.ops_web_route is not None
        and "/crm/business-dashboard" in mod.ops_web_route
    )
    return {
        "id": "W6-G03",
        "ok": ok,
        "label": "Registry finance module RETIRED with Nest + ops-web routes",
    }


def _check_wave6_flags() -> dict[str, Any]:
    from ptt_crm.config import finance_ops_on_nest

    expect = _truthy("WAVE6_EXPECT_FINANCE_NEST", "1")
    actual = finance_ops_on_nest()
    return {
        "id": "W6-G04",
        "ok": actual == expect,
        "label": "Wave 6 finance/owner-weekly on Nest",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave5_ppp_base(),
        _check_finance_owner_weekly_nest(),
        _check_ops_web_finance_pages(),
        _check_registry_finance_retired(),
        _check_wave6_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "6",
        "component": "crm_finance_owner_weekly",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave6-gate-report.json"
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
