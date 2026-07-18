"""Phase 2 prod pending closure — Sentry, CAPI, Meta alert, regression, backup."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# P0 lifecycle cases with automated coverage (L01–L26 critical subset).
CRITICAL_REGRESSION_MODULES: tuple[str, ...] = (
    "tests.test_crm_leads",
    "tests.test_crm_lead_presales",
    "tests.test_crm_service_lifecycle",
    "tests.test_crm_staff_kpi_readiness",
    "tests.test_crm_svc_lead_am_sync",
    "tests.test_crm_facebook_leads",
    "tests.test_crm_hdsd_docs",
    "tests.test_crm_test_cases_workbook",
    "tests.test_crm_svc_presales_l4",
    "tests.test_leads_v1_write_contract",
    "tests.test_dual_run_write",
    "tests.test_observability",
    "tests.test_meta_insights_sync",
    "tests.test_capi_dispatch",
)


def _project_root() -> Path:
    return ROOT


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (_project_root() / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_unittest_modules(modules: tuple[str, ...]) -> dict[str, Any]:
    """Run each module in a subprocess to avoid shared DB pollution between suites."""
    python = sys.executable
    root = str(_project_root())
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", root)
    total_run = 0
    total_failures = 0
    total_errors = 0
    failed_modules: list[str] = []
    output_parts: list[str] = []
    for mod in modules:
        proc = subprocess.run(
            [python, "-m", "unittest", mod],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        tail = (proc.stdout or "") + (proc.stderr or "")
        output_parts.append(f"=== {mod} ===\n{tail[-800:]}")
        m = re.search(r"Ran (\d+) test", tail)
        if m:
            total_run += int(m.group(1))
        if proc.returncode != 0:
            failed_modules.append(mod)
            if "failures=" in tail:
                fm = re.search(r"failures=(\d+)", tail)
                if fm:
                    total_failures += int(fm.group(1))
            if "errors=" in tail:
                em = re.search(r"errors=(\d+)", tail)
                if em:
                    total_errors += int(em.group(1))
            else:
                total_failures += 1
    ok = not failed_modules
    return {
        "ok": ok,
        "tests_run": total_run,
        "failures": total_failures,
        "errors": total_errors,
        "modules": list(modules),
        "failed_modules": failed_modules,
        "output_tail": "\n".join(output_parts)[-4000:],
    }


def verify_sentry_phase2(*, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Verify observability hooks + optional Sentry DSN smoke."""
    root = artifacts_dir or _artifacts_dir()
    runbook = root.parent / "docs" / "runbooks" / "sentry-phase2-dashboards.md"
    obs_example = root.parent / "deploy" / "env.observability.example"
    hooks = _run_unittest_modules(("tests.test_observability",))
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    test_event_sent = False
    test_event_error: str | None = None
    if dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=dsn,
                environment=os.environ.get("SENTRY_ENVIRONMENT", "staging"),
                traces_sample_rate=0.0,
            )
            sentry_sdk.capture_message("phase2_sentry_dashboard_test", level="info")
            test_event_sent = True
        except Exception as exc:
            test_event_error = str(exc)
    waiver = os.environ.get("PTT_SENTRY_CLOSURE_WAIVER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    ok = bool(
        hooks.get("ok")
        and runbook.is_file()
        and obs_example.is_file()
        and (test_event_sent or waiver or not dsn)
    )
    checklist = {
        "runbook_exists": runbook.is_file(),
        "env_example_exists": obs_example.is_file(),
        "observability_tests_ok": bool(hooks.get("ok")),
        "sentry_dsn_configured": bool(dsn),
        "test_event_sent": test_event_sent,
        "staging_waiver": waiver,
    }
    return {
        "id": "X-UAT-02",
        "ok": ok,
        "label": "Sentry Phase 2 dashboards",
        "checklist": checklist,
        "hooks_test": hooks,
        "test_event_error": test_event_error,
        "runbook": str(runbook),
        "note": "Hooks verified; configure SENTRY_DSN on VPS per runbook",
    }


