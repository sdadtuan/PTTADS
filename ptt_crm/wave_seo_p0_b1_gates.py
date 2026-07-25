"""Wave SEO Phase 0 + B1 — client workspace gates."""
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


def _check_module_files() -> dict[str, Any]:
    files = [
        ROOT / "deploy/env.seo-aeo-pilot.example",
        ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.controller.ts",
        ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.repository.ts",
        ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.service.spec.ts",
        ROOT / "services/ops-web/src/app/seo/clients/[id]/page.tsx",
        ROOT / "services/ops-web/src/lib/seo/caps.ts",
        ROOT / "services/ops-web/src/lib/seo/flags.ts",
        ROOT / "scripts/seed_seo_pilot_client_settings.py",
        ROOT / "services/ptt-crm-api/src/seo-admin/seo-oauth.util.ts",
        ROOT / "services/ptt-crm-api/src/seo-admin/seo-oauth.controller.ts",
        ROOT / "services/ops-web/src/lib/seo/charts.tsx",
        ROOT / "scripts/wave_seo_p0_b1_gate.sh",
        ROOT / "tests/test_seo_p0_b1_qa.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "SEO-P0B1-G01", "ok": not missing, "label": "P0+B1 module files", "missing": missing}


def _check_ops_links() -> dict[str, Any]:
    bad: list[str] = []
    for rel in (
        "ptt_seo/hub.py",
        "ptt_seo/automation.py",
        "ptt_seo/client_tasks.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if '"/crm/seo' in text or "'/crm/seo" in text:
            bad.append(rel)
    return {"id": "SEO-P0B1-G02", "ok": not bad, "label": "Python alert links use /seo", "bad_files": bad}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_seo_p0_b1_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "SEO-P0B1-G03",
        "ok": proc.returncode == 0,
        "label": "Python P0+B1 QA tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_gates() -> dict[str, Any]:
    checks = [_check_module_files(), _check_ops_links(), _run_python_qa()]
    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "seo_p0_b1_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'seo_p0_b1_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
