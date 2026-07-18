"""Write cutover rollback drill evidence (Phase 2 P1 #9)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPORT = Path(".local-dev/rollback-drill-evidence.json")
ROLLBACK_TARGET_SEC = 300


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def report_path() -> Path:
    raw = (os.environ.get("PTT_ROLLBACK_DRILL_REPORT") or "").strip()
    return Path(raw) if raw else _project_root() / DEFAULT_REPORT


def simulate_flag_cutover() -> dict[str, Any]:
    """Phase A — cutover flags (mirrors local_leads_write_cutover_drill.sh)."""
    from ptt_crm.config import leads_write_upstream

    start = time.monotonic()
    flags = {
        "PTT_LEADS_WRITE_ENABLED": "1",
        "PTT_LEADS_WRITE_UPSTREAM": "nest",
        "PTT_LEAD_SHADOW_SYNC": "1",
        "PTT_LEAD_REPLICA_SYNC": "0",
    }
    for key, val in flags.items():
        os.environ[key] = val
    elapsed = time.monotonic() - start
    upstream = leads_write_upstream()
    ok = upstream == "nest" and os.environ.get("PTT_LEADS_WRITE_ENABLED") == "1"
    return {"ok": ok, "flags": flags, "write_upstream": upstream, "elapsed_sec": round(elapsed, 3)}


def simulate_flag_rollback() -> dict[str, Any]:
    """Phase B — rollback flags (target ≤ 5 min)."""
    from ptt_crm.config import leads_write_upstream

    start = time.monotonic()
    flags = {
        "PTT_LEADS_WRITE_UPSTREAM": "flask",
        "PTT_LEADS_WRITE_ENABLED": "0",
        "PTT_LEAD_REPLICA_SYNC": "1",
        "PTT_LEAD_SHADOW_SYNC": "0",
    }
    for key, val in flags.items():
        os.environ[key] = val
    elapsed = time.monotonic() - start
    upstream = leads_write_upstream()
    ok = upstream == "flask" and os.environ.get("PTT_LEADS_WRITE_ENABLED") == "0"
    within_target = elapsed <= ROLLBACK_TARGET_SEC
    return {
        "ok": ok and within_target,
        "flags": flags,
        "write_upstream": upstream,
        "elapsed_sec": round(elapsed, 3),
        "target_sec": ROLLBACK_TARGET_SEC,
        "within_target": within_target,
    }


def run_shell_drill(*, root: Path | None = None) -> dict[str, Any]:
    """Run full shell drill script and capture exit code."""
    project = root or _project_root()
    script = project / "scripts" / "local_leads_write_cutover_drill.sh"
    if not script.is_file():
        return {"ok": False, "error": "drill_script_missing", "path": str(script)}
    start = time.monotonic()
    proc = subprocess.run(
        [str(script)],
        cwd=str(project),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(project)},
    )
    elapsed = time.monotonic() - start
    out = (proc.stdout or "") + (proc.stderr or "")
    rollback_elapsed: float | None = None
    total_elapsed: float | None = None
    for line in out.splitlines():
        if "Rollback flag simulation:" in line:
            try:
                rollback_elapsed = float(line.split(":")[-1].strip().rstrip("s"))
            except ValueError:
                pass
        if "Total drill:" in line:
            try:
                total_elapsed = float(line.split(":")[-1].strip().rstrip("s"))
            except ValueError:
                pass
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "elapsed_sec": round(elapsed, 3),
        "rollback_elapsed_sec": rollback_elapsed,
        "total_elapsed_sec": total_elapsed,
        "stdout_tail": out[-3000:],
    }


def build_drill_report(
    *,
    cutover: dict[str, Any],
    rollback: dict[str, Any],
    shell: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rollback_sec = float(rollback.get("elapsed_sec") or 0)
    ok = bool(cutover.get("ok")) and bool(rollback.get("ok"))
    if shell is not None:
        ok = ok and bool(shell.get("ok"))
        if shell.get("rollback_elapsed_sec") is not None:
            rollback_sec = float(shell["rollback_elapsed_sec"])
    return {
        "ok": ok,
        "generated_at": _utc_now().replace(microsecond=0).isoformat(),
        "host": socket.gethostname(),
        "rollback_elapsed_sec": rollback_sec,
        "rollback_target_sec": ROLLBACK_TARGET_SEC,
        "rollback_within_target": rollback_sec <= ROLLBACK_TARGET_SEC,
        "steps": {
            "cutover_flags": cutover,
            "rollback_flags": rollback,
            **({"shell_drill": shell} if shell is not None else {}),
        },
    }


def write_drill_report(report: dict[str, Any], *, path: Path | None = None) -> Path:
    out = path or report_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out


def run_rollback_drill_evidence(*, include_shell: bool = True) -> dict[str, Any]:
    """Record rollback drill evidence for runbook §7."""
    cutover = simulate_flag_cutover()
    rollback = simulate_flag_rollback()
    shell = run_shell_drill() if include_shell else None
    report = build_drill_report(cutover=cutover, rollback=rollback, shell=shell)
    path = write_drill_report(report)
    report["report_path"] = str(path)
    return report
