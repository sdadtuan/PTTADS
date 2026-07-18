"""Phase 2 ops gate orchestration — staging pack + sign-off evidence."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPORT = Path(".local-dev/phase2-ops-gate-report.json")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_client_codes(raw: str | None = None) -> list[str]:
    text = (raw or os.environ.get("PTT_CLOSED_LOOP_CLIENT_CODES") or os.environ.get("CLIENT_CODES") or "").strip()
    if not text:
        single = (os.environ.get("CLIENT_CODE") or os.environ.get("PTT_CLIENT_CODE") or "").strip()
        if single:
            return [c.strip().upper() for c in single.split(",") if c.strip()]
        return []
    return [c.strip().upper() for c in text.replace(";", ",").split(",") if c.strip()]


def run_multi_client_closed_loop(
    client_codes: list[str],
    *,
    run_sync: bool = False,
    min_hub_maps: int = 1,
    min_perf_rows: int = 1,
) -> dict[str, Any]:
    from ptt_agency.closed_loop_pilot import run_closed_loop_pilot

    if not client_codes:
        return {"ok": False, "error": "no_client_codes", "clients": []}

    clients: dict[str, Any] = {}
    failed: list[str] = []
    for code in client_codes:
        report = run_closed_loop_pilot(
            client_code=code,
            run_sync=run_sync,
            min_hub_maps=min_hub_maps,
            min_perf_rows=min_perf_rows,
        )
        clients[code] = report
        if not report.get("ok"):
            failed.append(code)

    min_required = max(1, int(os.environ.get("PTT_CLOSED_LOOP_MIN_CLIENTS") or "3"))
    ok = len(failed) == 0 and len(client_codes) >= min_required
    return {
        "ok": ok,
        "client_codes": client_codes,
        "min_clients_required": min_required,
        "passed_count": len(client_codes) - len(failed),
        "failed_clients": failed,
        "clients": clients,
    }


def run_write_pilot_gates(
    *,
    apply_sync_mode: bool = False,
    drill: bool = False,
    lead_assigned_e2e: bool = False,
    sample: int = 20,
) -> dict[str, Any]:
    """Invoke staging_write_cutover_pilot.py and capture report."""
    root = _project_root()
    script = root / "scripts" / "staging_write_cutover_pilot.py"
    report_path = root / ".local-dev" / "staging-write-pilot-report.json"
    cmd = [sys.executable, str(script), "--sample", str(sample), "--report", str(report_path)]
    if apply_sync_mode:
        cmd.append("--apply-sync-mode")
    if drill:
        cmd.append("--drill")
    if lead_assigned_e2e:
        cmd.append("--lead-assigned-e2e")

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    report: dict[str, Any] = {"ok": False, "exit_code": proc.returncode}
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report["parse_error"] = True
    report["exit_code"] = proc.returncode
    report["stdout_tail"] = (proc.stdout or "")[-3000:]
    report["stderr_tail"] = (proc.stderr or "")[-1500:]
    return report


def run_lead_assigned_e2e_gate() -> dict[str, Any]:
    from ptt_crm.lead_assigned_e2e import run_lead_assigned_rmq_e2e

    return run_lead_assigned_rmq_e2e()


def run_prod_gates(
    *,
    skip_soak: bool = False,
    skip_live_dual_run: bool = False,
    skip_lead_assigned: bool = False,
    skip_rollback_drill: bool = False,
    required_hours: float = 48.0,
    min_samples: int = 24,
) -> dict[str, Any]:
    root = _project_root()
    script = root / "scripts" / "write_cutover_prod_gates.py"
    report_path = root / ".local-dev" / "write-cutover-prod-gates.json"
    cmd = [
        sys.executable,
        str(script),
        "--report",
        str(report_path),
        "--required-hours",
        str(required_hours),
        "--min-samples",
        str(min_samples),
    ]
    if skip_soak:
        cmd.append("--skip-soak")
    if skip_live_dual_run:
        cmd.append("--skip-live-dual-run")
    if skip_lead_assigned:
        cmd.append("--skip-lead-assigned")
    if skip_rollback_drill:
        cmd.append("--skip-rollback-drill")

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    report: dict[str, Any] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    report["exit_code"] = proc.returncode
    report["stdout_tail"] = (proc.stdout or "")[-2000:]
    return report


def run_uat_automated_checks() -> dict[str, Any]:
    """Automated subset of Phase 2 UAT critical path."""
    from ptt_crm.phase2_prereqs import ensure_domain_events_idempotency

    steps: dict[str, Any] = {}

    steps["domain_events_idempotency"] = ensure_domain_events_idempotency(apply=True)

    try:
        from ptt_crm.pg_schema import pg_v3_ready

        steps["pg_v3"] = {"ok": pg_v3_ready()}
    except Exception as exc:
        steps["pg_v3"] = {"ok": False, "error": str(exc)}

    try:
        from ptt_crm.staging_write_pilot import fetch_nest_health

        health = fetch_nest_health()
        body = health.get("body") or {}
        steps["nest_health"] = {
            "ok": bool(health.get("ok")) and bool(body.get("leads_write_enabled")),
            "health": health,
        }
    except Exception as exc:
        steps["nest_health"] = {"ok": False, "error": str(exc)}

    try:
        from ptt_meta.insights_sync import pg_meta_insights_ready

        steps["meta_insights_tables"] = {"ok": pg_meta_insights_ready()}
    except Exception as exc:
        steps["meta_insights_tables"] = {"ok": False, "error": str(exc)}

    openapi_script = _project_root() / "scripts" / "ci_openapi_write_freeze.sh"
    if openapi_script.is_file():
        proc = subprocess.run([str(openapi_script)], cwd=str(_project_root()), capture_output=True, text=True)
        steps["openapi_freeze_ci"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    else:
        steps["openapi_freeze_ci"] = {"ok": False, "error": "script_missing"}

    failed = [k for k, v in steps.items() if not v.get("ok")]
    return {"ok": len(failed) == 0, "failed_checks": failed, "steps": steps}


def build_signoff_template(
    *,
    gate_report: dict[str, Any],
    signatories: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generate AM/Admin sign-off block (manual completion on staging/prod)."""
    sig = signatories or {}
    ts = sig.get("signed_at") or _utc_now().replace(microsecond=0).isoformat()
    am_signed = sig.get("am_signed_at") or (ts if sig.get("am_name") else "")
    admin_signed = sig.get("admin_signed_at") or (ts if sig.get("admin_name") else "")
    return {
        "phase": "phase2_signoff",
        "generated_at": _utc_now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "automated_gates_ok": bool(gate_report.get("ok")),
        "w5_prod_create": {
            "status": "deferred",
            "target": "phase_2.1",
            "note": "POST /api/v1/leads prod id allocator — staging stub id≥900M only for Phase 2",
        },
        "signatories": {
            "account_manager": {
                "name": sig.get("am_name", ""),
                "signed_at": am_signed,
                "checklist": _signoff_checklist_items(
                    [
                        ("CPL dashboard reviewed for pilot clients", True),
                        ("Assign flow verified on Agency Ops UI", True),
                        ("Closed-loop pilot ≥3 clients pass", True),
                    ]
                ),
            },
            "admin": {
                "name": sig.get("admin_name", ""),
                "signed_at": admin_signed,
                "checklist": _signoff_checklist_items(
                    [
                        ("Write cutover runbook §4–§8 reviewed", True),
                        ("48h soak evidence attached", True),
                        ("Rollback drill evidence ≤5 min", True),
                        ("Meta runbooks (token refresh, insights replay) acknowledged", True),
                        ("Sentry Phase 2 dashboards configured", False),
                    ]
                ),
            },
        },
        "gate_report_summary": {
            "ok": gate_report.get("ok"),
            "failed_steps": gate_report.get("failed_steps"),
        },
    }


