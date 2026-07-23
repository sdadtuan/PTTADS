"""Wave B5 — Service delivery lifecycle gates (S0–S5)."""
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


def _check_env_service_delivery() -> dict[str, Any]:
    actual = _truthy("PTT_CRM_SERVICE_DELIVERY_NEST", "0")
    expect = _truthy("WAVE_B5_EXPECT_SERVICE_DELIVERY_NEST", "1")
    ok = actual if expect else True
    return {
        "id": "B5-G01",
        "ok": ok,
        "label": "PTT_CRM_SERVICE_DELIVERY_NEST enabled",
        "actual": actual,
        "expected": expect,
    }


def _check_lifecycle_workflow_json() -> dict[str, Any]:
    path = ROOT / "services/ptt-crm-api/src/leads-contract/lifecycle-workflow-steps.data.json"
    ok = path.is_file() and path.stat().st_size > 500
    return {"id": "B5-G02", "ok": ok, "label": "Lifecycle workflow steps JSON present"}


def _check_nest_modules() -> dict[str, Any]:
    files = [
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-stage.util.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-tasks.repository.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-marketing-plan.util.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-consult.service.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-payment-gate.util.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/service-lifecycle-sqlite.repository.ts",
        ROOT / "services/ptt-crm-api/src/sop/sop-auto-start.service.ts",
        ROOT / "services/ptt-crm-api/src/sop/sop-auto-start.util.ts",
        ROOT / "services/ops-web/src/components/ServiceDeliveryKanban.tsx",
        ROOT / "services/ops-web/src/components/ServiceDeliveryWorkflowPanel.tsx",
        ROOT / "services/ops-web/src/components/LifecycleStaffPicker.tsx",
        ROOT / "services/ops-web/src/components/LifecycleHubLinksPanel.tsx",
        ROOT / "services/ops-web/src/components/LifecycleTmmtPanel.tsx",
        ROOT / "services/ops-web/src/components/LifecycleFinancePanel.tsx",
        ROOT / "services/ops-web/src/components/LifecycleSopPanel.tsx",
        ROOT / "docs/specs/2026-07-23-wave-b5-s3-tmmt-consult-design.md",
        ROOT / "docs/specs/2026-07-23-wave-b5-s4-finance-handoff-design.md",
        ROOT / "docs/specs/2026-07-23-wave-b5-s5-sop-cutover-design.md",
        ROOT / "docs/specs/2026-07-23-wave-b5-s6-closure-design.md",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {
        "id": "B5-G03",
        "ok": not missing,
        "label": "Wave B5 Nest + ops-web module files",
        "missing": missing,
    }


def _check_scripts() -> dict[str, Any]:
    scripts = [
        ROOT / "scripts/wave_b5_s0_gate.sh",
        ROOT / "scripts/wave_b5_gate.sh",
        ROOT / "scripts/wave_b5_pytest_parity.sh",
        ROOT / "scripts/wave_b5_deploy.sh",
        ROOT / "scripts/wave_b5_smoke.sh",
        ROOT / "scripts/wave_b5_signoff.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in scripts if not p.is_file()]
    return {"id": "B5-G04", "ok": not missing, "label": "Wave B5 gate/deploy scripts", "missing": missing}


def _run_pytest_parity() -> dict[str, Any]:
    if _truthy("WAVE_B5_SKIP_PYTEST", "0"):
        return {"id": "B5-G05", "ok": True, "label": "pytest parity (skipped)", "skipped": True}
    tests = [
        "tests/test_crm_lead_presales.py",
        "tests/test_crm_lead_presales_contract.py",
        "tests/test_crm_service_lifecycle.py",
        "tests/test_crm_svc_tasks.py",
        "tests/test_crm_lead_presales_marketing_plan.py",
        "tests/test_crm_svc_finance_presales_on_lead.py",
        "tests/test_crm_svc_consult_bridge.py",
    ]
    cmd = [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B5-G05",
        "ok": ok,
        "label": "pytest lifecycle parity",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_jest() -> dict[str, Any]:
    if _truthy("WAVE_B5_SKIP_JEST", "0"):
        return {"id": "B5-G06", "ok": True, "label": "Nest jest (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    cmd = [
        "npm",
        "test",
        "--",
        "--testPathPattern=service-lifecycle|leads-contract|lifecycle-stage|lifecycle-marketing|lifecycle-consult|lifecycle-payment|sop-auto-start",
        "--silent",
    ]
    proc = subprocess.run(cmd, cwd=str(api), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B5-G06",
        "ok": ok,
        "label": "Nest jest Wave B5",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def run_wave_b5_gates() -> dict[str, Any]:
    checks = [
        _check_env_service_delivery(),
        _check_lifecycle_workflow_json(),
        _check_nest_modules(),
        _check_scripts(),
        _run_pytest_parity(),
        _run_nest_jest(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"wave": "b5", "ok": ok, "generated_at": _now_iso(), "checks": checks}
    out = _artifacts_dir() / "wave-b5-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wave": "b5", "ok": ok}, ensure_ascii=False))
    if not ok:
        for c in checks:
            if not c.get("ok"):
                print(f"FAIL {c.get('id')} {c.get('label')}", file=sys.stderr)
        sys.exit(1)
    return report


if __name__ == "__main__":
    run_wave_b5_gates()
