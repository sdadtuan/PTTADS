"""Wave 1 — CRM Catalog migration gates."""
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


def _check_nest_catalog_module() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "catalog" / "catalog.controller.ts"
    mod = ROOT / "services" / "ptt-crm-api" / "src" / "catalog" / "catalog.module.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = ctrl.is_file() and mod.is_file() and "api/crm/catalog" in text and "assign-scopes" in text
    return {
        "id": "W1-G01",
        "ok": ok,
        "label": "Nest catalog module",
        "path": str(ctrl.relative_to(ROOT)) if ctrl.is_file() else None,
    }


def _check_ops_web_catalog() -> dict[str, Any]:
    page = ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "catalog" / "page.tsx"
    return {
        "id": "W1-G02",
        "ok": page.is_file(),
        "label": "ops-web /crm/catalog page",
        "path": str(page.relative_to(ROOT)) if page.is_file() else None,
    }


def _check_nginx_catalog_redirect() -> dict[str, Any]:
    nginx = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = "/crm/catalog" in text and "ops.pttads.vn/crm/catalog" in text
    return {
        "id": "W1-G03",
        "ok": ok,
        "label": "nginx /crm/catalog redirect",
    }


def _check_catalog_upstream_flag() -> dict[str, Any]:
    from ptt_crm.config import catalog_ops_on_ops_web

    expect = _truthy("WAVE1_EXPECT_CATALOG_OPS_WEB", "1")
    actual = catalog_ops_on_ops_web()
    ok = actual == expect
    return {
        "id": "W1-G04",
        "ok": ok,
        "label": "Catalog ops-web upstream",
        "actual": actual,
        "expected": expect,
    }


def _run_catalog_jest() -> dict[str, Any]:
    api_dir = ROOT / "services" / "ptt-crm-api"
    if not (api_dir / "package.json").is_file():
        return {"id": "W1-G05", "ok": True, "label": "Catalog jest", "skipped": True}
    if _truthy("WAVE1_SKIP_JEST", "1"):
        return {"id": "W1-G05", "ok": True, "label": "Catalog jest", "skipped": True}
    proc = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=catalog-slug", "--passWithNoTests"],
        cwd=str(api_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "id": "W1-G05",
        "ok": proc.returncode == 0,
        "label": "Catalog jest (slug util)",
        "returncode": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_nest_catalog_module(),
        _check_ops_web_catalog(),
        _check_nginx_catalog_redirect(),
        _check_catalog_upstream_flag(),
        _run_catalog_jest(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "wave": 1,
        "component": "crm_catalog",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
    }
    dest = _artifacts_dir() / "wave1-catalog-gate-report.json"
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
