"""Phase 3 Google Ads adapter gate pack (G1–G4)."""
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


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_unittest(module: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def verify_g1_channel_account(client_id: str) -> dict[str, Any]:
    from ptt_agency.clients import load_channel_account_for_sync
    from ptt_google.oauth import _client_config
    from ptt_google.token_vault import resolve_google_refresh_token

    accounts = load_channel_account_for_sync(client_id, channel="google")
    if not accounts:
        return {"id": "G3-G01", "ok": False, "label": "Google channel account", "error": "no_accounts"}

    acct = accounts[0]
    token = resolve_google_refresh_token(
        {
            "access_token_encrypted": acct.get("access_token_encrypted"),
            "credential_ref": acct.get("credential_ref"),
            "meta": acct.get("meta") or {},
        }
    )
    oauth_ready = True
    oauth_note = None
    try:
        _client_config()
    except ValueError as exc:
        oauth_ready = False
        oauth_note = str(exc)

    ok = bool(acct.get("external_account_id")) and bool(token or os.environ.get("PTT_GOOGLE_INSIGHTS_STUB") == "1")
    return {
        "id": "G3-G01",
        "ok": ok,
        "label": "Google channel account + token resolution",
        "account_id": str(acct.get("external_account_id")),
        "has_refresh_token": bool(token),
        "oauth_env_configured": oauth_ready,
        "oauth_note": oauth_note,
    }


def verify_g2_insights_sync(client_id: str) -> dict[str, Any]:
    os.environ.setdefault("PTT_GOOGLE_INSIGHTS_SYNC", "1")
    os.environ.setdefault("PTT_GOOGLE_INSIGHTS_STUB", "1")
    from ptt_google.insights_sync import pg_google_insights_ready, sync_google_insights

    if not pg_google_insights_ready():
        return {"id": "G3-G02", "ok": False, "label": "Google insights sync", "error": "ddl_not_ready"}
    out = sync_google_insights(client_id=client_id, compute_metrics=False)
    ok = bool(out.get("ok")) and int(out.get("rows_upserted") or 0) >= 1
    return {
        "id": "G3-G02",
        "ok": ok,
        "label": "Google insights sync → daily_performance",
        "rows_upserted": out.get("rows_upserted"),
        "performance_date": out.get("performance_date"),
        "sync": {k: out[k] for k in out if k not in {"metrics"}},
    }


def verify_g3_hub_map(client_id: str) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT external_campaign_id, external_campaign_name, target_cpl_vnd
                FROM hub_campaign_map
                WHERE client_id = %s::uuid AND channel = 'google' AND active IS TRUE
                LIMIT 1
                """,
                (client_id,),
            )
            row = cur.fetchone()
    ok = bool(row is not None and row[0])
    return {
        "id": "G3-G03",
        "ok": ok,
        "label": "Hub map channel=google",
        "external_campaign_id": row[0] if row else None,
        "target_cpl_vnd": float(row[2]) if row and row[2] is not None else None,
    }


def verify_g4_agency_performance(client_id: str) -> dict[str, Any]:
    from ptt_agency.performance import list_campaign_performance

    out = list_campaign_performance(client_id=client_id, group_by="day")
    rows = out.get("rows") or []
    google_rows = [r for r in rows if str(r.get("channel") or "").lower() == "google"]
    ok = bool(out.get("ok")) and len(google_rows) >= 1
    return {
        "id": "G3-G04",
        "ok": ok,
        "label": "Agency CPL tab includes Google rows",
        "total_rows": len(rows),
        "google_rows": len(google_rows),
        "sample_channel": google_rows[0].get("channel") if google_rows else None,
    }


def verify_g4_portal_performance(client_id: str) -> dict[str, Any]:
    api = (os.environ.get("PTT_API_URL") or "http://127.0.0.1:3000").rstrip("/")
    email = os.environ.get("PORTAL_E2E_APPROVER_EMAIL", "approver@demo.local")
    password = os.environ.get("PORTAL_E2E_APPROVER_PASSWORD", "demo123")

    def http_json(method: str, url: str, *, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                return exc.code, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return exc.code, {"error": raw}

    status, login = http_json(
        "POST",
        f"{api}/api/v1/portal/auth/login",
        body={"email": email, "password": password},
    )
    token = login.get("access_token")
    if not token:
        return {"id": "G3-G05", "ok": False, "label": "Portal performance Google rows", "error": "login_failed", "status": status}

    perf_status, perf = http_json("GET", f"{api}/api/v1/performance?group_by=day", token=token)
    rows = perf.get("rows") or []
    google_rows = [r for r in rows if str(r.get("channel") or "").lower() == "google"]
    ok = perf_status == 200 and len(google_rows) >= 1
    return {
        "id": "G3-G05",
        "ok": ok,
        "label": "Portal dashboard Google rows",
        "http_status": perf_status,
        "google_rows": len(google_rows),
        "total_rows": len(rows),
    }


def run_google_gate_pack(*, client_id: str | None = None) -> dict[str, Any]:
    cid = client_id or os.environ.get("GOOGLE_PILOT_CLIENT_ID", DEFAULT_CLIENT)
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)

    steps: dict[str, Any] = {
        "unit_tests": {
            "id": "G3-G00",
            "label": "Google insights unit tests",
            **_run_unittest("tests.test_google_insights_sync"),
        },
        "channel_account": verify_g1_channel_account(cid),
        "insights_sync": verify_g2_insights_sync(cid),
        "hub_map": verify_g3_hub_map(cid),
        "agency_performance": verify_g4_agency_performance(cid),
        "portal_performance": verify_g4_portal_performance(cid),
    }
    all_ok = all(bool(s.get("ok")) for s in steps.values())
    report = {
        "phase": "phase3_google_adapter",
        "generated_at": _now_iso(),
        "client_id": cid,
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": sum(1 for s in steps.values() if s.get("ok")),
            "failed": [k for k, s in steps.items() if not s.get("ok")],
        },
    }
    out = artifacts / "phase3-google-gate-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main() -> int:
    report = run_google_gate_pack()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
