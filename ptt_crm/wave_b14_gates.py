"""Wave B14 — Meta Enterprise warehouse BI gates."""
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


def _check_b14_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b14.example",
        ROOT / "deploy/clickhouse/init-meta-daily-facts.sql",
        ROOT / "deploy/grafana/meta-ops-dashboard.json",
        ROOT / "ptt_meta/warehouse_export.py",
        ROOT / "ptt_jobs/handlers/meta_clickhouse_export.py",
        ROOT / "tests/test_warehouse_export.py",
        ROOT / "tests/test_b14_warehouse_qa.py",
        ROOT / "services/ptt-crm-api/src/meta-compliance/meta-compliance.controller.ts",
        ROOT / "services/ptt-crm-api/src/meta-compliance/meta-compliance.service.spec.ts",
        ROOT / "services/ptt-crm-api/src/metrics/metrics.controller.ts",
        ROOT / "services/ptt-crm-api/src/metrics/metrics.service.spec.ts",
        ROOT / "scripts/export_meta_facts_clickhouse.sh",
        ROOT / "scripts/wave_b14_gate.sh",
        ROOT / "scripts/wave_b14_smoke.sh",
        ROOT / "deploy/ptt-meta-clickhouse-export.service",
        ROOT / "deploy/ptt-meta-clickhouse-export.timer",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B14-G01", "ok": not missing, "label": "Wave B14 module files", "missing": missing}


def _check_warehouse_flag_default() -> dict[str, Any]:
    off = not _truthy("PTT_META_WAREHOUSE_EXPORT", "0")
    return {
        "id": "B14-G02",
        "ok": off,
        "label": "PTT_META_WAREHOUSE_EXPORT default off",
        "off": off,
    }


def _run_b14_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_warehouse_export",
            "tests.test_b14_warehouse_qa",
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B14-G03",
        "ok": proc.returncode == 0,
        "label": "B14 Python unit tests",
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
    }


def _run_b14_smoke() -> dict[str, Any]:
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b14_smoke.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B14-G04",
        "ok": proc.returncode == 0,
        "label": "B14 smoke script",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
    }


def _run_b13_regression() -> dict[str, Any]:
    if _truthy("WAVE_B14_SKIP_B13", "0"):
        return {"id": "B14-G05", "ok": True, "label": "B13 regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b13_gate.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "WAVE_B13_SKIP_B12": os.environ.get("WAVE_B13_SKIP_B12", "1"),
        },
    )
    return {
        "id": "B14-G05",
        "ok": proc.returncode == 0,
        "label": "B13 regression gate",
        "returncode": proc.returncode,
    }


def _check_grafana_spend_panel() -> dict[str, Any]:
    try:
        dash = json.loads((ROOT / "deploy/grafana/meta-ops-dashboard.json").read_text(encoding="utf-8"))
        titles = [str(p.get("title", "")).lower() for p in dash.get("panels", [])]
        ok = any("spend trend" in t for t in titles)
    except Exception as exc:
        return {"id": "B14-G06", "ok": False, "label": "Grafana spend trend panel", "error": str(exc)}
    return {
        "id": "B14-G06",
        "ok": ok,
        "label": "Grafana spend trend panel",
        "hint": "Import deploy/grafana/meta-ops-dashboard.json",
    }


def run_wave_b14_gates() -> dict[str, Any]:
    checks = [
        _check_b14_modules(),
        _check_warehouse_flag_default(),
        _run_b14_python_tests(),
        _run_b14_smoke(),
        _run_b13_regression(),
        _check_grafana_spend_panel(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"ok": ok, "wave": "B14", "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave_b14_gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_wave_b14_gates()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
