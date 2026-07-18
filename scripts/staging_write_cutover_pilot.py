#!/usr/bin/env python3
"""CLI — staging write cutover pilot (Phase 2 P0 #3)."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_script(path: Path, *args: str) -> tuple[int, str]:
    cmd = [str(path), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _parse_lead_id(smoke_output: str) -> int | None:
    for pattern in (r"lead_id=(\d+)", r'"id"\s*:\s*(\d+)'):
        m = re.search(pattern, smoke_output, re.I)
        if m:
            return int(m.group(1))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Staging write cutover pilot gates")
    parser.add_argument("--apply-sync-mode", action="store_true", help="Set sync_mode=pg_primary")
    parser.add_argument("--drill", action="store_true", help="Run rollback drill at end")
    parser.add_argument("--lead-assigned-e2e", action="store_true", help="Run LeadAssigned RMQ E2E gate")
    parser.add_argument("--sample", type=int, default=20, help="Dual-run sample size")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "staging-write-pilot-report.json"),
        help="JSON report output path",
    )
    args = parser.parse_args()

    from ptt_crm.staging_write_pilot import (
        build_pilot_report,
        run_post_write_gates,
        run_preflight_gates,
        set_sync_mode,
    )

    steps: dict[str, dict] = {}

    if args.apply_sync_mode:
        result = set_sync_mode("pg_primary")
        steps["set_sync_mode"] = result
        if not result.get("ok"):
            print(json.dumps(result, indent=2, default=str))
            return 1
        print("OK  sync_mode=pg_primary")

    preflight = run_preflight_gates(expect_pg_primary=args.apply_sync_mode)
    steps["preflight"] = preflight
    print(json.dumps(preflight, indent=2, default=str)[:4000])
    if not preflight.get("ok"):
        print("FAIL preflight", file=sys.stderr)

    code, smoke_out = _run_script(ROOT / "scripts" / "local_leads_write_staging.sh")
    print(smoke_out)
    lead_id = _parse_lead_id(smoke_out)
    steps["nest_write_smoke"] = {"ok": code == 0, "lead_id": lead_id, "exit_code": code}
    if code != 0:
        print("FAIL nest write smoke", file=sys.stderr)

    scode, _ = _run_script(ROOT / "scripts" / "sync_lead_shadow.sh", "incremental")
    steps["shadow_sync"] = {"ok": scode == 0, "exit_code": scode}
    if scode != 0:
        print("FAIL shadow sync", file=sys.stderr)

    try:
        from ptt_crm.lead_shadow_sync import sync_shadow_repair_gaps

        repair = sync_shadow_repair_gaps()
        steps["shadow_repair"] = repair
        if not repair.get("ok"):
            print("WARN shadow repair", repair, file=sys.stderr)
    except Exception as exc:
        steps["shadow_repair"] = {"ok": False, "error": str(exc)}

    post = run_post_write_gates(lead_id=lead_id, sample_size=args.sample)
    steps["post_write"] = post
    print(json.dumps(post, indent=2, default=str)[:4000])
    if not post.get("ok"):
        print("FAIL post-write gates", file=sys.stderr)

    if args.lead_assigned_e2e:
        from ptt_crm.lead_assigned_e2e import run_lead_assigned_rmq_e2e

        e2e = run_lead_assigned_rmq_e2e(lead_id=lead_id)
        steps["lead_assigned_e2e"] = e2e
        print(json.dumps(e2e, indent=2, default=str)[:3000])
        if not e2e.get("ok"):
            print("FAIL lead assigned RMQ E2E", file=sys.stderr)

    if args.drill:
        dcode, drill_out = _run_script(ROOT / "scripts" / "local_leads_write_cutover_drill.sh")
        print(drill_out)
        from ptt_crm.rollback_drill_evidence import build_drill_report, simulate_flag_cutover, simulate_flag_rollback, write_drill_report

        drill_report = build_drill_report(
            cutover=simulate_flag_cutover(),
            rollback=simulate_flag_rollback(),
            shell={"ok": dcode == 0, "exit_code": dcode, "stdout_tail": drill_out[-2000:]},
        )
        drill_path = Path(args.report).parent / "rollback-drill-evidence.json"
        write_drill_report(drill_report, path=drill_path)
        steps["rollback_drill"] = {**drill_report, "report_path": str(drill_path)}
        if not drill_report.get("ok"):
            print("FAIL rollback drill", file=sys.stderr)

    report = build_pilot_report(phase="staging_write_pilot", steps=steps)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("")
    if report["ok"]:
        print(f"OK  staging write pilot passed — report: {report_path}")
        return 0
    print(f"FAIL staging write pilot — failed: {report['failed_steps']} — report: {report_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
