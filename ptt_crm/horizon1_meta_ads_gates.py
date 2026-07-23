"""Horizon 1 — Meta / Facebook Ads migration gates (Flask admin off)."""
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

META_PYTEST: tuple[str, ...] = (
    "tests/test_facebook_ads_hub.py",
    "tests/test_facebook_ingest_pg.py",
    "tests/test_meta_insights_sync.py",
)


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _run_pytest_meta() -> dict[str, Any]:
    python = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [python, "-m", "pytest", *META_PYTEST, "-q", "--tb=no"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return {
        "id": "M1-G01",
        "ok": proc.returncode == 0,
        "label": "Meta regression pytest",
        "returncode": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def _check_ops_web_meta_hub() -> dict[str, Any]:
    page = ROOT / "services" / "ops-web" / "src" / "app" / "meta" / "facebook-ads" / "page.tsx"
    return {
        "id": "M1-G02",
        "ok": page.is_file(),
        "label": "ops-web Meta Facebook Ads hub page",
        "path": str(page.relative_to(ROOT)) if page.is_file() else None,
    }


def _check_nest_facebook_hub_api() -> dict[str, Any]:
    ctrl = ROOT / "services" / "ptt-crm-api" / "src" / "agency" / "agency-ops.controller.ts"
    text = ctrl.read_text(encoding="utf-8") if ctrl.is_file() else ""
    ok = "facebook-ads/hub" in text and "StaffFacebookAdsViewGuard" in text
    return {
        "id": "M1-G03",
        "ok": ok,
        "label": "Nest GET /api/v1/facebook-ads/hub",
        "path": str(ctrl.relative_to(ROOT)) if ctrl.is_file() else None,
    }


def _check_seed_script() -> dict[str, Any]:
    script = ROOT / "scripts" / "seed_staff_meta_permissions.py"
    return {
        "id": "M1-G00",
        "ok": script.is_file(),
        "label": "Meta RBAC seed script",
        "path": str(script.relative_to(ROOT)) if script.is_file() else None,
    }


def _check_webhook_routing() -> dict[str, Any]:
    expect_nest = _truthy("PTT_WEBHOOKS_NEST_META", "1")
    expect_no_fallback = not _truthy("PTT_WEBHOOKS_FLASK_FALLBACK", "1")
    actual_nest = _truthy("PTT_WEBHOOKS_NEST_META", os.environ.get("PTT_WEBHOOKS_NEST_META", "0"))
    actual_fallback = _truthy("PTT_WEBHOOKS_FLASK_FALLBACK", os.environ.get("PTT_WEBHOOKS_FLASK_FALLBACK", "1"))
    ok = actual_nest == expect_nest and (actual_fallback == (not expect_no_fallback) if expect_no_fallback else True)
    if expect_no_fallback:
        ok = ok and not actual_fallback
    return {
        "id": "M1-G04",
        "ok": ok,
        "label": "Webhook routing Nest Meta / no Flask fallback",
        "actual": {"PTT_WEBHOOKS_NEST_META": actual_nest, "PTT_WEBHOOKS_FLASK_FALLBACK": actual_fallback},
        "expected": {"nest_meta": expect_nest, "no_flask_fallback": expect_no_fallback},
    }


def _nest_hub_smoke() -> dict[str, Any]:
    if _truthy("HORIZON1_SKIP_NEST_SMOKE", "1"):
        return {"id": "M1-G05", "ok": True, "label": "Nest facebook hub smoke", "skipped": True}
    base = (os.environ.get("OPS_E2E_API_URL") or "http://127.0.0.1:3000").rstrip("/")
    try:
        health = urllib.request.urlopen(f"{base}/health", timeout=5)
        health_ok = health.status == 200
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"id": "M1-G05", "ok": False, "label": "Nest facebook hub smoke", "error": str(exc)}
    hub_ok = False
    if _truthy("PTT_CRM_API_AUTH_DISABLED", "0"):
        hub_ok = True
    else:
        try:
            login_body = json.dumps({"email": "staff@demo.local", "password": "demo123"}).encode()
            req = urllib.request.Request(
                f"{base}/api/v1/staff/auth/login",
                data=login_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                token = str(data.get("access_token") or "")
            if token:
                hub_req = urllib.request.Request(
                    f"{base}/api/v1/facebook-ads/hub?days=7",
                    headers={"Authorization": f"Bearer {token}"},
                )
                with urllib.request.urlopen(hub_req, timeout=10) as resp:
                    hub = json.loads(resp.read().decode())
                    hub_ok = hub.get("ok") is True or isinstance(hub.get("clients"), list)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            hub_ok = False
    return {
        "id": "M1-G05",
        "ok": health_ok and hub_ok,
        "label": "Nest facebook hub smoke",
        "health_ok": health_ok,
        "hub_ok": hub_ok,
        "base_url": base,
    }


def _check_nginx_meta_redirect() -> dict[str, Any]:
    from ptt_crm.meta_ads_nginx_redirect import verify_nginx_redirect_gate

    return verify_nginx_redirect_gate()


def _check_autosync_standalone() -> dict[str, Any]:
    unit = ROOT / "deploy" / "ptt-fb-autosync.service"
    daemon = ROOT / "scripts" / "run_fb_autosync_daemon.py"
    crm_sqlite = ROOT / "ptt_crm" / "crm_sqlite.py"
    gunicorn_off = not _truthy("CRM_FACEBOOK_BACKGROUND_IN_GUNICORN", "1")
    unit_text = unit.read_text(encoding="utf-8") if unit.is_file() else ""
    no_ptt_service = "Wants=ptt.service" not in unit_text
    ok = unit.is_file() and daemon.is_file() and crm_sqlite.is_file() and gunicorn_off and no_ptt_service
    return {
        "id": "M1-G07",
        "ok": ok,
        "label": "Facebook autosync standalone (not in Gunicorn, no app import)",
        "no_ptt_service_dependency": no_ptt_service,
        "note": "flask retired",
    }


def _check_campaign_write_pilot() -> dict[str, Any]:
    if not _truthy("HORIZON1_EXPECT_CAMPAIGN_WRITE_PILOT", "0"):
        return {"id": "M1-G10", "ok": True, "label": "Meta campaign write pilot", "skipped": True}
    stub_off = not _truthy("PTT_META_CAMPAIGN_WRITE_STUB", "1")
    pilot_on = _truthy("PTT_META_CAMPAIGN_WRITE_PILOT", "0")
    ok = stub_off and pilot_on
    return {
        "id": "M1-G10",
        "ok": ok,
        "label": "Meta campaign write pilot enabled",
        "PTT_META_CAMPAIGN_WRITE_STUB": not stub_off,
        "PTT_META_CAMPAIGN_WRITE_PILOT": pilot_on,
    }


def _check_soak() -> dict[str, Any]:
    if _truthy("HORIZON1_SKIP_SOAK", "1"):
        return {"id": "M1-G08", "ok": True, "label": "Horizon 1 Meta soak", "skipped": True}
    from ptt_crm.horizon1_meta_ads_soak_evidence import evaluate_soak_gate

    result = evaluate_soak_gate(path=_artifacts_dir() / "horizon1-meta-ads-soak-evidence.jsonl")
    result["id"] = "M1-G08"
    return result


def _check_meta_admin_retired_flag() -> dict[str, Any]:
    expect = _truthy("HORIZON1_EXPECT_META_HUB_RETIRED", "1")
    actual = _truthy("PTT_FLASK_META_ADS_ADMIN_RETIRED", "0")
    ok = actual == expect
    return {
        "id": "M1-G09",
        "ok": ok,
        "label": "PTT_FLASK_META_ADS_ADMIN_RETIRED env",
        "actual": actual,
        "expected": expect,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_seed_script(),
        _run_pytest_meta(),
        _check_ops_web_meta_hub(),
        _check_nest_facebook_hub_api(),
        _check_webhook_routing(),
        _nest_hub_smoke(),
        _check_nginx_meta_redirect(),
        _check_autosync_standalone(),
        _check_meta_admin_retired_flag(),
        _check_campaign_write_pilot(),
        _check_soak(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "horizon": 1,
        "component": "meta_ads_migration",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "runbook": "docs/runbooks/horizon1-meta-ads-migration-checklist.md",
    }
    dest = _artifacts_dir() / "horizon1-meta-ads-gate-report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_gates()
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
