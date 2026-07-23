"""Meta Ads Flask admin retirement — dry-run preflight (Horizon 1 B3.5)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PLANNED_ENV: dict[str, str] = {
    "PTT_FLASK_META_ADS_ADMIN_RETIRED": "1",
    "HORIZON1_EXPECT_META_HUB_RETIRED": "1",
    "PTT_WEBHOOKS_NEST_ENABLED": "1",
    "PTT_WEBHOOKS_NEST_META": "1",
    "PTT_WEBHOOKS_FLASK_FALLBACK": "0",
    "CRM_FACEBOOK_BACKGROUND": "1",
    "CRM_FACEBOOK_BACKGROUND_IN_GUNICORN": "0",
    "HORIZON1_SKIP_NGINX_REDIRECT_VERIFY": "0",
    "HORIZON1_META_NGINX_REDIRECT_VERIFIED": "1",
}

SYSTEMD_UNITS: tuple[str, ...] = (
    "ptt-crm-api.service",
    "ptt-ops-web.service",
    "ptt.service",
    "ptt-fb-autosync.service",
)

RESTART_UNITS: tuple[str, ...] = (
    "ptt-crm-api",
    "ptt-ops-web",
    "ptt",
    "ptt.service",
    "ptt-fb-autosync.service",
)

ROLLBACK_STEPS: tuple[str, ...] = (
    "Set PTT_FLASK_META_ADS_ADMIN_RETIRED=0 and HORIZON1_EXPECT_META_HUB_RETIRED=0 in .env",
    "Comment nginx location ^~ /crm/facebook-ads; nginx -t && systemctl reload nginx",
    "systemctl restart ptt-crm-api ptt-ops-web ptt",
    "Staff use ops-web /meta/facebook-ads until Flask bookmark restored",
)


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_file_path() -> Path:
    raw = os.environ.get("PTT_ENV_FILE", "/var/www/ptt/.env")
    return Path(raw)


def read_env_file(path: Path | None = None) -> dict[str, str]:
    target = path or env_file_path()
    out: dict[str, str] = {}
    if not target.is_file():
        return out
    for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def planned_env_diff(*, env_path: Path | None = None) -> dict[str, Any]:
    current = read_env_file(env_path)
    rows: list[dict[str, Any]] = []
    for key, planned in PLANNED_ENV.items():
        cur = current.get(key)
        if cur is None:
            action = "add"
        elif cur.strip() == planned:
            action = "ok"
        else:
            action = "update"
        rows.append(
            {
                "key": key,
                "current": cur,
                "planned": planned,
                "action": action,
            }
        )
    pending = [r for r in rows if r["action"] != "ok"]
    return {
        "ok": True,
        "env_file": str(env_path or env_file_path()),
        "env_file_exists": (env_path or env_file_path()).is_file(),
        "rows": rows,
        "pending_changes": len(pending),
        "already_applied": len(pending) == 0,
    }


def check_required_scripts() -> dict[str, Any]:
    scripts = {
        "close_flask_retirement_meta_ads.sh": ROOT / "scripts" / "close_flask_retirement_meta_ads.sh",
        "apply_nginx_meta_ads_retired.sh": ROOT / "scripts" / "apply_nginx_meta_ads_retired.sh",
        "verify_meta_ads_nginx_redirect.sh": ROOT / "scripts" / "verify_meta_ads_nginx_redirect.sh",
        "wave_b3_4_smoke.sh": ROOT / "scripts" / "wave_b3_4_smoke.sh",
    }
    missing = [name for name, path in scripts.items() if not path.is_file()]
    return {
        "ok": not missing,
        "scripts": {name: str(path.relative_to(ROOT)) for name, path in scripts.items()},
        "missing": missing,
    }


def check_systemd_units() -> dict[str, Any]:
    if _truthy("HORIZON1_SKIP_SYSTEMD", "1"):
        return {"ok": True, "skipped": True, "units": list(SYSTEMD_UNITS)}
    if not Path("/run/systemd/system").exists():
        return {"ok": True, "skipped": True, "reason": "no_systemd", "units": list(SYSTEMD_UNITS)}
    missing: list[str] = []
    inactive: list[str] = []
    for unit in SYSTEMD_UNITS:
        unit_path = Path("/etc/systemd/system") / unit
        if not unit_path.is_file():
            missing.append(unit)
            continue
        try:
            proc = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=5,
            )
            state = (proc.stdout or "").strip()
            if state not in {"active", "activating"}:
                inactive.append(f"{unit}:{state}")
        except Exception as exc:
            inactive.append(f"{unit}:check_failed:{exc}")
    ok = not missing and not inactive
    return {
        "ok": ok,
        "skipped": False,
        "missing_unit_files": missing,
        "inactive": inactive,
        "restart_on_apply": list(RESTART_UNITS),
    }


def check_nginx_plan() -> dict[str, Any]:
    from ptt_crm.meta_ads_nginx_redirect import check_deploy_nginx_config, check_live_nginx_site

    deploy = check_deploy_nginx_config()
    site = check_live_nginx_site()
    apply_script = ROOT / "scripts" / "apply_nginx_meta_ads_retired.sh"
    return {
        "ok": deploy["ok"],
        "deploy_config_ok": deploy["ok"],
        "live_site_configured": site.get("configured"),
        "live_site_ok": site.get("ok"),
        "apply_script": str(apply_script.relative_to(ROOT)) if apply_script.is_file() else None,
        "redirect": "/crm/facebook-ads → ops-web /meta/facebook-ads",
        "will_apply_via": "apply_nginx_meta_ads_retired.sh",
    }


def run_horizon1_gates() -> dict[str, Any]:
    """Retirement preflight — skip optional prod soak/nest smoke by default."""
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "HORIZON1_SKIP_SOAK": "1",
        "HORIZON1_SKIP_NEST_SMOKE": "1",
        "HORIZON1_SKIP_NGINX_REDIRECT_VERIFY": os.environ.get("HORIZON1_SKIP_NGINX_REDIRECT_VERIFY", "1"),
        "HORIZON1_EXPECT_META_HUB_RETIRED": os.environ.get("HORIZON1_EXPECT_META_HUB_RETIRED", "1"),
        "PTT_FLASK_META_ADS_ADMIN_RETIRED": os.environ.get("PTT_FLASK_META_ADS_ADMIN_RETIRED", "1"),
        "PTT_WEBHOOKS_NEST_META": os.environ.get("PTT_WEBHOOKS_NEST_META", "1"),
        "PTT_WEBHOOKS_FLASK_FALLBACK": os.environ.get("PTT_WEBHOOKS_FLASK_FALLBACK", "0"),
        "CRM_FACEBOOK_BACKGROUND": "1",
        "CRM_FACEBOOK_BACKGROUND_IN_GUNICORN": "0",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.horizon1_meta_ads_gates"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    report: dict[str, Any] | None = None
    art = _artifacts_dir() / "horizon1-meta-ads-gate-report.json"
    if art.is_file():
        try:
            report = json.loads(art.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = None
    return {
        "ok": proc.returncode == 0 and bool(report and report.get("ok")),
        "returncode": proc.returncode,
        "gate_report_path": str(art.relative_to(ROOT)) if art.is_file() else None,
        "failed_ids": (report or {}).get("failed_ids") or [],
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def retirement_apply_plan() -> dict[str, Any]:
    return {
        "partial_retire": True,
        "stop_ptt_service": False,
        "env_updates": PLANNED_ENV,
        "nginx_action": "apply_nginx_meta_ads_retired.sh",
        "service_restarts": list(RESTART_UNITS),
        "post_apply_smoke": "./scripts/wave_b3_4_smoke.sh",
        "rollback": list(ROLLBACK_STEPS),
    }


def run_dry_run_preflight(*, write_artifact: bool = True) -> dict[str, Any]:
    steps = {
        "scripts": check_required_scripts(),
        "env_diff": planned_env_diff(),
        "nginx_plan": check_nginx_plan(),
        "systemd": check_systemd_units(),
        "horizon1_gates": run_horizon1_gates(),
    }
    optional = {"systemd"}
    required = [k for k in steps if k not in optional or not steps[k].get("skipped")]
    ok = all(bool(steps[k].get("ok")) for k in required)
    report = {
        "wave": "B3.5",
        "component": "meta_ads_retirement_dry_run",
        "dry_run": True,
        "ok": ok,
        "generated_at": _now_iso(),
        "apply_plan": retirement_apply_plan(),
        "steps": steps,
        "summary": {
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "total": len(required),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
        "next_command": "sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh",
        "runbook": "docs/runbooks/wave-b3.5-meta-retirement-dry-run.md",
    }
    if write_artifact:
        dest = _artifacts_dir() / "horizon1-meta-ads-retirement-dry-run.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        try:
            report["artifact_path"] = str(dest.relative_to(ROOT))
        except ValueError:
            report["artifact_path"] = str(dest)
    return report


def retirement_dry_run_status() -> dict[str, Any]:
    """Summary for migration-status API / ops-web (B3.5)."""
    artifact = verify_dry_run_artifact()
    env_diff = planned_env_diff()
    return {
        "gate_m1_g11": bool(artifact.get("ok")),
        "dry_run_artifact_ok": artifact.get("ok"),
        "dry_run_artifact_path": artifact.get("path"),
        "dry_run_artifact_error": artifact.get("error"),
        "dry_run_generated_at": artifact.get("generated_at"),
        "env_pending_changes": env_diff.get("pending_changes"),
        "env_already_applied": env_diff.get("already_applied"),
        "env_file": env_diff.get("env_file"),
        "next_apply_command": "sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh",
    }


def verify_dry_run_artifact(path: Path | None = None) -> dict[str, Any]:
    dest = path or (_artifacts_dir() / "horizon1-meta-ads-retirement-dry-run.json")
    if not dest.is_file():
        return {"ok": False, "error": "artifact_missing", "path": str(dest)}
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid_json", "path": str(dest), "detail": str(exc)}
    ok = bool(data.get("ok")) and bool(data.get("dry_run"))
    return {
        "ok": ok,
        "path": str(dest),
        "generated_at": data.get("generated_at"),
        "summary": data.get("summary"),
    }


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "run").strip().lower()
    if mode == "verify":
        out = verify_dry_run_artifact()
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    report = run_dry_run_preflight()
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
