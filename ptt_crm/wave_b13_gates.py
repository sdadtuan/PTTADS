"""Wave B13 — Meta Enterprise ops webhooks gates."""
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


def _check_b13_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b13.example",
        ROOT / "ptt_meta/ops_webhooks.py",
        ROOT / "ptt_jobs/handlers/meta_ops_webhook.py",
        ROOT / "tests/test_ops_webhooks.py",
        ROOT / "tests/test_b13_ops_webhooks_qa.py",
        ROOT / "tests/fixtures/channels/meta/webhook_account_disabled.json",
        ROOT / "services/ptt-crm-api/src/webhooks/meta-ops-webhook.parser.ts",
        ROOT / "services/ptt-crm-api/src/webhooks/meta-ops-webhook.service.ts",
        ROOT / "services/ptt-crm-api/src/webhooks/meta-ops-webhook.parser.spec.ts",
        ROOT / "services/ptt-crm-api/src/webhooks/meta-ops-webhook.service.spec.ts",
        ROOT / "scripts/wave_b13_gate.sh",
        ROOT / "scripts/wave_b13_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B13-G01", "ok": not missing, "label": "Wave B13 module files", "missing": missing}


def _check_ops_webhooks_flag_default() -> dict[str, Any]:
    off = not _truthy("PTT_META_OPS_WEBHOOKS", "0")
    return {
        "id": "B13-G02",
        "ok": off,
        "label": "PTT_META_OPS_WEBHOOKS default off",
        "off": off,
    }


def _run_b13_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_ops_webhooks",
            "tests.test_b13_ops_webhooks_qa",
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B13-G03",
        "ok": proc.returncode == 0,
        "label": "B13 Python unit tests",
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
    }


def _run_b13_smoke() -> dict[str, Any]:
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b13_smoke.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B13-G04",
        "ok": proc.returncode == 0,
        "label": "B13 smoke script",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
    }


def _run_b12_regression() -> dict[str, Any]:
    if _truthy("WAVE_B13_SKIP_B12", "0"):
        return {"id": "B13-G05", "ok": True, "label": "B12 regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b12_gate.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "WAVE_B12_SKIP_B11": os.environ.get("WAVE_B12_SKIP_B11", "1"),
            "WAVE_B12_SKIP_PG": os.environ.get("WAVE_B12_SKIP_PG", "1"),
        },
    )
    return {
        "id": "B13-G05",
        "ok": proc.returncode == 0,
        "label": "B12 regression gate",
        "returncode": proc.returncode,
    }


def _check_meta_alerts_hint() -> dict[str, Any]:
    try:
        from ptt_crm.pg_schema import pg_meta_alerts_ready

        ready = pg_meta_alerts_ready()
    except Exception:
        ready = False
    return {
        "id": "B13-G06",
        "ok": True,
        "label": "meta_alerts readiness (informational)",
        "pg_meta_alerts_ready": ready,
        "hint": "Enable PTT_META_ALERTS_ENABLED=1 for hub badge display",
    }


def run_wave_b13_gates() -> dict[str, Any]:
    checks = [
        _check_b13_modules(),
        _check_ops_webhooks_flag_default(),
        _run_b13_python_tests(),
        _run_b13_smoke(),
        _run_b12_regression(),
        _check_meta_alerts_hint(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"ok": ok, "wave": "B13", "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave_b13_gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_wave_b13_gates()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
