"""Wave B11 — Meta Enterprise Advanced gates."""
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


def _check_b11_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b11.example",
        ROOT / "docs/specs/2026-07-24-postgresql-ddl-v7-meta-advanced.sql",
        ROOT / "scripts/apply_pg_ddl_v7_meta_advanced.sh",
        ROOT / "ptt_meta/anomaly_stat.py",
        ROOT / "ptt_meta/forecast.py",
        ROOT / "ptt_meta/meta_pixels.py",
        ROOT / "ptt_meta/intelligence_snapshot.py",
        ROOT / "tests/test_meta_anomaly_stat.py",
        ROOT / "tests/test_meta_forecast.py",
        ROOT / "tests/test_meta_pixels.py",
        ROOT / "tests/test_meta_intelligence_snapshot.py",
        ROOT / "tests/test_b11_advanced_qa.py",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-intelligence.controller.ts",
        ROOT / "services/ptt-crm-api/test/meta-intelligence-b11.e2e-spec.ts",
        ROOT / "services/ops-web/src/components/meta/MetaForecastPanel.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaStatAnomaliesTable.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaPixelsTable.tsx",
        ROOT / "scripts/wave_b11_gate.sh",
        ROOT / "scripts/wave_b11_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B11-G01", "ok": not missing, "label": "Wave B11 module files", "missing": missing}


def _check_b11_flags_default() -> dict[str, Any]:
    stat_off = not _truthy("PTT_META_ANOMALY_STAT_ENABLED", "0")
    forecast_off = not _truthy("PTT_META_FORECAST_ENABLED", "0")
    pixels_off = not _truthy("PTT_META_PIXELS_ENABLED", "0")
    snapshot_off = not _truthy("PTT_META_INTEL_SNAPSHOT_ENABLED", "0")
    ok = stat_off and forecast_off and pixels_off and snapshot_off
    return {
        "id": "B11-G02",
        "ok": ok,
        "label": "B11 advanced flags default off in gate env",
        "stat_off": stat_off,
        "forecast_off": forecast_off,
        "pixels_off": pixels_off,
        "snapshot_off": snapshot_off,
    }


def _run_b11_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_meta_anomaly_stat",
            "tests.test_meta_forecast",
            "tests.test_meta_pixels",
            "tests.test_meta_intelligence_snapshot",
            "tests.test_b11_advanced_qa",
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B11-G03",
        "ok": proc.returncode == 0,
        "label": "B11 Python unit tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
    }


def _run_b10_regression() -> dict[str, Any]:
    if _truthy("WAVE_B11_SKIP_B10", "0"):
        return {"id": "B11-G04", "ok": True, "label": "B10 regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b10_gate.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "WAVE_B10_SKIP_PG": os.environ.get("WAVE_B10_SKIP_PG", "1")},
    )
    return {
        "id": "B11-G04",
        "ok": proc.returncode == 0,
        "label": "B10 regression gate",
        "returncode": proc.returncode,
    }


def _check_ddl_v7_hint() -> dict[str, Any]:
    try:
        from ptt_crm.pg_schema import pg_meta_pixels_ready

        ready = pg_meta_pixels_ready()
    except Exception:
        ready = False
    return {
        "id": "B11-G05",
        "ok": True,
        "label": "DDL v7 readiness (informational)",
        "pg_meta_pixels_ready": ready,
        "hint": "./scripts/apply_pg_ddl_v7_meta_advanced.sh",
    }


def run_wave_b11_gates() -> dict[str, Any]:
    checks = [
        _check_b11_modules(),
        _check_b11_flags_default(),
        _run_b11_python_tests(),
        _run_b10_regression(),
        _check_ddl_v7_hint(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "ok": ok,
        "wave": "B11",
        "generated_at": _now_iso(),
        "checks": checks,
    }
    out_dir = _artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "wave_b11_gate_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_wave_b11_gates()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
