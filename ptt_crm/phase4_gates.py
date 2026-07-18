"""Phase 4 gate pack — campaign write, Flask sunset, ClickHouse (F1–F6)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT = "550e8400-e29b-41d4-a716-446655440000"
PILOT_CAMPAIGN = "120210123456789"

PHASE4_UNIT_MODULES: tuple[str, ...] = (
    "tests.test_flask_guard",
    "tests.test_meta_campaign_write_pilot",
    "tests.test_campaign_write_workflow",
    "tests.test_clickhouse_export",
)


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _api_base() -> str:
    return (os.environ.get("PTT_API_URL") or os.environ.get("PTT_NEST_LEADS_URL") or "http://127.0.0.1:3000").rstrip("/")


def _run_unittest_modules(modules: tuple[str, ...]) -> dict[str, Any]:
    python = sys.executable
    root = str(ROOT)
    env = {**os.environ, "PYTHONPATH": root}
    failed: list[str] = []
    output_parts: list[str] = []
    total_run = 0
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
        output_parts.append(f"=== {mod} ===\n{tail[-900:]}")
        import re

        m = re.search(r"Ran (\d+) test", tail)
        if m:
            total_run += int(m.group(1))
        if proc.returncode != 0:
            failed.append(mod)
    return {
        "ok": not failed,
        "tests_run": total_run,
        "modules": list(modules),
        "failed_modules": failed,
        "output_tail": "\n".join(output_parts)[-4000:],
    }


def _http_json(method: str, url: str, *, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    key = (os.environ.get("PTT_CRM_INTERNAL_KEY") or "").strip()
    if key:
        req.add_header("X-PTT-Internal-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {"error": str(exc)}
        except json.JSONDecodeError:
            return exc.code, {"error": raw}


def verify_phase3_prerequisite() -> dict[str, Any]:
    path = _artifacts_dir() / "phase3-qa-gate-report.json"
    if not path.is_file():
        return {"id": "F4-G01", "ok": False, "label": "Phase 3 QA prerequisite", "error": "missing_report"}
    data = json.loads(path.read_text(encoding="utf-8"))
    ok = bool(data.get("ok"))
    return {
        "id": "F4-G01",
        "ok": ok,
        "label": "Phase 3 QA prerequisite",
        "path": str(path.relative_to(ROOT)),
        "generated_at": data.get("generated_at"),
    }


def verify_ddl_v5() -> dict[str, Any]:
    from ptt_crm.pg_schema import pg_campaign_writes_ready

    ok = pg_campaign_writes_ready()
    return {"id": "F4-G02", "ok": ok, "label": "DDL v5 campaign_write_requests"}


def verify_nest_campaign_writes_api() -> dict[str, Any]:
    os.environ.setdefault("PTT_META_CAMPAIGN_WRITE_STUB", "1")
    cid = os.environ.get("PHASE4_PILOT_CLIENT_ID", DEFAULT_CLIENT)
    camp = os.environ.get("PHASE4_PILOT_CAMPAIGN_ID", PILOT_CAMPAIGN)
    api = _api_base()

    status, health = _http_json("GET", f"{api}/health")
    if status != 200:
        return {
            "id": "F4-G03",
            "ok": False,
            "label": "Nest campaign-writes API smoke",
            "error": "nest_unreachable",
            "health_status": status,
        }

    sub_status, sub = _http_json(
        "POST",
        f"{api}/api/v1/campaign-writes",
        body={
            "client_id": cid,
            "external_campaign_id": camp,
            "external_campaign_name": "Phase4 Gate Budget Test",
            "change_type": "daily_budget",
            "new_value": {"daily_budget_vnd": 480000},
            "submitted_by": "phase4-gate@pttads.vn",
        },
    )
    req = sub.get("request") or {}
    req_id = req.get("id")
    ok_submit = sub_status in (200, 201) and req.get("status") == "pending_approval" and bool(req_id)

    list_status, pending = _http_json("GET", f"{api}/api/v1/campaign-writes/pending?client_id={cid}")
    rows = pending.get("rows") or []
    ok_list = list_status == 200 and any(str(r.get("id")) == str(req_id) for r in rows)

    appr_status, appr = _http_json(
        "POST",
        f"{api}/api/v1/campaign-writes/{req_id}/approve",
        body={"approved_by": "admin@pttads.vn", "note": "phase4-gate"},
    )
    ok_approve = appr_status in (200, 201) and (appr.get("request") or {}).get("status") == "approved"

    ok = ok_submit and ok_list and ok_approve
    return {
        "id": "F4-G03",
        "ok": ok,
        "label": "Nest campaign-writes API smoke",
        "submit_status": sub_status,
        "request_id": req_id,
        "list_status": list_status,
        "approve_status": appr_status,
        "temporal_signal": appr.get("temporal_signal"),
    }


def verify_clickhouse_export() -> dict[str, Any]:
    if os.environ.get("PHASE4_SKIP_CLICKHOUSE", "").strip().lower() in {"1", "true", "yes"}:
        return {"id": "F4-G04", "ok": True, "label": "ClickHouse export e2e", "skipped": True}
    script = ROOT / "scripts" / "clickhouse_export_e2e.sh"
    if not script.is_file():
        return {"id": "F4-G04", "ok": False, "label": "ClickHouse export e2e", "error": "script_missing"}
    proc = subprocess.run(
        [str(script)],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {
        "id": "F4-G04",
        "ok": proc.returncode == 0,
        "label": "ClickHouse export e2e",
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def verify_flask_readonly_docs() -> dict[str, Any]:
    runbooks = [
        "docs/runbooks/phase4-kickoff.md",
        "docs/runbooks/phase4-prod-cutover-checklist.md",
        "docs/specs/workflows/campaign-write-approval.md",
        "deploy/env.phase4-prod.example",
    ]
    missing = [r for r in runbooks if not (ROOT / r).is_file()]
    from ptt_crm.config import flask_monolith_mode

    mode = flask_monolith_mode()
    return {
        "id": "F4-G05",
        "ok": not missing,
        "label": "Flask sunset runbooks + env example",
        "missing": missing,
        "current_flask_mode": mode,
        "recommended_prod_mode": "readonly",
    }


def verify_nest_jest_e2e() -> dict[str, Any]:
    if os.environ.get("PHASE4_SKIP_NEST_JEST", "").strip().lower() in {"1", "true", "yes"}:
        return {"id": "F4-G06", "ok": True, "label": "Nest campaign-writes jest e2e", "skipped": True}
    api_dir = ROOT / "services" / "ptt-crm-api"
    if not (api_dir / "node_modules").is_dir():
        return {
            "id": "F4-G06",
            "ok": True,
            "label": "Nest campaign-writes jest e2e",
            "skipped": True,
            "reason": "node_modules missing",
        }
    proc = subprocess.run(
        ["npm", "run", "test:e2e", "--", "--testPathPattern=campaign-writes"],
        cwd=str(api_dir),
        env={
            **os.environ,
            "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency"),
            "PTT_CRM_API_AUTH_DISABLED": "1",
        },
        capture_output=True,
        text=True,
        timeout=300,
    )
    return {
        "id": "F4-G06",
        "ok": proc.returncode == 0,
        "label": "Nest campaign-writes jest e2e",
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def run_phase4_gate_pack() -> dict[str, Any]:
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)

    steps: dict[str, Any] = {
        "unit_tests": {
            "id": "F4-G00",
            "label": "Phase 4 unit tests",
            **_run_unittest_modules(PHASE4_UNIT_MODULES),
        },
        "phase3_prereq": verify_phase3_prerequisite(),
        "ddl_v5": verify_ddl_v5(),
        "nest_campaign_writes": verify_nest_campaign_writes_api(),
        "clickhouse_export": verify_clickhouse_export(),
        "flask_sunset_docs": verify_flask_readonly_docs(),
        "nest_jest_e2e": verify_nest_jest_e2e(),
    }
    required = [k for k in steps if not steps[k].get("skipped")]
    all_ok = all(bool(steps[k].get("ok")) for k in required)
    report = {
        "phase": "phase4_scale",
        "generated_at": _now_iso(),
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(required),
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
    }
    out = artifacts / "phase4-gate-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main() -> int:
    report = run_phase4_gate_pack()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
