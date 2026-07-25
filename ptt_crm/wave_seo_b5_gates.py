"""Wave SEO Phase 5 (B5) — client portal SEO prod gates."""
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
        ROOT / "services/ptt-crm-api/src/portal-seo/portal-seo.module.ts",
        ROOT / "services/ptt-crm-api/src/portal-seo/portal-seo.controller.ts",
        ROOT / "services/portal-web/src/app/seo/page.tsx",
        ROOT / "services/portal-web/src/app/seo/reports/page.tsx",
        ROOT / "services/portal-web/src/app/seo/content/page.tsx",
        ROOT / "services/portal-web/src/app/seo/content/[id]/page.tsx",
        ROOT / "services/portal-web/src/components/SeoWidgetsPanel.tsx",
        ROOT / "services/portal-web/src/hooks/usePortalSeoNav.ts",
        ROOT / "services/portal-web/e2e/portal-seo.spec.ts",
        ROOT / "scripts/seed_portal_seo_pilot_map.py",
        ROOT / "scripts/seed_portal_seo_e2e_content.py",
        ROOT / "scripts/phase5_portal_seo_e2e_gate.sh",
        ROOT / "scripts/wave_seo_b5_gate.sh",
        ROOT / "tests/test_seo_b5_qa.py",
        ROOT / "deploy/env.seo-portal-pilot.example",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "SEO-B5-G01", "ok": not missing, "label": "B5 portal module files", "missing": missing}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_seo_b5_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "SEO-B5-G02",
        "ok": proc.returncode == 0,
        "label": "Python B5 QA tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _run_portal_seo_jest() -> dict[str, Any]:
    if os.environ.get("WAVE_SEO_B5_SKIP_JEST", "0") == "1":
        return {"id": "SEO-B5-G03", "ok": True, "label": "Nest portal-seo unit tests", "skipped": True}
    proc = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=portal-seo", "--passWithNoTests"],
        cwd=ROOT / "services/ptt-crm-api",
        capture_output=True,
        text=True,
    )
    return {
        "id": "SEO-B5-G03",
        "ok": proc.returncode == 0,
        "label": "Nest portal-seo unit tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_gates() -> dict[str, Any]:
    checks = [_check_module_files(), _run_python_qa(), _run_portal_seo_jest()]
    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "seo_b5_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'seo_b5_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
