"""Wave 7 — Phase 5 readiness gates (crm_shell + svc-finance)."""
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


def _check_wave6_base() -> dict[str, Any]:
    from ptt_crm.wave6_gates import run_gates

    report = run_gates()
    return {
        "id": "W7-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 6 base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_svc_finance_and_board_nest() -> dict[str, Any]:
    svc_ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "svc-finance" / "svc-finance.controller.ts"
    board_ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "crm-board" / "crm-board.controller.ts"
    svc_text = svc_ctrl.read_text(encoding="utf-8") if svc_ctrl.is_file() else ""
    board_text = board_ctrl.read_text(encoding="utf-8") if board_ctrl.is_file() else ""
    ok = (
        "summary" in svc_text
        and "svc-payments" in svc_text
        and svc_ctrl.is_file()
        and board_ctrl.is_file()
        and "board" in board_text
        and "api/crm" in board_text
    )
    return {
        "id": "W7-G01",
        "ok": ok,
        "label": "Nest svc-finance summary + svc-payments; crm-board /api/crm/board",
    }


def _check_ops_web_crm_board() -> dict[str, Any]:
    page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = page.is_file() and "fetchCrmBoard" in api_text
    return {"id": "W7-G02", "ok": ok, "label": "ops-web CRM board hub + fetchCrmBoard"}


def _check_registry_phase5_ready() -> dict[str, Any]:
    from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus, gap_report

    shell = next((m for m in CRM_MODULES if m.id == "crm_shell"), None)
    report = gap_report()
    expect = _truthy("WAVE7_EXPECT_PHASE5_READY", "1")
    ok = (
        shell is not None
        and shell.status == CrmModuleStatus.RETIRED
        and shell.nest_module is not None
        and "crm-board" in shell.nest_module
        and shell.ops_web_route == "/crm"
        and (report.get("can_stop_ptt_service") is True if expect else True)
    )
    return {
        "id": "W7-G03",
        "ok": ok,
        "label": "Registry crm_shell RETIRED + gap can_stop_ptt_service",
        "can_stop_ptt_service": report.get("can_stop_ptt_service"),
        "expected_phase5_ready": expect,
    }


def _check_wave7_shell_flags() -> dict[str, Any]:
    from ptt_crm.config import crm_shell_ops_on_ops_web

    expect = _truthy("WAVE7_EXPECT_SHELL_OPS_WEB", "1")
    actual = crm_shell_ops_on_ops_web()
    return {
        "id": "W7-G04",
        "ok": actual == expect,
        "label": "Wave 7 CRM shell on ops-web",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave6_base(),
        _check_svc_finance_and_board_nest(),
        _check_ops_web_crm_board(),
        _check_registry_phase5_ready(),
        _check_wave7_shell_flags(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "7",
        "component": "crm_phase5_readiness",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave7-gate-report.json"
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
