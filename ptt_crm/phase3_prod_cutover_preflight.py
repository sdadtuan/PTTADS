"""Phase 3 prod cutover preflight checks (VPS dry-run)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _http_ok(url: str, *, timeout: float = 8.0) -> tuple[bool, int | None, str | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, None
    except urllib.error.HTTPError as exc:
        return exc.code < 500, exc.code, str(exc)
    except Exception as exc:
        return False, None, str(exc)


def verify_phase2_gates() -> dict[str, Any]:
    path = _artifacts_dir() / "phase2-uat-signoff.json"
    if not path.is_file():
        return {"ok": False, "error": "phase2-uat-signoff.json missing", "path": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    signoff = data.get("signoff") or data
    automated = bool(signoff.get("automated_gates_ok") or data.get("ok"))
    return {"ok": automated, "path": str(path), "automated_gates_ok": automated}


def verify_phase3_qa() -> dict[str, Any]:
    path = _artifacts_dir() / "phase3-qa-gate-report.json"
    if not path.is_file():
        return {"ok": False, "error": "phase3-qa-gate-report.json missing — run ./scripts/phase3_qa_gate.sh"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": bool(data.get("ok")), "path": str(path), "summary": data.get("summary")}


def verify_env_vars() -> dict[str, Any]:
    required = ["DATABASE_URL", "PTT_PORTAL_JWT_SECRET"]
    missing = [k for k in required if not (os.environ.get(k) or "").strip()]
    jwt = (os.environ.get("PTT_PORTAL_JWT_SECRET") or "").strip()
    weak_jwt = jwt == "dev-portal-jwt-change-me-min-32-chars" or len(jwt) < 32
    stub_users = (os.environ.get("PTT_PORTAL_STUB_USERS") or "").strip()
    stub_on = os.environ.get("PTT_PORTAL_ALLOW_STUB", "").strip().lower() in {"1", "true", "yes"}
    issues: list[str] = []
    if missing:
        issues.extend([f"missing:{k}" for k in missing])
    if weak_jwt and os.environ.get("PTT_CUTOVER_ENV", "prod") == "prod":
        issues.append("weak_portal_jwt_secret")
    if stub_on or stub_users:
        issues.append("portal_stub_must_be_off_in_prod")
    return {
        "ok": not issues,
        "missing": missing,
        "issues": issues,
        "portal_jwt_len": len(jwt),
    }


def verify_pg_ddl() -> dict[str, Any]:
    from ptt_crm.pg_schema import pg_hub_sop_ready, pg_v3_ready

    v3 = pg_v3_ready()
    v4 = pg_hub_sop_ready()
    ok = v3 and v4
    return {"ok": ok, "pg_v3_ready": v3, "pg_hub_sop_ready": v4}


def verify_prod_urls() -> dict[str, Any]:
    api = (os.environ.get("PTT_PROD_API_URL") or "https://api.pttads.vn").rstrip("/")
    portal = (os.environ.get("PTT_PROD_PORTAL_URL") or "https://portal.pttads.vn").rstrip("/")
    api_ok, api_status, api_err = _http_ok(f"{api}/health")
    portal_ok, portal_status, portal_err = _http_ok(f"{portal}/login")
    skip = os.environ.get("PTT_CUTOVER_SKIP_URL_CHECK", "").strip().lower() in {"1", "true", "yes"}
    if skip:
        return {
            "ok": True,
            "skipped": True,
            "api_url": api,
            "portal_url": portal,
        }
    ok = api_ok and portal_ok
    return {
        "ok": ok,
        "api": {"url": api, "ok": api_ok, "status": api_status, "error": api_err},
        "portal": {"url": portal, "ok": portal_ok, "status": portal_status, "error": portal_err},
    }


def verify_systemd_units() -> dict[str, Any]:
    units = [
        "ptt-portal-web.service",
        "ptt-temporal-worker.service",
        "ptt-crm-api.service",
        "ptt-google-insights.timer",
    ]
    if os.environ.get("PTT_CUTOVER_SKIP_SYSTEMD", "").strip().lower() in {"1", "true", "yes"}:
        return {"ok": True, "skipped": True, "units": units}
    missing: list[str] = []
    inactive: list[str] = []
    for unit in units:
        unit_path = Path("/etc/systemd/system") / unit
        if not unit_path.is_file():
            missing.append(unit)
            continue
        try:
            proc = subprocess.run(
                ["systemctl", "is-active", unit.replace(".service", "").replace(".timer", "")],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # is-active for timer checks timer unit name
            proc2 = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=5,
            )
            state = (proc2.stdout or proc.stdout or "").strip()
            if state not in {"active", "activating"}:
                inactive.append(f"{unit}:{state}")
        except Exception as exc:
            inactive.append(f"{unit}:check_failed:{exc}")
    ok = not missing and not inactive
    return {"ok": ok, "missing_unit_files": missing, "inactive": inactive}


def run_preflight() -> dict[str, Any]:
    steps = {
        "phase2_gates": verify_phase2_gates(),
        "phase3_qa": verify_phase3_qa(),
        "env_vars": verify_env_vars(),
        "pg_ddl": verify_pg_ddl(),
        "prod_urls": verify_prod_urls(),
        "systemd": verify_systemd_units(),
    }
    skip_optional = {"prod_urls", "systemd"}
    required = [k for k in steps if k not in skip_optional or not steps[k].get("skipped")]
    all_ok = all(bool(steps[k].get("ok")) for k in required)
    report = {
        "phase": "phase3_prod_cutover_preflight",
        "generated_at": _now_iso(),
        "host": socket.gethostname(),
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "total": len(required),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
    }
    out = _artifacts_dir() / "phase3-prod-cutover-preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main() -> int:
    report = run_preflight()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
