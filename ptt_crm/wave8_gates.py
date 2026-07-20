"""Wave 8 — Flask HTTP removed from repo (Phase 5 complete)."""
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


def _check_wave7_base() -> dict[str, Any]:
    from ptt_crm.wave7_gates import run_gates

    report = run_gates()
    return {
        "id": "W8-G00",
        "ok": bool(report.get("ok")),
        "label": "Wave 7 base gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_flask_http_removed() -> dict[str, Any]:
    app_py = ROOT / "app.py"
    blueprints = ROOT / "blueprints"
    ok = not app_py.is_file() and not blueprints.is_dir()
    return {
        "id": "W8-G01",
        "ok": ok,
        "label": "app.py deleted; blueprints/ removed",
        "app_py_exists": app_py.is_file(),
        "blueprints_exists": blueprints.is_dir(),
    }


def _check_no_flask_proxy_in_nest() -> dict[str, Any]:
    webhooks_svc = ROOT / "services" / "ptt-crm-api" / "src" / "webhooks" / "webhooks.service.ts"
    text = webhooks_svc.read_text(encoding="utf-8") if webhooks_svc.is_file() else ""
    ok = webhooks_svc.is_file() and "proxyToFlask" not in text
    return {
        "id": "W8-G02",
        "ok": ok,
        "label": "No proxyToFlask in Nest webhooks.service.ts",
    }


def _check_registry_all_retired() -> dict[str, Any]:
    from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus

    non_retired = [m.id for m in CRM_MODULES if m.status != CrmModuleStatus.RETIRED]
    email = next((m for m in CRM_MODULES if m.id == "email"), None)
    ok = len(non_retired) == 0 and email is not None and email.status == CrmModuleStatus.RETIRED
    return {
        "id": "W8-G03",
        "ok": ok,
        "label": "Registry all modules RETIRED (email included)",
        "non_retired": non_retired,
    }


def _check_gap_can_stop() -> dict[str, Any]:
    from ptt_crm.crm_flask_retirement_registry import gap_report

    report = gap_report()
    ok = report.get("can_stop_ptt_service") is True
    return {
        "id": "W8-G04",
        "ok": ok,
        "label": "Gap report can_stop_ptt_service",
        "can_stop_ptt_service": report.get("can_stop_ptt_service"),
    }


def _check_landing_site_removed() -> dict[str, Any]:
    landing_html = ROOT / "templates" / "landing.html"
    static_landing = ROOT / "static" / "landing.js"
    cms_media = ROOT / "cms_media_images.py"
    ok = not landing_html.is_file() and not static_landing.is_file() and not cms_media.is_file()
    return {
        "id": "W8-G05",
        "ok": ok,
        "label": "Public landing/CMS site assets removed",
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_wave7_base(),
        _check_flask_http_removed(),
        _check_no_flask_proxy_in_nest(),
        _check_registry_all_retired(),
        _check_gap_can_stop(),
        _check_landing_site_removed(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "8",
        "component": "crm_flask_http_removed",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave8-gate-report.json"
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
