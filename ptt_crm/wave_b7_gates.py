"""Wave B7 — Client offboard + tenant lock gates (B7.1-S1/S2)."""
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


def _check_b7_modules() -> dict[str, Any]:
    files = [
        ROOT / "docs/specs/2026-07-23-wave-b7-offboarding-flask-retire-design.md",
        ROOT / "docs/specs/2026-07-23-postgresql-ddl-v3-client-offboard.sql",
        ROOT / "services/ptt-crm-api/src/agency/client-offboard.service.ts",
        ROOT / "services/ptt-crm-api/src/agency/client-offboard.repository.ts",
        ROOT / "services/ptt-crm-api/src/agency/guards/staff-agency-configure.guard.ts",
        ROOT / "services/ops-web/src/app/agency/clients/[id]/AgencyClientDetailContent.tsx",
        ROOT / "services/ptt-crm-api/src/agency/client-offboard.service.spec.ts",
        ROOT / "services/ptt-crm-api/src/portal/portal-jwt.guard.ts",
        ROOT / "services/portal-web/src/app/archived/page.tsx",
        ROOT / "services/portal-web/src/hooks/usePortalAuth.ts",
        ROOT / "scripts/apply_pg_ddl_v3_client_offboard.sh",
        ROOT / "scripts/wave_b7_gate.sh",
        ROOT / "scripts/wave_b7_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B7-G01", "ok": not missing, "label": "Wave B7 module files", "missing": missing}


def _check_pg_offboard_ddl() -> dict[str, Any]:
    if _truthy("WAVE_B7_SKIP_PG", "0"):
        return {"id": "B7-G02", "ok": True, "label": "PG client offboard DDL (skipped)", "skipped": True}
    try:
        from ptt_crm.pg_schema import pg_client_offboard_ready

        ok = pg_client_offboard_ready()
    except Exception as exc:
        ok = False
        err = str(exc)
    else:
        err = None
    return {
        "id": "B7-G02",
        "ok": ok,
        "label": "PG client_offboard_audit + tenant_locked",
        "error": err,
        "hint": "./scripts/apply_pg_ddl_v3_client_offboard.sh",
    }


def _run_nest_jest() -> dict[str, Any]:
    if _truthy("WAVE_B7_SKIP_JEST", "0"):
        return {"id": "B7-G03", "ok": True, "label": "Nest jest B7 offboard (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    proc = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=client-offboard", "--silent"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B7-G03",
        "ok": ok,
        "label": "Nest jest client-offboard",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_build() -> dict[str, Any]:
    if _truthy("WAVE_B7_SKIP_BUILD", "0"):
        return {"id": "B7-G04", "ok": True, "label": "Nest build (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(api), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B7-G04",
        "ok": ok,
        "label": "Nest build (ptt-crm-api)",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_b6_gate() -> dict[str, Any]:
    if _truthy("WAVE_B7_SKIP_B6_GATE", "0"):
        return {"id": "B7-G05", "ok": True, "label": "Wave B6 regression gate (skipped)", "skipped": True}
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.wave_b6_gates"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT), "WAVE_B6_SKIP_JEST": "1"},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B7-G05",
        "ok": ok,
        "label": "Wave B6 regression gate",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def run_wave_b7_gates() -> dict[str, Any]:
    checks = [_check_b7_modules(), _check_pg_offboard_ddl(), _run_nest_jest(), _run_nest_build(), _run_b6_gate()]
    ok = all(c.get("ok") for c in checks)
    report = {"wave": "b7", "ok": ok, "generated_at": _now_iso(), "checks": checks}
    out = _artifacts_dir() / "wave-b7-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wave": "b7", "ok": ok}, ensure_ascii=False))
    if not ok:
        for c in checks:
            if not c.get("ok"):
                print(f"FAIL {c.get('id')} {c.get('label')}", file=sys.stderr)
        sys.exit(1)
    return report


if __name__ == "__main__":
    run_wave_b7_gates()
