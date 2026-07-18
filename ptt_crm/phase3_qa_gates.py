"""Phase 3 QA gate pack — aggregate track gates, regression, UAT sign-off template."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

TRACK_REPORTS: dict[str, str] = {
    "portal": "phase3-portal-mvp-gate-report.json",
    "temporal": "phase3-temporal-gate-report.json",
    "google": "phase3-google-gate-report.json",
    "hub_migration": "phase3-hub-migration-gate-report.json",
}

PHASE3_REGRESSION_MODULES: tuple[str, ...] = (
    "tests.test_hub_pg_migration",
    "tests.test_hub_campaign_sync",
    "tests.test_google_insights_sync",
    "tests.test_client_onboarding_workflow",
    "tests.test_launch_qa_workflow",
    "tests.test_creative_approval_workflow",
    "tests.test_facebook_ads_hub",
)

RUNBOOKS: tuple[str, ...] = (
    "docs/runbooks/phase3-uat-signoff.md",
    "docs/runbooks/deploy-client-portal.md",
    "docs/runbooks/hub-pg-migration.md",
    "docs/runbooks/lead-shadow-sunset.md",
    "docs/runbooks/vps-phase3-portal-cutover-checklist.md",
)


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_track_report(name: str, path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    summary = data.get("summary") or {}
    try:
        rel_path = str(path.relative_to(ROOT))
    except ValueError:
        rel_path = str(path)
    return {
        "track": name,
        "path": rel_path,
        "ok": bool(data.get("ok")),
        "phase": data.get("phase"),
        "generated_at": data.get("generated_at"),
        "passed": summary.get("passed"),
        "total": summary.get("total"),
        "failed": summary.get("failed") or [],
    }


def verify_track_gate_reports() -> dict[str, Any]:
    artifacts = _artifacts_dir()
    tracks: dict[str, Any] = {}
    missing: list[str] = []
    failed: list[str] = []
    for name, filename in TRACK_REPORTS.items():
        path = artifacts / filename
        loaded = _load_track_report(name, path)
        if loaded is None:
            missing.append(name)
            tracks[name] = {"ok": False, "error": "report_missing", "expected": filename}
        else:
            tracks[name] = loaded
            if not loaded.get("ok"):
                failed.append(name)
    ok = not missing and not failed
    return {
        "id": "P3-QA01",
        "ok": ok,
        "label": "Track gate reports (P/T/G/D)",
        "tracks": tracks,
        "missing": missing,
        "failed_tracks": failed,
    }


def verify_regression_phase3() -> dict[str, Any]:
    from ptt_crm.phase2_prod_closure import CRITICAL_REGRESSION_MODULES, _run_unittest_modules

    phase2 = _run_unittest_modules(CRITICAL_REGRESSION_MODULES)
    phase3 = _run_unittest_modules(PHASE3_REGRESSION_MODULES)
    ok = bool(phase2.get("ok")) and bool(phase3.get("ok"))
    return {
        "id": "P3-QA02",
        "ok": ok,
        "label": "Regression L01–L26 + Phase 3 modules",
        "phase2_critical": phase2,
        "phase3_modules": phase3,
    }


def verify_runbooks() -> dict[str, Any]:
    missing = [rel for rel in RUNBOOKS if not (ROOT / rel).is_file()]
    ok = not missing
    return {
        "id": "P3-QA03",
        "ok": ok,
        "label": "Phase 3 runbooks present",
        "checked": list(RUNBOOKS),
        "missing": missing,
    }


def verify_hub_migration_flags() -> dict[str, Any]:
    hub_example = ROOT / "deploy" / "env.staging-hub-pg.example"
    sunset = ROOT / "docs" / "runbooks" / "lead-shadow-sunset.md"
    hub_runbook = ROOT / "docs" / "runbooks" / "hub-pg-migration.md"
    ok = sunset.is_file() and hub_runbook.is_file()
    return {
        "id": "P3-QA04",
        "ok": ok,
        "label": "Hub PG + shadow sunset docs",
        "hub_runbook": hub_runbook.is_file(),
        "shadow_sunset_runbook": sunset.is_file(),
        "staging_env_example": hub_example.is_file(),
        "recommended_flags": {
            "PTT_HUB_READ_SOURCE": "1",
            "PTT_SOP_READ_SOURCE": "1",
            "PTT_HUB_PG_PRIMARY": "1 (after staging soak)",
            "PTT_LEAD_SHADOW_SYNC": "0 (prod after 30d write soak)",
        },
    }


def verify_playwright_e2e() -> dict[str, Any]:
    if os.environ.get("RUN_PORTAL_E2E", "").strip().lower() not in {"1", "true", "yes"}:
        return {
            "id": "P3-QA05",
            "ok": True,
            "label": "Playwright portal E2E",
            "skipped": True,
            "reason": "RUN_PORTAL_E2E not set",
        }
    script = ROOT / "scripts" / "playwright_portal_e2e.sh"
    if not script.is_file():
        return {"id": "P3-QA05", "ok": False, "label": "Playwright portal E2E", "error": "script_missing"}
    proc = subprocess.run(
        [str(script)],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "id": "P3-QA05",
        "ok": proc.returncode == 0,
        "label": "Playwright portal E2E",
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def verify_portal_cross_tenant() -> dict[str, Any]:
    """Portal JWT must not read another client's performance (403)."""
    email = os.environ.get("PORTAL_E2E_APPROVER_EMAIL", "approver@demo.local")
    password = os.environ.get("PORTAL_E2E_APPROVER_PASSWORD", "demo123")
    api = (os.environ.get("PTT_API_URL") or "http://127.0.0.1:3000").rstrip("/")

    import urllib.error
    import urllib.request

    def _login() -> str | None:
        req = urllib.request.Request(
            f"{api}/api/v1/portal/auth/login",
            data=json.dumps({"email": email, "password": password}).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
                return body.get("access_token")
        except Exception:
            return None

    token = _login()
    if not token:
        return {"id": "P3-QA06", "ok": False, "label": "Portal cross-tenant 403", "error": "login_failed"}

    other_client = "00000000-0000-0000-0000-000000000001"
    req = urllib.request.Request(
        f"{api}/api/v1/performance?client_id={other_client}",
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {
                "id": "P3-QA06",
                "ok": False,
                "label": "Portal cross-tenant 403",
                "error": "expected_403",
                "status": resp.status,
            }
    except urllib.error.HTTPError as exc:
        ok = exc.code == 403
        return {
            "id": "P3-QA06",
            "ok": ok,
            "label": "Portal cross-tenant 403",
            "status": exc.code,
        }
    except Exception as exc:
        return {"id": "P3-QA06", "ok": False, "label": "Portal cross-tenant 403", "error": str(exc)}


def build_uat_signoff(*, qa_report: dict[str, Any]) -> dict[str, Any]:
    steps = qa_report.get("steps") or {}
    track = steps.get("track_gates") or {}
    tracks = track.get("tracks") or {}
    regression_ok = bool((steps.get("regression") or {}).get("ok"))
    playwright = steps.get("playwright") or {}
    pw_ok = bool(playwright.get("ok")) and not playwright.get("skipped")
    security = steps.get("cross_tenant") or {}

    portal_report_path = _artifacts_dir() / "phase3-portal-mvp-gate-report.json"
    meta_portal_ok = False
    if portal_report_path.is_file():
        try:
            portal_data = json.loads(portal_report_path.read_text(encoding="utf-8"))
            meta_portal_ok = bool((portal_data.get("steps") or {}).get("meta_performance", {}).get("ok"))
        except json.JSONDecodeError:
            meta_portal_ok = False

    return {
        "phase": "3",
        "signed_at": None,
        "environment": os.environ.get("PTT_QA_ENV", "local"),
        "generated_at": _now_iso(),
        "host": socket.gethostname(),
        "automated_qa_ok": bool(qa_report.get("ok")),
        "gates": {
            "portal_track": bool((tracks.get("portal") or {}).get("ok")),
            "temporal_track": bool((tracks.get("temporal") or {}).get("ok")),
            "google_track": bool((tracks.get("google") or {}).get("ok")),
            "hub_migration_track": bool((tracks.get("hub_migration") or {}).get("ok")),
            "regression_l01_l26": regression_ok,
            "playwright_portal": pw_ok,
            "meta_performance_portal": meta_portal_ok,
            "facebook_ads_hub": bool((steps.get("regression") or {}).get("phase3_modules", {}).get("ok")),
            "portal_tls": False,
            "pilot_users_scrypt": False,
            "creative_approve_e2e_prod": False,
            "cross_tenant_403": bool(security.get("ok")),
            "temporal_worker_healthy_48h": False,
            "google_oauth_pilot_prod": False,
            "hub_pg_primary_staging_7d": False,
            "lead_shadow_off_prod": False,
        },
        "signoffs": {
            "am_lead": None,
            "client_approver": None,
            "devops": None,
            "qa": None,
        },
        "notes": "Automated local QA — complete manual checklist in docs/runbooks/phase3-uat-signoff.md for prod.",
    }


def run_phase3_qa_gate_pack() -> dict[str, Any]:
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)

    steps: dict[str, Any] = {
        "track_gates": verify_track_gate_reports(),
        "regression": verify_regression_phase3(),
        "runbooks": verify_runbooks(),
        "hub_docs": verify_hub_migration_flags(),
        "cross_tenant": verify_portal_cross_tenant(),
        "playwright": verify_playwright_e2e(),
    }
    required = [k for k in steps if k != "playwright" or not steps[k].get("skipped")]
    all_ok = all(bool(steps[k].get("ok")) for k in required)

    report: dict[str, Any] = {
        "phase": "phase3_qa_gate",
        "generated_at": _now_iso(),
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(required),
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
    }
    report["uat_signoff"] = build_uat_signoff(qa_report=report)

    qa_out = artifacts / "phase3-qa-gate-report.json"
    qa_out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    signoff_out = artifacts / "phase3-uat-signoff.json"
    signoff_out.write_text(
        json.dumps(report["uat_signoff"], indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = run_phase3_qa_gate_pack()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
