"""Production write cutover assistant — runbook §4–§8 (Phase 2)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

W5_DEFER_NOTE = (
    "W5 prod POST /api/v1/leads available when PTT_LEADS_CREATE_ID_MODE=prod "
    "(Sprint 0 — apply ./scripts/apply_pg_ddl_v3_sprint0.sh). "
    "Default staging uses id≥900_000_000. Phase 2 prod cutover may still be PATCH-only until W5 enabled."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def preflight_prod_cutover() -> dict[str, Any]:
    """Pre-cutover checks before change window."""
    steps: dict[str, Any] = {}
    issues: list[str] = []

    try:
        from ptt_crm.pg_schema import pg_v3_ready

        steps["pg_v3"] = {"ok": pg_v3_ready()}
    except Exception as exc:
        steps["pg_v3"] = {"ok": False, "error": str(exc)}

    try:
        from ptt_crm.staging_write_pilot import fetch_nest_health, run_preflight_gates

        health = fetch_nest_health()
        nest_ok = bool(health.get("ok"))
        steps["nest_reachable"] = {"ok": nest_ok, "health": health}
        if not nest_ok:
            issues.append("nest_unreachable")

        pilot = run_preflight_gates(expect_pg_primary=False)
        steps["write_pilot_preflight"] = pilot
        if not pilot.get("ok"):
            issues.extend(pilot.get("issues") or [])
    except Exception as exc:
        steps["write_pilot_preflight"] = {"ok": False, "error": str(exc)}
        issues.append("preflight_error")

    soak_script = _project_root() / "scripts" / "write_cutover_prod_gates.py"
    if soak_script.is_file():
        proc = subprocess.run(
            [
                sys.executable,
                str(soak_script),
                "--skip-live-dual-run",
                "--skip-lead-assigned",
                "--skip-rollback-drill",
            ],
            cwd=str(_project_root()),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(_project_root())},
        )
        steps["soak_gate"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
        if proc.returncode != 0:
            issues.append("soak_48h_not_pass")
    else:
        steps["soak_gate"] = {"ok": False, "error": "gate_script_missing"}

    steps["w5_decision"] = {
        "ok": True,
        "deferred": True,
        "note": W5_DEFER_NOTE,
    }

    ok = len(issues) == 0 and all(
        v.get("ok") for k, v in steps.items() if k != "w5_decision" and isinstance(v, dict)
    )
    return {"ok": ok, "issues": issues, "steps": steps}


def apply_cutover_flags(*, dry_run: bool = True) -> dict[str, Any]:
    """
    Runbook §4 steps — flag simulation or env export for operators.

    Does NOT restart systemd on dry_run; records intended flag values.
    """
    flags = {
        "PTT_LEAD_SHADOW_SYNC": "1",
        "PTT_LEAD_REPLICA_SYNC": "0",
        "PTT_LEADS_WRITE_ENABLED": "1",
        "PTT_LEADS_WRITE_UPSTREAM": "nest",
        "sync_mode": "pg_primary",
    }
    result: dict[str, Any] = {"ok": True, "dry_run": dry_run, "flags": flags, "actions": []}

    if dry_run:
        result["actions"].append("DRY_RUN — set flags on Flask .env + ptt-crm-api.env per runbook §4")
        result["actions"].append("DRY_RUN — UPDATE crm_leads_sync_state SET sync_mode='pg_primary'")
        return result

    try:
        from ptt_crm.staging_write_pilot import set_sync_mode

        sync = set_sync_mode("pg_primary")
        result["sync_mode"] = sync
        if not sync.get("ok"):
            result["ok"] = False
    except Exception as exc:
        result["ok"] = False
        result["sync_mode_error"] = str(exc)

    for key, val in flags.items():
        if key != "sync_mode":
            os.environ[key] = val
    result["actions"].append("env_flags_set_in_process")
    result["note"] = "Restart ptt, ptt-crm-api, ptt-worker on VPS after updating service env files"
    return result


def post_cutover_verify(*, sample: int = 20) -> dict[str, Any]:
    """Runbook §4 Bước 5 — shadow, dual-run, events."""
    root = _project_root()
    steps: dict[str, Any] = {}

    shadow_script = root / "scripts" / "sync_lead_shadow.sh"
    if shadow_script.is_file():
        proc = subprocess.run(
            [str(shadow_script), "incremental"],
            cwd=str(root),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(root)},
        )
        steps["shadow_sync"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    else:
        steps["shadow_sync"] = {"ok": False, "error": "script_missing"}

    dual_script = root / "scripts" / "dual_run_write_check.py"
    if dual_script.is_file():
        proc = subprocess.run(
            [sys.executable, str(dual_script), "--sample", str(sample), "--quiet"],
            cwd=str(root),
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(root)},
        )
        steps["dual_run"] = {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "summary": (proc.stdout or proc.stderr or "").strip()[-500:],
        }
    else:
        steps["dual_run"] = {"ok": False, "error": "script_missing"}

    try:
        from ptt_crm.staging_write_pilot import check_lead_assigned_event

        steps["lead_assigned_recent"] = check_lead_assigned_event(within_minutes=60)
    except Exception as exc:
        steps["lead_assigned_recent"] = {"ok": False, "error": str(exc)}

    ok = all(v.get("ok") for v in steps.values() if isinstance(v, dict))
    return {"ok": ok, "steps": steps}


def run_rollback_drill_record() -> dict[str, Any]:
    from ptt_crm.rollback_drill_evidence import run_rollback_drill_evidence

    return run_rollback_drill_evidence(include_shell=False)


def build_prod_cutover_report(
    *,
    phase: str,
    preflight: dict[str, Any] | None = None,
    cutover: dict[str, Any] | None = None,
    post: dict[str, Any] | None = None,
    rollback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    steps = {
        "preflight": preflight or {},
        "cutover": cutover or {},
        "post_verify": post or {},
        "rollback_drill": rollback or {},
    }
    failed = [k for k, v in steps.items() if v and not v.get("ok")]
    return {
        "ok": len(failed) == 0,
        "phase": phase,
        "generated_at": _utc_now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "w5_deferred": True,
        "w5_note": W5_DEFER_NOTE,
        "failed_steps": failed,
        "steps": steps,
    }


def run_prod_cutover_pack(*, dry_run: bool = True, include_rollback: bool = True) -> dict[str, Any]:
    pre = preflight_prod_cutover()
    cut = apply_cutover_flags(dry_run=dry_run)
    post = post_cutover_verify() if not dry_run else {"ok": True, "skipped": True, "reason": "dry_run"}
    roll = run_rollback_drill_record() if include_rollback else {"ok": True, "skipped": True}
    return build_prod_cutover_report(
        phase="prod_write_cutover_dry_run" if dry_run else "prod_write_cutover",
        preflight=pre,
        cutover=cut,
        post=post,
        rollback=roll,
    )


def write_prod_report(report: dict[str, Any], *, path: Path | None = None) -> Path:
    out = path or (_project_root() / ".local-dev" / "prod-write-cutover-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out
