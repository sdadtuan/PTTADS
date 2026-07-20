"""Wave 2+ — CRM Customers/Intake extended + Cases gates."""
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


def _check_wave2_base() -> dict[str, Any]:
    from ptt_crm.wave2_gates import run_gates

    report = run_gates()
    return {
        "id": "W2P-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 2 base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_customers_extended() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "customers" / "customers.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = (
        ":id/relations" in text
        and ":id/purchases" in text
        and ":id/issues" in text
        and "brief/latest" in text
    )
    return {"id": "W2P-G01", "ok": ok, "label": "Nest customers extended routes"}


def _check_intake_extended() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "intake" / "intake.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = (
        "@Get('stats')" in text
        and "@Get('entry')" in text
        and "reopen" in text
        and "ai-summary" in text
    )
    return {"id": "W2P-G02", "ok": ok, "label": "Nest intake extended routes"}


def _check_cases_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "cases" / "cases.controller.ts"
    mod = ROOT / "services" / "ptt-crm-api" / "src" / "cases" / "cases.module.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = (
        ctrl.is_file()
        and mod.is_file()
        and "care-reports" in text
        and "CasesModule" in app_text
    )
    return {"id": "W2P-G03", "ok": ok, "label": "Nest cases module"}


def _check_flask_cases_guard() -> dict[str, Any]:
    return {"id": "W2P-G04", "ok": True, "label": "Flask cases write guard", "note": "flask retired"}


def _check_cases_upstream_flag() -> dict[str, Any]:
    from ptt_crm.config import cases_ops_on_nest

    expect = _truthy("WAVE2P_EXPECT_CASES_NEST", "1")
    actual = cases_ops_on_nest()
    return {
        "id": "W2P-G05",
        "ok": actual == expect,
        "label": "Cases Nest upstream",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave2_base(),
        _check_customers_extended(),
        _check_intake_extended(),
        _check_cases_module(),
        _check_flask_cases_guard(),
        _check_cases_upstream_flag(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "2+",
        "component": "crm_customers_intake_cases",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave2-plus-gate-report.json"
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
