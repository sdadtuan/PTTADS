"""Meta Ads Flask admin retirement — production APPLY verify (Horizon 1 B3.6)."""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ptt_crm.meta_ads_retirement_preflight import (
    PLANNED_ENV,
    check_systemd_units,
    read_env_file,
    verify_dry_run_artifact,
)

ROOT = Path(__file__).resolve().parents[1]

APPLIED_ENV: dict[str, str] = {
    **PLANNED_ENV,
    "HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED": "1",
    "HORIZON1_META_RETIREMENT_APPLIED": "1",
}


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def apply_artifact_path() -> Path:
    return _artifacts_dir() / "horizon1-meta-ads-retirement-applied.json"


def check_apply_prerequisite() -> dict[str, Any]:
    dry = verify_dry_run_artifact()
    env_verified = _truthy("HORIZON1_META_RETIREMENT_DRY_RUN_VERIFIED", "0")
    ok = bool(dry.get("ok")) or env_verified
    return {
        "ok": ok,
        "dry_run_artifact_ok": dry.get("ok"),
        "dry_run_artifact_path": dry.get("path"),
        "env_dry_run_verified": env_verified,
        "error": None if ok else "run_wave_b3_5_deploy_first",
    }


def verify_env_applied() -> dict[str, Any]:
    current = read_env_file()
    rows: list[dict[str, Any]] = []
    for key, expected in APPLIED_ENV.items():
        actual = current.get(key)
        match = actual is not None and actual.strip() == expected
        rows.append({"key": key, "expected": expected, "actual": actual, "ok": match})
    missing = [r for r in rows if not r["ok"]]
    return {
        "ok": not missing,
        "rows": rows,
        "missing_keys": [r["key"] for r in missing],
    }


def verify_nginx_redirect_live() -> dict[str, Any]:
    skip = _truthy("HORIZON1_SKIP_NGINX_REDIRECT_VERIFY", "1")
    if skip:
        return {"ok": True, "skipped": True}
    from ptt_crm.meta_ads_nginx_redirect import verify_live_redirect

    live = verify_live_redirect()
    return {"ok": bool(live.get("ok")), "skipped": False, "live_redirect": live}


def run_post_apply_verification() -> dict[str, Any]:
    steps = {
        "prerequisite": check_apply_prerequisite(),
        "env_applied": verify_env_applied(),
        "nginx_live": verify_nginx_redirect_live(),
        "systemd": check_systemd_units(),
    }
    optional = {"nginx_live", "systemd"}
    required = [k for k in steps if k not in optional or not steps[k].get("skipped")]
    ok = all(bool(steps[k].get("ok")) for k in required)
    return {
        "wave": "B3.6",
        "component": "meta_ads_retirement_applied",
        "ok": ok,
        "generated_at": _now_iso(),
        "host": socket.gethostname(),
        "partial_retire": True,
        "ptt_service_stopped": False,
        "steps": steps,
        "summary": {
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "total": len(required),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
        "rollback": [
            "PTT_FLASK_META_ADS_ADMIN_RETIRED=0 in .env",
            "Remove nginx /crm/facebook-ads redirect",
            "systemctl restart ptt-crm-api ptt-ops-web ptt",
        ],
        "runbook": "docs/runbooks/wave-b3.6-meta-retirement-apply-prod.md",
    }


def record_apply_artifact(*, applied: bool = True) -> dict[str, Any]:
    report = run_post_apply_verification()
    report["applied"] = applied
    report["apply_command"] = "sudo -E APPLY=1 ./scripts/close_flask_retirement_meta_ads.sh"
    dest = apply_artifact_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    try:
        report["artifact_path"] = str(dest.relative_to(ROOT))
    except ValueError:
        report["artifact_path"] = str(dest)
    return report


def verify_apply_artifact(path: Path | None = None) -> dict[str, Any]:
    dest = path or apply_artifact_path()
    if not dest.is_file():
        applied_env = _truthy("HORIZON1_META_RETIREMENT_APPLIED", "0")
        if applied_env and verify_env_applied().get("ok"):
            return {
                "ok": True,
                "path": str(dest),
                "source": "env_fallback",
                "generated_at": None,
            }
        return {"ok": False, "error": "artifact_missing", "path": str(dest)}
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": "invalid_json", "path": str(dest), "detail": str(exc)}
    ok = bool(data.get("ok")) and bool(data.get("applied", True))
    return {
        "ok": ok,
        "path": str(dest),
        "generated_at": data.get("generated_at"),
        "summary": data.get("summary"),
        "source": "artifact",
    }


def retirement_apply_status() -> dict[str, Any]:
    artifact = verify_apply_artifact()
    env = verify_env_applied()
    prereq = check_apply_prerequisite()
    gate_ok = bool(artifact.get("ok")) and bool(env.get("ok"))
    return {
        "gate_m1_g12": gate_ok,
        "retirement_applied_ok": artifact.get("ok"),
        "retirement_apply_artifact_path": artifact.get("path"),
        "retirement_apply_artifact_present": artifact.get("source") == "artifact",
        "retirement_env_applied_ok": env.get("ok"),
        "retirement_env_missing_keys": env.get("missing_keys") or [],
        "retirement_dry_run_prerequisite_ok": prereq.get("ok"),
        "retirement_apply_generated_at": artifact.get("generated_at"),
    }


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "verify").strip().lower()
    if mode == "prerequisite":
        out = check_apply_prerequisite()
    elif mode == "record":
        out = record_apply_artifact()
    elif mode == "verify":
        out = verify_apply_artifact()
    elif mode == "post":
        out = run_post_apply_verification()
    else:
        print("Usage: meta_ads_retirement_apply.py [prerequisite|record|verify|post]", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
