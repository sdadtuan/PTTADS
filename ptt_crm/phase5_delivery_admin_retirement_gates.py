"""Phase 5 partial — retire Flask admin for SEO + Email delivery (ops-web canonical)."""
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


def _check_ops_web_delivery_hubs() -> dict[str, Any]:
    seo_hub = ROOT / "services" / "ops-web" / "src" / "app" / "seo" / "hub" / "page.tsx"
    email_hub = ROOT / "services" / "ops-web" / "src" / "app" / "email" / "hub" / "page.tsx"
    ok = seo_hub.is_file() and email_hub.is_file()
    return {
        "id": "P5DA-G01",
        "ok": ok,
        "label": "ops-web SEO + Email admin hubs",
        "seo_hub": str(seo_hub.relative_to(ROOT)) if seo_hub.is_file() else None,
        "email_hub": str(email_hub.relative_to(ROOT)) if email_hub.is_file() else None,
    }


def _check_nest_delivery_apis() -> dict[str, Any]:
    seo = ROOT / "services" / "ptt-crm-api" / "src" / "seo-admin" / "seo-admin.controller.ts"
    email = ROOT / "services" / "ptt-crm-api" / "src" / "email-marketing" / "email-marketing.controller.ts"
    ok = seo.is_file() and email.is_file()
    return {
        "id": "P5DA-G02",
        "ok": ok,
        "label": "Nest seo-admin + email-marketing APIs",
        "seo_api": str(seo.relative_to(ROOT)) if seo.is_file() else None,
        "email_api": str(email.relative_to(ROOT)) if email.is_file() else None,
    }


def _check_no_flask_email_admin() -> dict[str, Any]:
    patterns = [
        ROOT / "blueprints" / "email_marketing.py",
        ROOT / "templates" / "crm_email_hub.html",
    ]
    found = [str(p.relative_to(ROOT)) for p in patterns if p.is_file()]
    return {
        "id": "P5DA-G03",
        "ok": not found,
        "label": "No Flask email admin blueprint/templates",
        "legacy_files_found": found,
    }


def _check_nginx_delivery_redirects() -> dict[str, Any]:
    nginx = ROOT / "deploy" / "nginx-rs-delivery-admin-retired.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = nginx.is_file() and "/crm/seo" in text and "/email/" in text
    return {
        "id": "P5DA-G04",
        "ok": ok,
        "label": "nginx delivery-admin redirect config",
        "path": str(nginx.relative_to(ROOT)) if nginx.is_file() else None,
    }


def _check_env_flags() -> dict[str, Any]:
    seo_retired = _truthy("PTT_FLASK_SEO_ADMIN_RETIRED", os.environ.get("PHASE5DA_EXPECT_SEO_RETIRED", "1"))
    email_retired = _truthy("PTT_FLASK_EMAIL_ADMIN_RETIRED", os.environ.get("PHASE5DA_EXPECT_EMAIL_RETIRED", "1"))
    expect_seo = os.environ.get("PHASE5DA_EXPECT_SEO_RETIRED", "1") == "1"
    expect_email = os.environ.get("PHASE5DA_EXPECT_EMAIL_RETIRED", "1") == "1"
    ok = seo_retired == expect_seo and email_retired == expect_email
    return {
        "id": "P5DA-G05",
        "ok": ok,
        "label": "Delivery admin retirement env flags",
        "actual": {
            "PTT_FLASK_SEO_ADMIN_RETIRED": seo_retired,
            "PTT_FLASK_EMAIL_ADMIN_RETIRED": email_retired,
        },
        "expected": {
            "PTT_FLASK_SEO_ADMIN_RETIRED": expect_seo,
            "PTT_FLASK_EMAIL_ADMIN_RETIRED": expect_email,
        },
    }


def _run_ops_web_build_smoke() -> dict[str, Any]:
    if os.environ.get("PHASE5DA_SKIP_BUILD", "1") == "1":
        return {"id": "P5DA-G06", "ok": True, "label": "ops-web build smoke", "skipped": True}
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ROOT / "services" / "ops-web"),
        env={**os.environ},
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "id": "P5DA-G06",
        "ok": proc.returncode == 0,
        "label": "ops-web build smoke",
        "returncode": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_ops_web_delivery_hubs(),
        _check_nest_delivery_apis(),
        _check_no_flask_email_admin(),
        _check_nginx_delivery_redirects(),
        _check_env_flags(),
        _run_ops_web_build_smoke(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "phase": "5-delivery-admin-retire",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "notes": "Apply: APPLY=1 sudo -E ./scripts/close_flask_retirement_delivery_admin.sh",
    }
    dest = _artifacts_dir() / "phase5-delivery-admin-retirement-gate-report.json"
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
