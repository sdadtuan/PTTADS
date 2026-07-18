#!/usr/bin/env python3
"""Prod cutover gates — OpenAPI freeze CI + 48h soak evidence (Phase 2)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Write cutover production gates")
    parser.add_argument("--skip-contract", action="store_true", help="Skip OpenAPI contract CI")
    parser.add_argument("--skip-soak", action="store_true", help="Skip 48h soak gate")
    parser.add_argument("--skip-live-dual-run", action="store_true", help="Skip live dual-run check")
    parser.add_argument("--skip-lead-assigned", action="store_true", help="Skip LeadAssigned RMQ E2E")
    parser.add_argument("--skip-rollback-drill", action="store_true", help="Skip rollback drill evidence")
    parser.add_argument("--required-hours", type=float, default=48.0)
    parser.add_argument("--min-samples", type=int, default=24)
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--report", default=str(ROOT / ".local-dev" / "write-cutover-prod-gates.json"))
    args = parser.parse_args()

    steps: dict[str, dict] = {}

    from ptt_crm.phase2_prereqs import ensure_phase2_write_gates

    prereq = ensure_phase2_write_gates(repair_shadow=True)
    steps["phase2_prerequisites"] = prereq

    if not args.skip_contract:
        proc = subprocess.run(
            [str(ROOT / "scripts" / "ci_openapi_write_freeze.sh")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        steps["openapi_freeze_ci"] = {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-1000:],
        }
        print(proc.stdout or proc.stderr)
        if proc.returncode != 0:
            print("FAIL openapi freeze CI", file=sys.stderr)

    if not args.skip_soak:
        from ptt_crm.write_soak_evidence import evaluate_soak_gate, soak_log_path

        gate = evaluate_soak_gate(
            required_hours=args.required_hours,
            min_ok_samples=args.min_samples,
        )
        steps["soak_48h"] = gate
        status = "OK" if gate["ok"] else "FAIL"
        print(
            f"{status} soak-48h span={gate.get('span_hours')}h "
            f"ok={gate.get('ok_sample_count')} log={soak_log_path()}"
        )
        if not gate["ok"]:
            print(f"  reason: {gate.get('reason')}", file=sys.stderr)

    if not args.skip_live_dual_run:
        try:
            from ptt_crm.lead_shadow_sync import sync_shadow_incremental, sync_shadow_repair_gaps

            sync_shadow_incremental()
            sync_shadow_repair_gaps()
        except Exception as exc:
            steps["shadow_sync_before_dual_run"] = {"ok": False, "error": str(exc)}

        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "dual_run_write_check.py"),
                "--sample",
                str(args.sample),
                "--quiet",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT)},
        )
        line = (proc.stdout or proc.stderr or "").strip()
        steps["live_dual_run"] = {"ok": proc.returncode == 0, "summary": line}
        print(line)
        if proc.returncode != 0:
            print("FAIL live dual-run", file=sys.stderr)

    if not getattr(args, "skip_lead_assigned", False):
        from ptt_crm.lead_assigned_e2e import run_lead_assigned_rmq_e2e

        e2e = run_lead_assigned_rmq_e2e()
        steps["lead_assigned_rmq_e2e"] = e2e
        status = "OK" if e2e.get("ok") else "FAIL"
        print(f"{status} lead-assigned-rmq-e2e lead_id={e2e.get('lead_id')}")
        if not e2e.get("ok"):
            print(f"  error: {e2e.get('error')}", file=sys.stderr)

    if not getattr(args, "skip_rollback_drill", False):
        from ptt_crm.rollback_drill_evidence import run_rollback_drill_evidence

        drill = run_rollback_drill_evidence(include_shell=False)
        steps["rollback_drill_evidence"] = drill
        status = "OK" if drill.get("ok") else "FAIL"
        print(
            f"{status} rollback-drill elapsed={drill.get('rollback_elapsed_sec')}s "
            f"target={drill.get('rollback_target_sec')}s"
        )

    report = {
        "ok": all(s.get("ok") for s in steps.values()) and prereq.get("ok", True),
        "steps": steps,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print("")
    if report["ok"]:
        print(f"OK  write cutover prod gates passed — {report_path}")
        return 0
    failed = [k for k, v in steps.items() if not v.get("ok")]
    print(f"FAIL prod gates — failed: {failed} — {report_path}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
