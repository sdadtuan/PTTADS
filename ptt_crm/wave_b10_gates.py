"""Wave B10 — Meta Enterprise Intelligence gates."""
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


def _check_b10_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b10.example",
        ROOT / "ptt_meta/anomaly.py",
        ROOT / "ptt_meta/roas.py",
        ROOT / "ptt_meta/budget_recommend.py",
        ROOT / "tests/test_meta_anomaly.py",
        ROOT / "tests/test_meta_roas.py",
        ROOT / "tests/test_meta_budget_recommend.py",
        ROOT / "tests/test_b10_intelligence_qa.py",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-intelligence.module.ts",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-intelligence.controller.ts",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-intelligence.service.ts",
        ROOT / "services/ptt-crm-api/src/meta-intelligence/meta-intelligence.util.ts",
        ROOT / "services/ptt-crm-api/test/meta-intelligence-b10.e2e-spec.ts",
        ROOT / "services/ops-web/src/app/meta/intelligence/page.tsx",
        ROOT / "services/ops-web/src/app/meta/intelligence/MetaIntelligenceContent.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaIntelligenceRoasKpi.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaAnomaliesTable.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaBudgetRecommendTable.tsx",
        ROOT / "services/ops-web/src/hooks/meta/useMetaIntelligence.ts",
        ROOT / "scripts/wave_b10_gate.sh",
        ROOT / "scripts/wave_b10_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B10-G01", "ok": not missing, "label": "Wave B10 module files", "missing": missing}


def _check_intelligence_flags_default() -> dict[str, Any]:
    anomaly_off = not _truthy("PTT_META_ANOMALY_ENABLED", "0")
    roas_off = not _truthy("PTT_META_ROAS_ENABLED", "0")
    ok = anomaly_off and roas_off
    return {
        "id": "B10-G02",
        "ok": ok,
        "label": "B10 intelligence flags default off in gate env",
        "anomaly_off": anomaly_off,
        "roas_off": roas_off,
    }


def _run_b10_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_meta_anomaly",
            "tests.test_meta_roas",
            "tests.test_meta_budget_recommend",
            "-v",
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    return {
        "id": "B10-G03",
        "ok": proc.returncode == 0,
        "label": "unittest anomaly + roas + budget_recommend",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_b10_qa_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_b10_intelligence_qa", "-v"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    return {
        "id": "B10-G04",
        "ok": proc.returncode == 0,
        "label": "unittest tests.test_b10_intelligence_qa",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_build() -> dict[str, Any]:
    if _truthy("WAVE_B10_SKIP_BUILD", "0"):
        return {"id": "B10-G05", "ok": True, "label": "Nest build (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(api), capture_output=True, text=True)
    return {
        "id": "B10-G05",
        "ok": proc.returncode == 0,
        "label": "Nest build (ptt-crm-api)",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_jest_b10() -> dict[str, Any]:
    if _truthy("WAVE_B10_SKIP_JEST", "0"):
        return {"id": "B10-G06", "ok": True, "label": "Nest jest B10 (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    unit = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=meta-intelligence", "--silent"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    e2e = subprocess.run(
        ["npm", "run", "test:e2e", "--", "--testPathPattern=meta-intelligence-b10", "--silent"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    ok = unit.returncode == 0 and e2e.returncode == 0
    return {
        "id": "B10-G06",
        "ok": ok,
        "label": "Nest jest + e2e B10 meta-intelligence",
        "unit_returncode": unit.returncode,
        "e2e_returncode": e2e.returncode,
        "tail": (unit.stdout or unit.stderr or e2e.stdout or e2e.stderr)[-800:],
    }


def _run_ops_web_build() -> dict[str, Any]:
    if _truthy("WAVE_B10_SKIP_BUILD", "0"):
        return {"id": "B10-G07", "ok": True, "label": "ops-web build (skipped)", "skipped": True}
    ops = ROOT / "services/ops-web"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(ops), capture_output=True, text=True)
    return {
        "id": "B10-G07",
        "ok": proc.returncode == 0,
        "label": "ops-web build",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_wave_b9_gate() -> dict[str, Any]:
    if _truthy("WAVE_B10_SKIP_B9_GATE", "0"):
        return {"id": "B10-G08", "ok": True, "label": "Wave B9 regression gate (skipped)", "skipped": True}
    b9 = ROOT / "ptt_crm/wave_b9_gates.py"
    if not b9.is_file():
        return {"id": "B10-G08", "ok": True, "label": "Wave B9 gate absent", "skipped": True}
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.wave_b9_gates"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "WAVE_B9_SKIP_BUILD": "1",
            "WAVE_B9_SKIP_JEST": "1",
            "WAVE_B9_SKIP_E2E": "1",
            "WAVE_B9_SKIP_B8_GATE": "1",
            "WAVE_B9_SKIP_HORIZON1": "1",
            "WAVE_B9_SKIP_SOAK": "1",
        },
        capture_output=True,
        text=True,
    )
    return {
        "id": "B10-G08",
        "ok": proc.returncode == 0,
        "label": "Wave B9 regression gate",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def run_wave_b10_gates() -> dict[str, Any]:
    checks = [
        _check_b10_modules(),
        _check_intelligence_flags_default(),
        _run_b10_python_tests(),
        _run_b10_qa_tests(),
        _run_nest_build(),
        _run_nest_jest_b10(),
        _run_ops_web_build(),
        _run_wave_b9_gate(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"wave": "b10", "ok": ok, "generated_at": _now_iso(), "checks": checks}
    out = _artifacts_dir() / "wave-b10-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wave": "b10", "ok": ok}, ensure_ascii=False))
    if not ok:
        for c in checks:
            if not c.get("ok"):
                print(f"FAIL {c.get('id')} {c.get('label')}", file=sys.stderr)
        sys.exit(1)
    return report


if __name__ == "__main__":
    run_wave_b10_gates()