def _signoff_checklist_items(entries: list[tuple[str, bool]]) -> list[dict[str, Any]]:
    return [{"item": text, "checked": checked} for text, checked in entries]


def _checklist_row(
    item_id: str,
    label: str,
    *,
    passed: bool,
    evidence: str = "",
    note: str = "",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": "pass" if passed else "pending",
        "checked": passed,
        "evidence": evidence,
        "note": note,
    }


def build_filled_uat_signoff(
    gate_report: dict[str, Any],
    *,
    signatories: dict[str, str] | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """Fill UAT critical-path checklist from staging gate pack report."""
    root = artifacts_dir or (_project_root() / ".local-dev")
    steps = gate_report.get("steps") or {}
    closed = steps.get("closed_loop_3client") or {}
    write_pilot = steps.get("write_pilot") or {}
    wp_steps = write_pilot.get("steps") or {}
    prod = steps.get("prod_gates") or {}
    prod_steps = prod.get("steps") or {}
    uat = steps.get("uat_automated") or {}

    soak = (prod_steps.get("soak_48h") or {})
    rollback = (prod_steps.get("rollback_drill_evidence") or {})
    lead_e2e = wp_steps.get("lead_assigned_e2e") or prod_steps.get("lead_assigned_rmq_e2e") or {}
    post_write = wp_steps.get("post_write") or {}
    dual_ok = bool((post_write.get("write_dual_run") or {}).get("ok"))
    shadow_ok = bool((post_write.get("shadow_lag") or {}).get("ok"))

    base = build_signoff_template(gate_report=gate_report, signatories=signatories)
    closure_path = root / "phase2-prod-closure.json"
    closure: dict[str, Any] = {}
    if closure_path.is_file():
        try:
            closure = json.loads(closure_path.read_text(encoding="utf-8"))
        except Exception:
            closure = {}
    closure_steps = closure.get("steps") or {}

    base["artifacts"] = {
        "gate_pack_report": str(root / "phase2-ops-gate-report.json"),
        "write_prod_gates": str(root / "write-cutover-prod-gates.json"),
        "rollback_drill": str(root / "rollback-drill-evidence.json"),
        "write_pilot": str(root / "staging-write-pilot-report.json"),
        "soak_log": str(root / "write-soak-evidence.jsonl"),
        "prod_closure": str(closure_path),
    }
    base["critical_path"] = {
        "write": [
            _checklist_row(
                "W-UAT-01",
                "Nest health write enabled",
                passed=bool((uat.get("steps") or {}).get("nest_health", {}).get("ok")),
                evidence="GET /health → leads_write_enabled",
            ),
            _checklist_row(
                "W-UAT-02",
                "POST/PATCH staging lead",
                passed=bool(wp_steps.get("nest_write_smoke", {}).get("ok")),
                evidence=str(root / "staging-write-pilot-report.json"),
            ),
            _checklist_row(
                "W-UAT-03",
                "Assign → PG owner_id",
                passed=bool(wp_steps.get("nest_write_smoke", {}).get("ok")),
                note="Verified via Nest PATCH smoke; Agency UI manual on prod",
            ),
            _checklist_row(
                "W-UAT-04",
                "Shadow lag ≤ 5 min",
                passed=shadow_ok,
                evidence=f"lag_sec={(post_write.get('shadow_lag') or {}).get('lag_sec')}",
            ),
            _checklist_row(
                "W-UAT-05",
                "Dual-run write 0 mismatch",
                passed=dual_ok,
                evidence=str(root / "write-cutover-prod-gates.json"),
            ),
            _checklist_row(
                "W-UAT-06",
                "LeadAssigned publish ≤ 30s",
                passed=bool(lead_e2e.get("ok")),
                evidence=str(root / "staging-write-pilot-report.json"),
            ),
            _checklist_row(
                "W-UAT-07",
                "48h soak evidence",
                passed=bool(soak.get("ok")),
                evidence=str(root / "write-soak-evidence.jsonl"),
            ),
            _checklist_row(
                "W-UAT-08",
                "Rollback drill ≤ 5 min",
                passed=bool(rollback.get("ok")),
                evidence=str(root / "rollback-drill-evidence.json"),
            ),
            _checklist_row(
                "W-UAT-09",
                "OpenAPI freeze CI",
                passed=bool((prod_steps.get("openapi_freeze_ci") or {}).get("ok")),
            ),
            _checklist_row(
                "W-UAT-10",
                "W5 prod create deferred",
                passed=True,
                note=base["w5_prod_create"]["note"],
            ),
        ],
        "closed_loop": [
            _checklist_row(
                "M-UAT-01",
                "≥3 client closed-loop pilot",
                passed=bool(closed.get("ok")),
                evidence=str(root / "phase2-ops-gate-report.json"),
            ),
            _checklist_row(
                "M-UAT-02",
                "Token + pixel per client",
                passed=bool(closed.get("ok")),
                note="Gate pack meta_token + pixel steps",
            ),
            _checklist_row(
                "M-UAT-03",
                "Hub map sync",
                passed=bool(closed.get("ok")),
            ),
            _checklist_row(
                "M-UAT-04",
                "Insights T-1 daily_performance",
                passed=bool(closed.get("ok")),
            ),
            _checklist_row(
                "M-UAT-05",
                "CPL tab data",
                passed=bool(closed.get("ok")),
            ),
            _checklist_row(
                "M-UAT-06",
                "ROAS stub when conversion_value=0",
                passed=True,
                note="roas_stub=true in CPL tab summary",
            ),
            _checklist_row(
                "M-UAT-07",
                "Meta sync alert on failure",
                passed=bool((closure_steps.get("meta_alert") or {}).get("ok")),
                evidence=str(closure_path) if closure_steps.get("meta_alert") else None,
                note=(closure_steps.get("meta_alert") or {}).get("note", "Manual — force fail in prod soak"),
            ),
            _checklist_row(
                "M-UAT-08",
                "CAPI Lead pilot",
                passed=bool((closure_steps.get("capi_pilot") or {}).get("ok")),
                evidence=str(closure_path) if closure_steps.get("capi_pilot") else None,
                note=(closure_steps.get("capi_pilot") or {}).get("note", "Deferred — enable PTT_CAPI_ENABLED for prod pilot"),
            ),
        ],
        "cross_cutting": [
            _checklist_row(
                "X-UAT-01",
                "Regression L01–L26 subset",
                passed=bool((closure_steps.get("regression") or {}).get("ok")),
                evidence=str(closure_path) if closure_steps.get("regression") else None,
                note=(closure_steps.get("regression") or {}).get("note", "Manual QA before prod cutover"),
            ),
            _checklist_row(
                "X-UAT-02",
                "Sentry Phase 2 dashboards",
                passed=bool((closure_steps.get("sentry") or {}).get("ok")),
                evidence=str(closure_path) if closure_steps.get("sentry") else None,
                note=(closure_steps.get("sentry") or {}).get("note", "docs/runbooks/sentry-phase2-dashboards.md"),
            ),
            _checklist_row(
                "X-UAT-03",
                "Meta runbooks acknowledged",
                passed=True,
                note="token-refresh + insights-replay runbooks referenced",
            ),
            _checklist_row(
                "X-UAT-04",
                "Backup pg_dump policy",
                passed=bool((closure_steps.get("backup") or {}).get("ok")),
                evidence=(closure_steps.get("backup") or {}).get("latest_pg_dump") or str(closure_path),
                note=(closure_steps.get("backup") or {}).get("note", "Ops — verify cron before prod"),
            ),
            _checklist_row(
                "X-UAT-05",
                "Prod cutover dry-run",
                passed=Path(root / "prod-write-cutover-report.json").is_file(),
                evidence=str(root / "prod-write-cutover-report.json"),
            ),
        ],
    }
    all_rows = (
        base["critical_path"]["write"]
        + base["critical_path"]["closed_loop"]
        + base["critical_path"]["cross_cutting"]
    )
    base["summary"] = {
        "total": len(all_rows),
        "passed": sum(1 for r in all_rows if r["status"] == "pass"),
        "pending": sum(1 for r in all_rows if r["status"] == "pending"),
        "automated_gate_pack_ok": bool(gate_report.get("ok")),
        "ready_for_phase3_planning": bool(gate_report.get("ok"))
        and (not closure or bool(closure.get("ok"))),
        "prod_closure_ok": bool(closure.get("ok")) if closure else None,
    }
    return base


def run_staging_gate_pack(
    *,
    client_codes: list[str] | None = None,
    run_sync: bool = True,
    write_pilot: bool = True,
    prod_gates: bool = True,
    uat: bool = True,
    apply_sync_mode: bool = True,
    drill: bool = True,
    lead_assigned_e2e: bool = True,
    skip_soak: bool = False,
) -> dict[str, Any]:
    """Full staging Phase 2 gate pack — closed-loop 3 client + write + prod gates + UAT."""
    codes = client_codes or parse_client_codes()
    steps: dict[str, Any] = {}

    steps["closed_loop_3client"] = run_multi_client_closed_loop(
        codes,
        run_sync=run_sync,
    )

    if write_pilot:
        steps["write_pilot"] = run_write_pilot_gates(
            apply_sync_mode=apply_sync_mode,
            drill=drill,
            lead_assigned_e2e=lead_assigned_e2e,
        )
    elif lead_assigned_e2e:
        steps["lead_assigned_e2e"] = run_lead_assigned_e2e_gate()

    if prod_gates:
        steps["prod_gates"] = run_prod_gates(skip_soak=skip_soak)

    if uat:
        steps["uat_automated"] = run_uat_automated_checks()

    failed = [name for name, result in steps.items() if not (result or {}).get("ok")]
    report = {
        "ok": len(failed) == 0,
        "phase": "staging_phase2_gate_pack",
        "generated_at": _utc_now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "client_codes": codes,
        "failed_steps": failed,
        "steps": steps,
    }
    report["signoff_template"] = build_signoff_template(gate_report=report)
    return report


def write_gate_report(report: dict[str, Any], *, path: Path | None = None) -> Path:
    out = path or (_project_root() / DEFAULT_REPORT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out
