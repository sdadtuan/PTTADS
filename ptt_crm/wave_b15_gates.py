"""Wave B15 — Meta Enterprise Ads Ops UI gates."""
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


def _check_b15_modules() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.meta-enterprise-b15.example",
        ROOT / "ptt_meta/ads_ops.py",
        ROOT / "ptt_meta/ads_edit.py",
        ROOT / "ptt_meta/creative_upload.py",
        ROOT / "tests/test_ads_ops.py",
        ROOT / "tests/test_b15_ads_ops_qa.py",
        ROOT / "services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.module.ts",
        ROOT / "services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.controller.ts",
        ROOT / "services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.service.ts",
        ROOT / "services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.repository.ts",
        ROOT / "services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.service.spec.ts",
        ROOT / "services/ops-web/src/app/meta/ads-ops/page.tsx",
        ROOT / "services/ops-web/src/app/meta/ads-ops/MetaAdsOpsContent.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaWizardStepper.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaCreativePicker.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaEditAdLink.tsx",
        ROOT / "services/ops-web/src/lib/meta/ads-ops-url.ts",
        ROOT / "scripts/wave_b15_gate.sh",
        ROOT / "scripts/wave_b15_smoke.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B15-G01", "ok": not missing, "label": "Wave B15 module files", "missing": missing}


def _check_ads_ops_flag_default() -> dict[str, Any]:
    off = not _truthy("PTT_META_ADS_OPS_ENABLED", "0")
    return {
        "id": "B15-G02",
        "ok": off,
        "label": "PTT_META_ADS_OPS_ENABLED default off",
        "off": off,
    }


def _run_b15_python_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_ads_ops",
            "tests.test_b15_ads_ops_qa",
            "-v",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B15-G03",
        "ok": proc.returncode == 0,
        "label": "B15 Python unit tests",
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-1500:] if proc.stderr else "",
    }


def _run_b15_smoke() -> dict[str, Any]:
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b15_smoke.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "B15-G04",
        "ok": proc.returncode == 0,
        "label": "B15 smoke script",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
    }


def _run_b14_regression() -> dict[str, Any]:
    if _truthy("WAVE_B15_SKIP_B14", "0"):
        return {"id": "B15-G05", "ok": True, "label": "B14 regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [str(ROOT / "scripts" / "wave_b14_gate.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "WAVE_B14_SKIP_B13": os.environ.get("WAVE_B14_SKIP_B13", "1"),
        },
    )
    return {
        "id": "B15-G05",
        "ok": proc.returncode == 0,
        "label": "B14 regression gate",
        "returncode": proc.returncode,
    }


def _check_campaign_writes_create_actions() -> dict[str, Any]:
    try:
        text = (ROOT / "services/ptt-crm-api/src/campaign-writes/campaign-writes.types.ts").read_text(
            encoding="utf-8"
        )
        ok = all(
            token in text
            for token in (
                "create_campaign",
                "create_adset",
                "create_ad",
                "update_ad_creative",
                "update_ad_copy",
            )
        )
    except Exception as exc:
        return {"id": "B15-G06", "ok": False, "label": "Campaign write create/edit actions", "error": str(exc)}
    return {
        "id": "B15-G06",
        "ok": ok,
        "label": "Campaign write create/edit actions",
    }


def run_wave_b15_gates() -> dict[str, Any]:
    checks = [
        _check_b15_modules(),
        _check_ads_ops_flag_default(),
        _run_b15_python_tests(),
        _run_b15_smoke(),
        _run_b14_regression(),
        _check_campaign_writes_create_actions(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"ok": ok, "wave": "B15", "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "wave_b15_gate_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run_wave_b15_gates()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
