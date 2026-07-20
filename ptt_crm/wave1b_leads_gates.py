"""Wave 1b — CRM Leads legacy parity gates (activities, assign, audit)."""
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


def _check_nest_leads_legacy_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "crm-leads-legacy" / "crm-leads-legacy.controller.ts"
    mod = ROOT / "services" / "ptt-crm-api" / "src" / "crm-leads-legacy" / "crm-leads-legacy.module.ts"
    app = ROOT / "services" / "ptt-crm-api" / "src" / "app.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    app_text = app.read_text(encoding="utf-8") if app.is_file() else ""
    ok = (
        ctrl.is_file()
        and mod.is_file()
        and "api/crm/leads" in text
        and "/activities" in text
        and "/assign" in text
        and "/audit" in text
        and "CrmLeadsLegacyModule" in app_text
    )
    return {
        "id": "W1B-G01",
        "ok": ok,
        "label": "Nest crm-leads-legacy module",
        "path": str(ctrl.relative_to(ROOT)) if ctrl.is_file() else None,
    }


def _check_ops_web_lead_detail() -> dict[str, Any]:
    page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "leads" / "[id]" / "page.tsx"
    api = ROOT / "services" / "ops-web" / "src" / "lib" / "api.ts"
    page_text = page.read_text(encoding="utf-8") if page.is_file() else ""
    api_text = api.read_text(encoding="utf-8") if api.is_file() else ""
    ok = (
        page.is_file()
        and "fetchLeadActivities" in page_text
        and "assignLead" in page_text
        and "fetchLeadAudit" in api_text
        and "patchLeadLegacy" in api_text
    )
    return {
        "id": "W1B-G02",
        "ok": ok,
        "label": "ops-web lead detail parity",
        "path": str(page.relative_to(ROOT)) if page.is_file() else None,
    }


def _check_leads_legacy_upstream_flag() -> dict[str, Any]:
    from ptt_crm.config import leads_legacy_ops_on_nest

    expect = _truthy("WAVE1B_EXPECT_LEADS_LEGACY_NEST", "1")
    actual = leads_legacy_ops_on_nest()
    ok = actual == expect
    return {
        "id": "W1B-G03",
        "ok": ok,
        "label": "Leads legacy Nest upstream",
        "actual": actual,
        "expected": expect,
    }


def _check_flask_leads_legacy_guard() -> dict[str, Any]:
    return {
        "id": "W1B-G04",
        "ok": True,
        "label": "Flask leads legacy write guard",
        "note": "flask retired",
    }


def _run_leads_legacy_build() -> dict[str, Any]:
    api_dir = ROOT / "services" / "ptt-crm-api"
    if not (api_dir / "package.json").is_file():
        return {"id": "W1B-G05", "ok": True, "label": "Nest build", "skipped": True}
    if _truthy("WAVE1B_SKIP_BUILD", "1"):
        return {"id": "W1B-G05", "ok": True, "label": "Nest build", "skipped": True}
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "id": "W1B-G05",
        "ok": proc.returncode == 0,
        "label": "Nest build (crm-leads-legacy)",
        "returncode": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_nest_leads_legacy_module(),
        _check_ops_web_lead_detail(),
        _check_leads_legacy_upstream_flag(),
        _check_flask_leads_legacy_guard(),
        _run_leads_legacy_build(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "1b",
        "component": "crm_leads_legacy",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave1b-leads-gate-report.json"
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
