"""Phase 5 — Flask monolith retirement gates (stop ptt.service)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _check_env_prerequisites() -> dict[str, Any]:
    required = {
        "PTT_LEADS_WRITE_SOURCE": os.environ.get("PTT_LEADS_WRITE_SOURCE", ""),
        "PTT_LEAD_INGEST_RULES_SOURCE": os.environ.get("PTT_LEAD_INGEST_RULES_SOURCE", ""),
        "PTT_WEBHOOKS_FLASK_FALLBACK": os.environ.get("PTT_WEBHOOKS_FLASK_FALLBACK", "1"),
        "PTT_WEBHOOKS_NEST_META": os.environ.get("PTT_WEBHOOKS_NEST_META", "0"),
        "PTT_PORTAL_SEO_ENABLED": os.environ.get("PTT_PORTAL_SEO_ENABLED", "0"),
    }
    ok = (
        required["PTT_LEADS_WRITE_SOURCE"] == "pg"
        and required["PTT_LEAD_INGEST_RULES_SOURCE"] == "pg"
        and required["PTT_WEBHOOKS_FLASK_FALLBACK"] in {"0", "false", "no", "off", ""}
        and _truthy("PTT_WEBHOOKS_NEST_META", "1")
        and _truthy("PTT_PORTAL_SEO_ENABLED", "1")
    )
    return {
        "id": "P5R-G01",
        "ok": ok,
        "label": "PG-primary + Nest webhooks + portal SEO native",
        "env": required,
    }


def _check_flask_mode_retired() -> dict[str, Any]:
    mode = (os.environ.get("PTT_FLASK_MONOLITH_MODE") or "active").strip().lower()
    expect = (os.environ.get("PHASE5_EXPECT_FLASK_MODE") or "retired").strip().lower()
    ok = mode == expect
    return {
        "id": "P5R-G02",
        "ok": ok,
        "label": "Flask monolith mode",
        "actual": mode,
        "expected": expect,
    }


def _check_prior_gate_artifacts() -> dict[str, Any]:
    if _truthy("PHASE5_SKIP_PRIOR_GATES"):
        return {"id": "P5R-G03", "ok": True, "label": "Prior phase gate artifacts", "skipped": True}
    art = _artifacts_dir()
    checks: dict[str, Any] = {}
    for name in ("phase2-ops-gate-report.json", "phase3-qa-gate-report.json", "staging-phase4-gate-report.json"):
        path = art / name
        if not path.is_file():
            checks[name] = {"ok": False, "error": "missing"}
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        checks[name] = {"ok": bool(data.get("ok")), "path": str(path)}
    ok = all(v.get("ok") for v in checks.values())
    return {"id": "P5R-G03", "ok": ok, "label": "Prior phase gate artifacts", "artifacts": checks}


def _check_nest_no_flask_portal_proxy() -> dict[str, Any]:
    svc = ROOT / "services" / "ptt-crm-api" / "src" / "portal-seo" / "portal-seo.service.ts"
    text = svc.read_text(encoding="utf-8") if svc.is_file() else ""
    has_flask = "flaskGet" in text or "flaskPost" in text or "PTT_FLASK_MONOLITH_URL" in text
    return {
        "id": "P5R-G04",
        "ok": not has_flask,
        "label": "Portal SEO Nest native (no Flask proxy)",
        "path": str(svc.relative_to(ROOT)),
    }


def _check_ops_web_seo_hub() -> dict[str, Any]:
    hub = ROOT / "services" / "ops-web" / "src" / "app" / "seo" / "hub" / "page.tsx"
    nest = ROOT / "services" / "ptt-crm-api" / "src" / "seo-admin" / "seo-admin.controller.ts"
    ok = hub.is_file() and nest.is_file()
    return {
        "id": "P5R-G05",
        "ok": ok,
        "label": "ops-web SEO hub + Nest seo-admin API",
        "ops_hub": str(hub.relative_to(ROOT)) if hub.is_file() else None,
        "nest_api": str(nest.relative_to(ROOT)) if nest.is_file() else None,
    }


def _run_flask_guard_tests() -> dict[str, Any]:
    python = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [python, "-m", "unittest", "tests.test_flask_guard", "-q"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "id": "P5R-G06",
        "ok": proc.returncode == 0,
        "label": "Flask guard unit tests",
        "returncode": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
    }


def _check_worker_units_documented() -> dict[str, Any]:
    units = [
        ROOT / "deploy" / "ptt-fb-autosync.service",
        ROOT / "deploy" / "ptt-worker.service",
    ]
    missing = [str(u.relative_to(ROOT)) for u in units if not u.is_file()]
    return {
        "id": "P5R-G07",
        "ok": not missing,
        "label": "Python workers survive Flask HTTP retirement",
        "missing": missing,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_env_prerequisites(),
        _check_flask_mode_retired(),
        _check_prior_gate_artifacts(),
        _check_nest_no_flask_portal_proxy(),
        _check_ops_web_seo_hub(),
        _run_flask_guard_tests(),
        _check_worker_units_documented(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "phase": "5-flask-retire",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "failed_ids": [c["id"] for c in checks if not c.get("ok")],
        "notes": "Apply: APPLY=1 sudo -E ./scripts/close_flask_retirement.sh",
    }
    dest = _artifacts_dir() / "phase5-flask-retirement-gate-report.json"
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
