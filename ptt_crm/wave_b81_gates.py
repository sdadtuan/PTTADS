"""Wave B8.1 — Meta Enterprise breakdown + granular RBAC gates."""
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


def _check_b81_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b8-1.example",
        ROOT / "docs/specs/2026-07-24-postgresql-ddl-v8-meta-insights-breakdown.sql",
        ROOT / "scripts/apply_pg_ddl_v8_meta_insights_breakdown.sh",
        ROOT / "scripts/seed_staff_meta_rbac_b81.py",
        ROOT / "ptt_meta/insights_breakdown.py",
        ROOT / "tests/test_insights_breakdown.py",
        ROOT / "tests/test_meta_rbac_b81.py",
        ROOT / "tests/test_b81_breakdown_qa.py",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-rbac.util.ts",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-rbac.util.spec.ts",
        ROOT / "services/ptt-crm-api/test/meta-insights-breakdown-b81.e2e-spec.ts",
        ROOT / "services/ops-web/src/components/meta/MetaBreakdownPanel.tsx",
        ROOT / "scripts/wave_b8_1_gate.sh",
        ROOT / "scripts/wave_b8_1_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B81-G01", "ok": not missing, "label": "Wave B8.1 module files", "missing": missing}


def _check_breakdown_flag_default() -> dict[str, Any]:
    off = not _truthy("PTT_META_INSIGHTS_BREAKDOWN", "0")
    return {"id": "B81-G02", "ok": off, "label": "PTT_META_INSIGHTS_BREAKDOWN default off", "off": off}


def _run_b81_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_insights_breakdown",
            "tests.test_meta_rbac_b81",
            "tests.test_b81_breakdown_qa",
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B81-G03",
        "ok": proc.returncode == 0,
        "label": "B8.1 Python unit tests",
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
    }


def _run_b8_regression() -> dict[str, Any]:
    if _truthy("WAVE_B81_SKIP_B8", "0"):
        return {"id": "B81-G04", "ok": True, "label": "B8 regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b8_gate.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "WAVE_B8_SKIP_PG": os.environ.get("WAVE_B8_SKIP_PG", "1"),
            "WAVE_B8_SKIP_BUILD": os.environ.get("WAVE_B8_SKIP_BUILD", "1"),
            "WAVE_B8_SKIP_JEST": os.environ.get("WAVE_B8_SKIP_JEST", "1"),
            "WAVE_B8_SKIP_E2E": os.environ.get("WAVE_B8_SKIP_E2E", "1"),
            "WAVE_B8_SKIP_B7_GATE": os.environ.get("WAVE_B8_SKIP_B7_GATE", "1"),
            "WAVE_B8_SKIP_HORIZON1": os.environ.get("WAVE_B8_SKIP_HORIZON1", "1"),
        },
    )
    return {"id": "B81-G04", "ok": proc.returncode == 0, "label": "B8 regression gate", "returncode": proc.returncode}


def _check_ddl_v8_hint() -> dict[str, Any]:
    try:
        from ptt_crm.pg_schema import pg_daily_performance_breakdown_ready

        ready = pg_daily_performance_breakdown_ready()
    except Exception:
        ready = False
    return {
        "id": "B81-G05",
        "ok": True,
        "label": "DDL v8 readiness (informational)",
        "pg_daily_performance_breakdown_ready": ready,
        "hint": "./scripts/apply_pg_ddl_v8_meta_insights_breakdown.sh",
    }


def run_wave_b81_gates() -> dict[str, Any]:
    checks = [
        _check_b81_modules(),
        _check_breakdown_flag_default(),
        _run_b81_python_tests(),
        _run_b8_regression(),
        _check_ddl_v8_hint(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"ok": ok, "wave": "B8.1", "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave_b81_gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_wave_b81_gates()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
