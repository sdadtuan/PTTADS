"""CRM Flask retirement gates — wave progress + Phase 5 prerequisites."""
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


def _check_gap_report() -> dict[str, Any]:
    from ptt_crm.crm_flask_retirement_registry import gap_report

    report = gap_report()
    min_pct = float(os.environ.get("CRM_FLASK_MIN_MIGRATED_PCT", "100"))
    ok = report["migrated_pct"] >= min_pct and report.get("can_stop_ptt_service", False)
    return {
        "id": "CRM-G01",
        "ok": ok if _truthy("CRM_FLASK_REQUIRE_FULL_MIGRATION", "0") else True,
        "label": "CRM module migration gap",
        "migrated_pct": report["migrated_pct"],
        "flask_only_count": report["flask_only"],
        "can_stop_ptt_service": report["can_stop_ptt_service"],
        "next_modules": report.get("next_modules"),
        "skipped_strict": not _truthy("CRM_FLASK_REQUIRE_FULL_MIGRATION", "0"),
    }


def _check_leads_upstream() -> dict[str, Any]:
    from ptt_crm.config import leads_read_source_pg, nest_leads_base_url

    expect_nest = _truthy("CRM_EXPECT_LEADS_NEST", "1")
    read_pg = leads_read_source_pg()
    ok = (not expect_nest) or read_pg
    return {
        "id": "CRM-G02",
        "ok": ok,
        "label": "Leads read PG / Nest upstream",
        "read_pg": read_pg,
        "nest_url": nest_leads_base_url(),
    }


def _check_webhooks_nest() -> dict[str, Any]:
    nest_meta = _truthy("PTT_WEBHOOKS_NEST_META", os.environ.get("PTT_WEBHOOKS_NEST_META", "1"))
    nest_zalo = _truthy("PTT_WEBHOOKS_NEST_ZALO", os.environ.get("PTT_WEBHOOKS_NEST_ZALO", "1"))
    nest_google = _truthy("PTT_WEBHOOKS_NEST_GOOGLE", os.environ.get("PTT_WEBHOOKS_NEST_GOOGLE", "1"))
    fallback = _truthy("PTT_WEBHOOKS_FLASK_FALLBACK", os.environ.get("PTT_WEBHOOKS_FLASK_FALLBACK", "0"))
    ok = nest_meta and nest_zalo and nest_google and not fallback
    return {
        "id": "CRM-G03",
        "ok": ok,
        "label": "Webhooks Nest-only (meta/zalo/google)",
        "PTT_WEBHOOKS_NEST_META": nest_meta,
        "PTT_WEBHOOKS_NEST_ZALO": nest_zalo,
        "PTT_WEBHOOKS_NEST_GOOGLE": nest_google,
        "PTT_WEBHOOKS_FLASK_FALLBACK": fallback,
    }


def _check_delivery_admin_retired() -> dict[str, Any]:
    seo = _truthy("PTT_FLASK_SEO_ADMIN_RETIRED", os.environ.get("PTT_FLASK_SEO_ADMIN_RETIRED", "0"))
    email = _truthy("PTT_FLASK_EMAIL_ADMIN_RETIRED", os.environ.get("PTT_FLASK_EMAIL_ADMIN_RETIRED", "0"))
    meta = _truthy("PTT_FLASK_META_ADS_ADMIN_RETIRED", os.environ.get("PTT_FLASK_META_ADS_ADMIN_RETIRED", "0"))
    ok = seo and email and meta
    return {
        "id": "CRM-G04",
        "ok": ok if _truthy("CRM_EXPECT_DELIVERY_ADMIN_RETIRED", "1") else True,
        "label": "Horizon 0/1 delivery admin retired",
        "seo": seo,
        "email": email,
        "meta": meta,
    }


def _check_ops_web_crm_routes() -> dict[str, Any]:
    routes = [
        ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "leads" / "page.tsx",
        ROOT / "services" / "ops-web" / "src" / "app" / "crm" / "hub" / "page.tsx",
    ]
    missing = [str(p.relative_to(ROOT)) for p in routes if not p.is_file()]
    return {
        "id": "CRM-G05",
        "ok": not missing,
        "label": "ops-web CRM core routes",
        "missing": missing,
    }


def _check_phase5_prerequisites() -> dict[str, Any]:
    if _truthy("CRM_SKIP_PHASE5_PREREQ", "1"):
        return {"id": "CRM-G06", "ok": True, "label": "Phase 5 prerequisites", "skipped": True}
    mode = (os.environ.get("PTT_FLASK_MONOLITH_MODE") or "active").strip().lower()
    ok = mode in {"readonly", "retired"}
    return {
        "id": "CRM-G06",
        "ok": ok,
        "label": "Phase 4 readonly soak (PTT_FLASK_MONOLITH_MODE)",
        "mode": mode,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_gap_report(),
        _check_leads_upstream(),
        _check_webhooks_nest(),
        _check_delivery_admin_retired(),
        _check_ops_web_crm_routes(),
        _check_phase5_prerequisites(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "component": "crm_flask_retirement",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/crm-flask-retirement-master-checklist.md",
        "stop_ptt_service_allowed": _check_gap_report().get("can_stop_ptt_service", False),
    }
    dest = _artifacts_dir() / "crm-flask-retirement-gate-report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_gates()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
