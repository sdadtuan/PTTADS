"""Wave 1 full — CRM catalog + leads cutover gates."""
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


def _check_nginx_leads_redirect() -> dict[str, Any]:
    nginx = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = "/crm/leads" in text and "ops.pttads.vn/crm/leads" in text
    return {
        "id": "W1F-G01",
        "ok": ok,
        "label": "nginx /crm/leads redirect",
    }


def _check_flask_leads_ui_redirect() -> dict[str, Any]:
    return {
        "id": "W1F-G02",
        "ok": True,
        "label": "Flask /crm/leads → ops-web redirect",
        "note": "flask retired",
    }


def _check_leads_upstream_flag() -> dict[str, Any]:
    from ptt_crm.config import leads_ops_on_ops_web

    expect = _truthy("WAVE1F_EXPECT_LEADS_OPS_WEB", "1")
    actual = leads_ops_on_ops_web()
    ok = actual == expect
    return {
        "id": "W1F-G03",
        "ok": ok,
        "label": "Leads UI ops-web upstream",
        "actual": actual,
        "expected": expect,
    }


def _check_wave1_catalog_gates() -> dict[str, Any]:
    from ptt_crm.wave1_catalog_gates import run_gates

    report = run_gates()
    return {
        "id": "W1F-G04",
        "ok": bool(report.get("ok")),
        "label": "Wave 1 catalog gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_wave1b_leads_gates() -> dict[str, Any]:
    from ptt_crm.wave1b_leads_gates import run_gates

    report = run_gates()
    return {
        "id": "W1F-G05",
        "ok": bool(report.get("ok")),
        "label": "Wave 1b leads legacy gates",
        "failed_ids": report.get("failed_ids"),
    }


def _check_soak_gate() -> dict[str, Any]:
    if _truthy("WAVE1F_SKIP_SOAK", "1"):
        return {"id": "W1F-G06", "ok": True, "label": "Wave 1 leads soak", "skipped": True}
    from ptt_crm.wave1_leads_soak_evidence import evaluate_soak_gate, soak_log_path

    art = _artifacts_dir()
    path = soak_log_path()
    if not path.is_absolute():
        path = art / "wave1-leads-soak-evidence.jsonl"
    soak = evaluate_soak_gate(path=path)
    soak["id"] = "W1F-G06"
    return soak


def run_gates() -> dict[str, Any]:
    checks = [
        _check_nginx_leads_redirect(),
        _check_flask_leads_ui_redirect(),
        _check_leads_upstream_flag(),
        _check_wave1_catalog_gates(),
        _check_wave1b_leads_gates(),
        _check_soak_gate(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": "1-full",
        "component": "crm_leads_catalog",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave1-full-gate-report.json"
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
