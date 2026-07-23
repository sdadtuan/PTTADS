"""Wave B6 — Launch QA + Creative brief gates."""
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


def _check_b6_modules() -> dict[str, Any]:
    files = [
        ROOT / "docs/specs/2026-07-23-wave-b6-s3-creative-e2e-design.md",
        ROOT / "services/ptt-crm-api/src/crm-creatives/crm-creatives.controller.ts",
        ROOT / "services/ptt-crm-api/src/launch-qa/launch-qa-creative-bridge.service.ts",
        ROOT / "services/ops-web/src/app/crm/creatives/page.tsx",
        ROOT / "services/ptt-crm-api/src/launch-qa/launch-qa.controller.ts",
        ROOT / "services/ops-web/src/app/crm/launch-qa/page.tsx",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-launch-gate.util.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/launch-qa-pg.repository.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/launch-qa-auto-start.service.ts",
        ROOT / "services/ptt-crm-api/src/service-lifecycle/lifecycle-launch-qa.service.ts",
        ROOT / "services/ops-web/src/components/LifecycleLaunchQaPanel.tsx",
        ROOT / "scripts/wave_b6_gate.sh",
        ROOT / "scripts/wave_b6_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B6-G01", "ok": not missing, "label": "Wave B6 module files", "missing": missing}


def _check_env() -> dict[str, Any]:
    actual = _truthy("PTT_LAUNCH_QA_AUTO_START_ON_DELIVER", "0")
    expect = _truthy("WAVE_B6_EXPECT_LAUNCH_QA_AUTO_START", "0")
    ok = actual if expect else True
    return {
        "id": "B6-G02",
        "ok": ok,
        "label": "PTT_LAUNCH_QA_AUTO_START_ON_DELIVER",
        "actual": actual,
        "expected": expect,
    }


def _run_nest_jest() -> dict[str, Any]:
    if _truthy("WAVE_B6_SKIP_JEST", "0"):
        return {"id": "B6-G03", "ok": True, "label": "Nest jest B6 (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    cmd = [
        "npm",
        "test",
        "--",
        "--testPathPattern=lifecycle-launch|launch-qa-auto-start|launch-qa-creative-bridge|lifecycle-stage",
        "--silent",
    ]
    proc = subprocess.run(cmd, cwd=str(api), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B6-G03",
        "ok": ok,
        "label": "Nest jest Wave B6",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_b5_gate() -> dict[str, Any]:
    if _truthy("WAVE_B6_SKIP_B5_GATE", "0"):
        return {"id": "B6-G04", "ok": True, "label": "Wave B5 gate (skipped)", "skipped": True}
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.wave_b5_gates"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B6-G04",
        "ok": ok,
        "label": "Wave B5 regression gate",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def run_wave_b6_gates() -> dict[str, Any]:
    checks = [_check_b6_modules(), _check_env(), _run_nest_jest(), _run_b5_gate()]
    ok = all(c.get("ok") for c in checks)
    report = {"wave": "b6", "ok": ok, "generated_at": _now_iso(), "checks": checks}
    out = _artifacts_dir() / "wave-b6-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wave": "b6", "ok": ok}, ensure_ascii=False))
    if not ok:
        for c in checks:
            if not c.get("ok"):
                print(f"FAIL {c.get('id')} {c.get('label')}", file=sys.stderr)
        sys.exit(1)
    return report


if __name__ == "__main__":
    run_wave_b6_gates()
