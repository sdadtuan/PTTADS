"""Wave 5++ — RE projects KPI/risks/budget phase gates."""
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


def _check_wave5_plus_base() -> dict[str, Any]:
    from ptt_crm.wave5_plus_gates import run_gates

    report = run_gates()
    return {
        "id": "W5PP-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 5+ base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_re_projects_kpi_risks_budget_nest() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "re-projects" / "re-projects.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = ":id/kpis" in text and ":id/budget" in text and ":id/risks" in text
    return {"id": "W5PP-G01", "ok": ok, "label": "Nest re-projects KPI/risks/budget routes"}


def _check_ops_web_kpi_risks_budget() -> dict[str, Any]:
    detail = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "re-projects" / "[id]" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    page_text = detail.read_text(encoding="utf-8") if detail.is_file() else ""
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = (
        "fetchReProjectKpis" in api_text
        and "kpi" in page_text.lower()
        and "budget" in page_text.lower()
        and "risks" in page_text.lower()
    )
    return {"id": "W5PP-G02", "ok": ok, "label": "ops-web RE KPI/risks/budget UI"}


def _check_registry_re_projects_retired() -> dict[str, Any]:
    from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus

    mod = next((m for m in CRM_MODULES if m.id == "re_projects"), None)
    ok = (
        mod is not None
        and mod.status == CrmModuleStatus.RETIRED
        and mod.nest_module is not None
        and "re-projects/" in mod.nest_module
    )
    return {"id": "W5PP-G03", "ok": ok, "label": "Registry re_projects RETIRED with Nest routes"}


def _check_wave5pp_flags() -> dict[str, Any]:
    from ptt_crm.config import re_projects_kpi_risks_on_nest

    expect = _truthy("WAVE5PP_EXPECT_KPI_RISKS_NEST", "1")
    actual = re_projects_kpi_risks_on_nest()
    return {
        "id": "W5PP-G04",
        "ok": actual == expect,
        "label": "Wave 5++ RE KPI/risks/budget on Nest",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave5_plus_base(),
        _check_re_projects_kpi_risks_budget_nest(),
        _check_ops_web_kpi_risks_budget(),
        _check_registry_re_projects_retired(),
        _check_wave5pp_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "5++",
        "component": "crm_re_projects_kpi_risks_budget",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave5-pp-gate-report.json"
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
