#!/usr/bin/env python3
"""Staging Phase 3 gate pack — DDL, seeds, Nest, track gates, QA aggregate."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(cmd: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=merged,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{tail}")
    return proc


def _http_ok(url: str, *, timeout: float = 5.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except Exception:
        return False


def ensure_postgres() -> dict[str, Any]:
    if not _run(["docker", "compose", "ps", "postgres"], check=False).returncode == 0:
        return {"ok": True, "skipped": True, "reason": "docker_compose_unavailable"}
    _run(["docker", "compose", "up", "-d", "postgres"], check=False)
    for _ in range(45):
        proc = _run(
            ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "ptt", "-d", "ptt_agency"],
            check=False,
        )
        if proc.returncode == 0:
            return {"ok": True}
        time.sleep(1)
    return {"ok": False, "error": "postgres_not_ready"}


def apply_phase3_ddl() -> dict[str, Any]:
    scripts = [
        "scripts/apply_pg_ddl_v2_leads.sh",
        "scripts/apply_pg_ddl_v3.sh",
        "scripts/apply_pg_ddl_v3_sprint0.sh",
        "scripts/apply_pg_ddl_v3_creatives.sh",
        "scripts/apply_pg_ddl_v3_launch_qa.sh",
        "scripts/apply_pg_ddl_v3_google_sync.sh",
        "scripts/apply_pg_ddl_v3_leads_ingest_config.sh",
        "scripts/apply_pg_ddl_v4_hub_sop.sh",
    ]
    applied: list[str] = []
    failed: list[str] = []
    for rel in scripts:
        path = ROOT / rel
        if not path.is_file():
            continue
        proc = _run(["bash", str(path)], check=False)
        if proc.returncode == 0:
            applied.append(rel)
        else:
            failed.append(rel)
    return {"ok": not failed, "applied": applied, "failed": failed}


def ensure_phase2_prereqs() -> dict[str, Any]:
    from ptt_crm.phase2_prereqs import ensure_phase2_write_gates

    return ensure_phase2_write_gates(repair_shadow=True)


def sync_ingest_rules() -> dict[str, Any]:
    proc = _run(["bash", str(ROOT / "scripts/sync_lead_ingest_config.sh")], check=False)
    if proc.returncode != 0:
        return {"ok": False, "stderr": (proc.stderr or "")[-500:]}
    return {"ok": True}


def seed_portal_basics() -> dict[str, Any]:
    py = sys.executable
    _run([py, str(ROOT / "scripts/seed_portal_gate_users.py")])
    _run([py, str(ROOT / "scripts/seed_portal_demo_performance.py"), "--days", "30"], check=False)
    return {"ok": True}


def ensure_nest(*, api_url: str) -> dict[str, Any]:
    health = f"{api_url.rstrip('/')}/health"
    if _http_ok(health):
        return {"ok": True, "started": False, "url": api_url}
    proc = subprocess.Popen(
        ["bash", str(ROOT / "scripts/local_crm_api_up.sh")],
        cwd=str(ROOT),
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if _http_ok(health):
            return {"ok": True, "started": True, "pid": proc.pid, "url": api_url}
        if proc.poll() is not None:
            return {"ok": False, "error": "nest_exited_early", "pid": proc.pid}
        time.sleep(2)
    proc.kill()
    return {"ok": False, "error": "nest_health_timeout"}


def run_track_gates(
    *,
    skip_portal: bool,
    skip_temporal: bool,
    skip_google: bool,
    skip_hub: bool,
    skip_build: bool,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    portal_args = ["--skip-build"] if skip_build else []

    if not skip_portal:
        proc = _run(["bash", str(ROOT / "scripts/phase3_portal_mvp_gate.sh"), *portal_args], check=False)
        steps["portal"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    if not skip_temporal:
        proc = _run(["bash", str(ROOT / "scripts/phase3_temporal_gate.sh")], check=False)
        steps["temporal"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    if not skip_google:
        proc = _run(["bash", str(ROOT / "scripts/phase3_google_gate.sh")], check=False)
        steps["google"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}
    if not skip_hub:
        proc = _run(["bash", str(ROOT / "scripts/phase3_hub_migration_gate.sh")], check=False)
        steps["hub"] = {"ok": proc.returncode == 0, "exit_code": proc.returncode}

    failed = [k for k, v in steps.items() if not v.get("ok")]
    return {"ok": not failed, "steps": steps, "failed": failed}


def run_qa_aggregate(*, run_playwright: bool) -> dict[str, Any]:
    env = os.environ.copy()
    if run_playwright:
        env["RUN_PORTAL_E2E"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.phase3_qa_gates"],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-3000:],
    }


def write_report(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 staging gate pack")
    parser.add_argument("--skip-ddl", action="store_true")
    parser.add_argument("--skip-prereqs", action="store_true")
    parser.add_argument("--skip-ingest-sync", action="store_true")
    parser.add_argument("--skip-portal", action="store_true")
    parser.add_argument("--skip-temporal", action="store_true")
    parser.add_argument("--skip-google", action="store_true")
    parser.add_argument("--skip-hub", action="store_true")
    parser.add_argument("--skip-build", action="store_true", help="Portal gate skips Next build")
    parser.add_argument("--skip-playwright", action="store_true")
    parser.add_argument("--skip-nest", action="store_true")
    parser.add_argument(
        "--report",
        default=str(ROOT / ".local-dev" / "staging-phase3-gate-report.json"),
    )
    args = parser.parse_args()

    api_url = (os.environ.get("PTT_API_URL") or "http://127.0.0.1:3000").rstrip("/")
    os.environ.setdefault("PTT_ARTIFACTS_DIR", str(ROOT / ".local-dev"))
    os.environ.setdefault("DATABASE_URL", "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency")
    os.environ.setdefault("PTT_SQLITE_PATH", str(ROOT / "ptt.db"))

    steps: dict[str, Any] = {}

    print("==> Staging Phase 3 gate pack")
    steps["postgres"] = ensure_postgres()
    if not steps["postgres"].get("ok"):
        print(json.dumps(steps, indent=2))
        return 1

    if not args.skip_ddl:
        print("==> Apply Phase 3 PG DDL")
        steps["ddl"] = apply_phase3_ddl()
    if not args.skip_prereqs:
        print("==> Phase 2 write prerequisites (idempotency + shadow repair + ingest rules)")
        steps["phase2_prereqs"] = ensure_phase2_prereqs()
    if not args.skip_ingest_sync:
        print("==> Sync lead ingest rules snapshot")
        steps["ingest_rules"] = sync_ingest_rules()

    print("==> Seed portal demo users + performance")
    steps["portal_seed"] = seed_portal_basics()

    if not args.skip_nest:
        print("==> Ensure Nest CRM API")
        steps["nest"] = ensure_nest(api_url=api_url)
        if not steps["nest"].get("ok"):
            print(json.dumps(steps, indent=2))
            return 1

    print("==> Phase 3 track gates")
    steps["tracks"] = run_track_gates(
        skip_portal=args.skip_portal,
        skip_temporal=args.skip_temporal,
        skip_google=args.skip_google,
        skip_hub=args.skip_hub,
        skip_build=args.skip_build,
    )

    print("==> Phase 3 QA aggregate")
    steps["qa"] = run_qa_aggregate(run_playwright=not args.skip_playwright)

    failed = [name for name, result in steps.items() if not result.get("ok")]
    report = {
        "phase": "staging_phase3_gate_pack",
        "ok": len(failed) == 0,
        "failed_steps": failed,
        "steps": steps,
        "env_hint": "source deploy/env.staging-phase3.example",
        "next": {
            "manual_stack": "./scripts/staging_phase3_up.sh",
            "playwright": "./scripts/phase3_playwright_e2e_gate.sh",
            "prod_preflight": "./scripts/close_phase3_prod_cutover.sh (after Phase 2 prod soak)",
        },
    }
    out = write_report(report, Path(args.report))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:10000])
    print("")
    if report["ok"]:
        print(f"OK  Staging Phase 3 gate pack — {out}")
        print(f"    QA report: {ROOT / '.local-dev' / 'phase3-qa-gate-report.json'}")
        return 0
    print(f"FAIL Staging Phase 3 — failed: {failed} — {out}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
