"""Wave B12 — Meta Enterprise creative registry gates."""
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


def _check_b12_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b12.example",
        ROOT / "docs/specs/2026-07-25-postgresql-ddl-v9-meta-creative-registry.sql",
        ROOT / "scripts/apply_pg_ddl_v9_meta_creative_registry.sh",
        ROOT / "ptt_meta/creative_registry.py",
        ROOT / "tests/test_creative_registry.py",
        ROOT / "tests/test_b12_creative_registry_qa.py",
        ROOT / "services/ptt-crm-api/src/meta-creative-registry/meta-creative-registry.controller.ts",
        ROOT / "services/ptt-crm-api/src/meta-creative-registry/meta-creative-registry.service.spec.ts",
        ROOT / "services/ptt-crm-api/test/meta-creative-registry-b12.e2e-spec.ts",
        ROOT / "services/ops-web/src/components/meta/MetaCreativeLinkPanel.tsx",
        ROOT / "scripts/wave_b12_gate.sh",
        ROOT / "scripts/wave_b12_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B12-G01", "ok": not missing, "label": "Wave B12 module files", "missing": missing}


def _check_registry_flag_default() -> dict[str, Any]:
    off = not _truthy("PTT_META_CREATIVE_REGISTRY_ENABLED", "0")
    return {
        "id": "B12-G02",
        "ok": off,
        "label": "PTT_META_CREATIVE_REGISTRY_ENABLED default off",
        "off": off,
    }


def _run_b12_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_creative_registry",
            "tests.test_b12_creative_registry_qa",
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B12-G03",
        "ok": proc.returncode == 0,
        "label": "B12 Python unit tests",
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
    }


def _run_b11_regression() -> dict[str, Any]:
    if _truthy("WAVE_B12_SKIP_B11", "0"):
        return {"id": "B12-G04", "ok": True, "label": "B11 regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b11_gate.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "WAVE_B11_SKIP_PG": os.environ.get("WAVE_B11_SKIP_PG", "1"),
            "WAVE_B11_SKIP_B10": os.environ.get("WAVE_B11_SKIP_B10", "1"),
        },
    )
    return {
        "id": "B12-G04",
        "ok": proc.returncode == 0,
        "label": "B11 regression gate",
        "returncode": proc.returncode,
    }


def _check_ddl_v9_hint() -> dict[str, Any]:
    try:
        from ptt_crm.pg_schema import pg_meta_ad_creative_links_ready

        ready = pg_meta_ad_creative_links_ready()
    except Exception:
        ready = False
    return {
        "id": "B12-G05",
        "ok": True,
        "label": "DDL v9 readiness (informational)",
        "pg_meta_ad_creative_links_ready": ready,
        "hint": "./scripts/apply_pg_ddl_v9_meta_creative_registry.sh",
    }


def run_wave_b12_gates() -> dict[str, Any]:
    checks = [
        _check_b12_modules(),
        _check_registry_flag_default(),
        _run_b12_python_tests(),
        _run_b11_regression(),
        _check_ddl_v9_hint(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"ok": ok, "wave": "B12", "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave_b12_gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_wave_b12_gates()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
