"""Phase 3 Client Portal MVP gate pack — auth, performance, approvals."""
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


def _api_base() -> str:
    return (os.environ.get("PTT_API_URL") or "http://127.0.0.1:3000").rstrip("/")


def _http_json(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {"error": str(exc)}
        except Exception:
            return exc.code, {"error": raw or str(exc)}


def verify_nest_health() -> dict[str, Any]:
    status, body = _http_json("GET", f"{_api_base()}/health")
    ok = status == 200 and body.get("status") in ("ok", "healthy", None)
    return {
        "id": "P3-G01",
        "ok": ok,
        "label": "Nest health",
        "status": status,
        "body": body,
    }


def verify_portal_login() -> dict[str, Any]:
    email = os.environ.get("PORTAL_E2E_APPROVER_EMAIL", "approver@demo.local")
    password = os.environ.get("PORTAL_E2E_APPROVER_PASSWORD", "demo123")
    status, body = _http_json(
        "POST",
        f"{_api_base()}/api/v1/portal/auth/login",
        body={"email": email, "password": password},
    )
    token = body.get("access_token")
    ok = status == 200 and bool(token) and bool(body.get("user", {}).get("client_id"))
    return {
        "id": "P3-G02",
        "ok": ok,
        "label": "Portal login JWT",
        "status": status,
        "user": body.get("user"),
        "access_token_prefix": (token or "")[:12] + "..." if token else None,
    }


def verify_performance_api(login_step: dict[str, Any]) -> dict[str, Any]:
    email = os.environ.get("PORTAL_E2E_APPROVER_EMAIL", "approver@demo.local")
    password = os.environ.get("PORTAL_E2E_APPROVER_PASSWORD", "demo123")
    if not login_step.get("ok"):
        status, body = _http_json(
            "POST",
            f"{_api_base()}/api/v1/portal/auth/login",
            body={"email": email, "password": password},
        )
        token = body.get("access_token")
    else:
        status, body = _http_json(
            "POST",
            f"{_api_base()}/api/v1/portal/auth/login",
            body={"email": email, "password": password},
        )
        token = body.get("access_token")
    if not token:
        return {"id": "P3-G03", "ok": False, "label": "Performance API", "error": "no token"}
    perf_status, perf = _http_json(
        "GET",
        f"{_api_base()}/api/v1/performance?group_by=day",
        headers={"Authorization": f"Bearer {token}"},
    )
    rows = perf.get("rows") or []
    ok = perf_status == 200 and perf.get("ok") is True and len(rows) >= 1
    return {
        "id": "P3-G03",
        "ok": ok,
        "label": "Performance dashboard API",
        "status": perf_status,
        "row_count": len(rows),
        "summary": perf.get("summary"),
        "date_from": perf.get("date_from"),
        "date_to": perf.get("date_to"),
    }


def verify_meta_performance_api(login_step: dict[str, Any]) -> dict[str, Any]:
    email = os.environ.get("PORTAL_E2E_APPROVER_EMAIL", "approver@demo.local")
    password = os.environ.get("PORTAL_E2E_APPROVER_PASSWORD", "demo123")
    status, body = _http_json(
        "POST",
        f"{_api_base()}/api/v1/portal/auth/login",
        body={"email": email, "password": password},
    )
    token = body.get("access_token")
    if not token:
        return {"id": "P3-G06", "ok": False, "label": "Meta performance API", "error": "no token"}
    perf_status, perf = _http_json(
        "GET",
        f"{_api_base()}/api/v1/performance?group_by=day&channel=meta",
        headers={"Authorization": f"Bearer {token}"},
    )
    rows = perf.get("rows") or []
    ok = (
        perf_status == 200
        and perf.get("ok") is True
        and perf.get("channel") == "meta"
        and all(str(r.get("channel") or "meta") == "meta" for r in rows)
    )
    return {
        "id": "P3-G06",
        "ok": ok,
        "label": "Meta performance API (channel=meta)",
        "status": perf_status,
        "row_count": len(rows),
        "channel": perf.get("channel"),
        "summary": perf.get("summary"),
    }


def verify_creative_approve_flow() -> dict[str, Any]:
    email = os.environ.get("PORTAL_E2E_APPROVER_EMAIL", "approver@demo.local")
    password = os.environ.get("PORTAL_E2E_APPROVER_PASSWORD", "demo123")
    client_id = os.environ.get("PORTAL_E2E_CLIENT_ID", DEFAULT_CLIENT)
    internal_key = os.environ.get("PTT_CRM_INTERNAL_KEY") or os.environ.get("PORTAL_E2E_INTERNAL_KEY", "")

    _, login = _http_json(
        "POST",
        f"{_api_base()}/api/v1/portal/auth/login",
        body={"email": email, "password": password},
    )
    token = login.get("access_token")
    if not token:
        return {"id": "P3-G04", "ok": False, "label": "Creative approval", "error": "login failed"}

    title = f"Gate Creative {int(datetime.now().timestamp())}"
    headers: dict[str, str] = {}
    if internal_key:
        headers["X-PTT-Internal-Key"] = internal_key
    submit_status, submit = _http_json(
        "POST",
        f"{_api_base()}/api/v1/creatives",
        headers=headers,
        body={
            "client_id": client_id,
            "title": title,
            "description": "Phase 3 gate pack approve smoke",
            "external_campaign_id": "camp_demo_meta_summer",
            "version": 1,
            "submitted_by": "gate@pttads.vn",
        },
    )
    creative_id = (submit.get("creative") or {}).get("id")
    if submit_status not in (200, 201) or not creative_id:
        return {
            "id": "P3-G04",
            "ok": False,
            "label": "Creative approval",
            "submit_status": submit_status,
            "submit": submit,
            "note": "Set PTT_CRM_INTERNAL_KEY or PTT_CRM_API_AUTH_DISABLED=1 for internal submit",
        }

    pending_status, pending = _http_json(
        "GET",
        f"{_api_base()}/api/v1/creatives/pending",
        headers={"Authorization": f"Bearer {token}"},
    )
    ids = [r.get("id") for r in (pending.get("rows") or [])]
    if creative_id not in ids:
        return {
            "id": "P3-G04",
            "ok": False,
            "label": "Creative approval",
            "error": "creative not in pending inbox",
            "pending_status": pending_status,
        }

    approve_status, approve = _http_json(
        "POST",
        f"{_api_base()}/api/v1/creatives/{creative_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )
    ok = approve_status in (200, 201) and approve.get("ok") is True
    return {
        "id": "P3-G04",
        "ok": ok,
        "label": "Creative approval flow",
        "creative_id": creative_id,
        "approve_status": approve_status,
        "temporal_signal": approve.get("temporal_signal"),
    }


def verify_portal_build() -> dict[str, Any]:
    portal_dir = ROOT / "services" / "portal-web"
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(portal_dir),
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "id": "P3-G05",
        "ok": proc.returncode == 0,
        "label": "Portal Next.js build",
        "exit_code": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def run_portal_mvp_gate(*, skip_build: bool = False) -> dict[str, Any]:
    artifacts = _artifacts_dir()
    artifacts.mkdir(parents=True, exist_ok=True)
    steps: dict[str, Any] = {
        "nest_health": verify_nest_health(),
        "portal_login": verify_portal_login(),
    }
    steps["performance"] = verify_performance_api(steps["portal_login"])
    steps["meta_performance"] = verify_meta_performance_api(steps["portal_login"])
    steps["creative_approve"] = verify_creative_approve_flow()
    if not skip_build:
        steps["portal_build"] = verify_portal_build()
    all_ok = all(bool(s.get("ok")) for s in steps.values())
    report = {
        "phase": "phase3_portal_mvp",
        "generated_at": _now_iso(),
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "total": len(steps),
            "passed": sum(1 for s in steps.values() if s.get("ok")),
            "failed": [k for k, s in steps.items() if not s.get("ok")],
        },
    }
    out = artifacts / "phase3-portal-mvp-gate-report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    skip_build = "--skip-build" in (argv or sys.argv[1:])
    report = run_portal_mvp_gate(skip_build=skip_build)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