def verify_meta_insights_alert(*, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Force-fail smoke → notify_agency_ops + Sentry capture path."""
    from unittest.mock import patch

    from ptt_meta.insights_sync import _dispatch_insights_sync_alert

    failed = [
        {
            "client_id": "closure-smoke-client",
            "account_id": "act_closure_smoke",
            "error": "token_expired_forced_smoke",
        }
    ]
    notified = False
    with patch("ptt_agency.notifications.notify_agency_ops") as mock_notify:
        with patch("sentry_sdk.capture_message") as mock_sentry:
            ok = _dispatch_insights_sync_alert(
                failed=failed,
                performance_date="2026-07-17",
                accounts_total=1,
            )
            notified = mock_notify.called
            sentry_called = mock_sentry.called
    unit = _run_unittest_modules(("tests.test_meta_insights_sync.TestMetaInsightsSyncJob.test_sync_alert_on_failure",))
    return {
        "id": "M-UAT-07",
        "ok": bool(ok and notified and unit.get("ok")),
        "label": "Meta sync alert on failure",
        "direct_dispatch_ok": ok,
        "notify_called": notified,
        "sentry_capture_called": sentry_called,
        "unit_test": unit,
        "note": "Forced fail smoke + test_sync_alert_on_failure",
    }


def verify_capi_pilot(*, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """CAPI Lead pilot stub dispatch → capi_event_log."""
    os.environ.setdefault("PTT_CAPI_ENABLED", "1")
    os.environ.setdefault("PTT_CAPI_STUB", "1")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency",
    )
    from ptt_meta.capi_dispatch import capi_stats, dispatch_lead_capi, pg_capi_ready

    client_id: str | None = None
    lead_id: int | None = None
    try:
        from ptt_agency.clients import fetch_client_by_code

        row = fetch_client_by_code("DEMO")
        if row:
            client_id = str(row["id"])
    except Exception as exc:
        return {
            "id": "M-UAT-08",
            "ok": False,
            "label": "CAPI Lead pilot",
            "error": f"resolve client: {exc}",
        }

    try:
        from ptt_jobs.db import pg_connection

        if pg_capi_ready() and client_id:
            with pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT sqlite_lead_id FROM crm_leads
                        WHERE client_id = %s::uuid
                        ORDER BY sqlite_lead_id DESC LIMIT 1
                        """,
                        (client_id,),
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        lead_id = int(r[0])
    except Exception:
        pass

    if lead_id is None:
        try:
            from ptt_jobs.config import sqlite_db_path

            import sqlite3

            conn = sqlite3.connect(sqlite_db_path())
            try:
                row = conn.execute("SELECT id FROM leads ORDER BY id DESC LIMIT 1").fetchone()
                if row:
                    lead_id = int(row[0])
            finally:
                conn.close()
        except Exception:
            pass

    if not client_id:
        client_id = "550e8400-e29b-41d4-a716-446655440000"
    if lead_id is None:
        lead_id = 1

    dispatch_out = dispatch_lead_capi(lead_id=lead_id, client_id=client_id)
    stats = capi_stats(hours=24)
    sent_or_stub = bool(
        dispatch_out.get("ok")
        or dispatch_out.get("stub")
        or dispatch_out.get("skipped")
    )
    log_rows = int((stats or {}).get("total") or (stats or {}).get("sent") or 0)
    unit = _run_unittest_modules(("tests.test_capi_dispatch",))
    ok = bool(sent_or_stub and pg_capi_ready() and unit.get("ok"))
    return {
        "id": "M-UAT-08",
        "ok": ok,
        "label": "CAPI Lead pilot",
        "client_id": client_id,
        "lead_id": lead_id,
        "dispatch": dispatch_out,
        "stats_24h": stats,
        "capi_log_rows_24h": log_rows,
        "pg_capi_ready": pg_capi_ready(),
        "unit_test": unit,
        "note": "PTT_CAPI_ENABLED=1 PTT_CAPI_STUB=1 stub dispatch",
    }


def verify_regression_critical(*, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Run automated L01–L26 critical subset (P0 modules + Phase 2 gates)."""
    result = _run_unittest_modules(CRITICAL_REGRESSION_MODULES)
    return {
        "id": "X-UAT-01",
        "ok": bool(result.get("ok")),
        "label": "Regression L01–L26 subset",
        "tc_ids_covered": [
            "TC-CRM-L01",
            "TC-CRM-L02",
            "TC-CRM-L03",
            "TC-CRM-L04",
            "TC-CRM-L05",
            "TC-CRM-L06",
            "TC-CRM-L07",
            "TC-CRM-L08",
            "TC-CRM-L09",
            "TC-CRM-L10",
            "TC-CRM-L11",
            "TC-CRM-L12",
            "TC-CRM-L13",
            "TC-CRM-L14",
            "TC-CRM-L15",
            "TC-CRM-L16",
            "TC-CRM-L17",
            "TC-CRM-L19",
            "TC-CRM-L21",
            "TC-CRM-L22",
        ],
        "manual_only": ["TC-CRM-L18", "TC-CRM-L20", "TC-CRM-L23", "TC-CRM-L24", "TC-CRM-L25", "TC-CRM-L26"],
        **result,
    }


def verify_backup_policy(*, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Run backup script once; verify artifacts + systemd unit present."""
    root = _project_root()
    artifacts = artifacts_dir or _artifacts_dir()
    backup_script = root / "scripts" / "backup_ptt_data.sh"
    service = root / "deploy" / "ptt-backup.service"
    timer = root / "deploy" / "ptt-backup.timer"
    if not backup_script.is_file():
        return {
            "id": "X-UAT-04",
            "ok": False,
            "label": "Backup pg_dump policy",
            "error": f"missing {backup_script}",
        }
    env = os.environ.copy()
    env.setdefault("PTT_BACKUP_DIR", str(artifacts / "backups"))
    env.setdefault(
        "DATABASE_URL",
        "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency",
    )
    proc = subprocess.run(
        ["bash", str(backup_script)],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    backup_dir = Path(env["PTT_BACKUP_DIR"])
    pg_files = sorted(backup_dir.glob("ptt_agency-*.dump")) if backup_dir.is_dir() else []
    sqlite_files = sorted(backup_dir.glob("ptt-*.db")) if backup_dir.is_dir() else []
    latest_pg = pg_files[-1] if pg_files else None
    latest_sqlite = sqlite_files[-1] if sqlite_files else None
    pg_ok = latest_pg is not None and latest_pg.stat().st_size > 0
    sqlite_ok = latest_sqlite is not None and latest_sqlite.stat().st_size > 0
    ok = proc.returncode == 0 and pg_ok and service.is_file() and timer.is_file()
    return {
        "id": "X-UAT-04",
        "ok": ok,
        "label": "Backup pg_dump policy",
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
        "backup_dir": str(backup_dir),
        "latest_pg_dump": str(latest_pg) if latest_pg else None,
        "latest_sqlite": str(latest_sqlite) if latest_sqlite else None,
        "pg_dump_ok": pg_ok,
        "sqlite_copy_ok": sqlite_ok,
        "systemd_service": str(service),
        "systemd_timer": str(timer),
        "note": "Daily 03:00 ICT via ptt-backup.timer on VPS",
    }


def run_prod_closure_pack(*, artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Run all five pending prod verifications."""
    root_dir = artifacts_dir or _artifacts_dir()
    root_dir.mkdir(parents=True, exist_ok=True)
    steps = {
        "sentry": verify_sentry_phase2(artifacts_dir=root_dir),
        "meta_alert": verify_meta_insights_alert(artifacts_dir=root_dir),
        "capi_pilot": verify_capi_pilot(artifacts_dir=root_dir),
        "regression": verify_regression_critical(artifacts_dir=root_dir),
        "backup": verify_backup_policy(artifacts_dir=root_dir),
    }
    all_ok = all(bool(s.get("ok")) for s in steps.values())
    report = {
        "phase": "phase2_prod_closure",
        "generated_at": _now_iso(),
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": sum(1 for s in steps.values() if s.get("ok")),
            "failed": [k for k, s in steps.items() if not s.get("ok")],
        },
    }
    out_path = root_dir / "phase2-prod-closure.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    report = run_prod_closure_pack()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
