#!/usr/bin/env python3
"""Staging Phase 4 gate pack — Phase 3 prereq, DDL v5, campaign writes, Flask readonly."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(ROOT), env=os.environ.copy(), text=True, capture_output=True)
    if check and proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{tail}")
    return proc


def ensure_phase3_qa(*, refresh: bool) -> dict[str, Any]:
    artifacts = Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))
    qa_path = artifacts / "phase3-qa-gate-report.json"
    if qa_path.is_file() and not refresh:
        data = json.loads(qa_path.read_text(encoding="utf-8"))
        return {"ok": bool(data.get("ok")), "refreshed": False, "path": str(qa_path)}

    print("==> Refresh Phase 3 staging gates (prerequisite)")
    proc = _run(["bash", str(ROOT / "scripts/staging_phase3_gate_pack.sh"), "--skip-temporal", "--skip-playwright", "--skip-build"])
    if proc.returncode != 0:
        return {"ok": False, "refreshed": True, "error": "phase3_staging_failed", "tail": (proc.stderr or "")[-500:]}
    data = json.loads(qa_path.read_text(encoding="utf-8"))
    return {"ok": bool(data.get("ok")), "refreshed": True, "path": str(qa_path)}


def run_phase4_gates() -> dict[str, Any]:
    proc = _run(["bash", str(ROOT / "scripts/phase4_gate.sh")])
    artifacts = Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))
    report_path = artifacts / "phase4-gate-report.json"
    report: dict[str, Any] = {}
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "ok": proc.returncode == 0 and bool(report.get("ok")),
        "exit_code": proc.returncode,
        "report": report.get("summary"),
    }


def run_preflight_dry() -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("PTT_CUTOVER_SKIP_PILOT", "1")
    env.setdefault("PTT_CUTOVER_ENV", "staging")
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.phase4_prod_cutover_preflight"],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def verify_flask_readonly_mode() -> dict[str, Any]:
    from ptt_crm.config import flask_monolith_mode
    from ptt_crm.flask_guard import flask_monolith_readonly

    mode = flask_monolith_mode()
    return {
        "ok": mode == "readonly" and flask_monolith_readonly(),
        "mode": mode,
        "readonly": flask_monolith_readonly(),
    }


def write_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Staging Phase 4 gate pack")
    parser.add_argument("--refresh-phase3", action="store_true", help="Re-run Phase 3 staging pack first")
    parser.add_argument("--skip-phase3", action="store_true", help="Require existing phase3-qa-gate-report.json")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--with-clickhouse", action="store_true", help="Enable ClickHouse export gate (needs docker)")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "staging-phase4-gate-report.json"),
    )
    args = parser.parse_args()

    os.environ.setdefault("PTT_ARTIFACTS_DIR", str(ROOT / ".local-dev"))
    os.environ.setdefault("DATABASE_URL", "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency")
    os.environ.setdefault("PTT_SQLITE_PATH", str(ROOT / "ptt.db"))
    os.environ.setdefault("PTT_FLASK_MONOLITH_MODE", "readonly")
    os.environ.setdefault("PTT_META_CAMPAIGN_WRITE_STUB", "1")
    os.environ.setdefault("PHASE4_SKIP_CLICKHOUSE", "0" if args.with_clickhouse else "1")
    os.environ.setdefault("PHASE4_SKIP_NEST_JEST", "1")
    os.environ.setdefault("PTT_CUTOVER_SKIP_PILOT", "1")

    steps: dict[str, Any] = {}
    print("==> Staging Phase 4 gate pack")

    if args.skip_phase3:
        from ptt_crm.phase4_gates import verify_phase3_prerequisite

        steps["phase3_prereq"] = verify_phase3_prerequisite()
        if not steps["phase3_prereq"].get("ok"):
            print(json.dumps(steps, indent=2))
            return 1
    else:
        steps["phase3"] = ensure_phase3_qa(refresh=args.refresh_phase3)
        if not steps["phase3"].get("ok"):
            print(json.dumps(steps, indent=2))
            return 1

    steps["flask_mode"] = verify_flask_readonly_mode()
    steps["phase4_gates"] = run_phase4_gates()
    if not args.skip_preflight:
        steps["preflight_dry"] = run_preflight_dry()

    failed = [k for k, v in steps.items() if not v.get("ok")]
    report = {
        "phase": "staging_phase4_gate_pack",
        "ok": len(failed) == 0,
        "failed_steps": failed,
        "steps": steps,
        "env_hint": "source deploy/env.staging-phase4.example",
        "next": {
            "flask_ui": "PTT_FLASK_MONOLITH_MODE=readonly flask run --port 5050",
            "prod_cutover_dry": "APPLY=0 ./scripts/close_phase4_prod_cutover.sh",
            "prod_cutover": "see deploy/env.phase4-prod.example",
        },
    }
    out = write_report(report, Path(args.report))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:8000])
    print("")
    if report["ok"]:
        print(f"OK  Staging Phase 4 gate pack — {out}")
        return 0
    print(f"FAIL Staging Phase 4 — failed: {failed} — {out}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
