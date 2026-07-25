"""Wave SEO Phase 2 (B2) — research + content pipeline gates."""
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
        ROOT / "services/ptt-crm-api/src/seo-content/seo-content.controller.ts",
        ROOT / "services/ptt-crm-api/src/seo-content/seo-content.service.ts",
        ROOT / "services/ptt-crm-api/src/seo-content/seo-content.repository.ts",
        ROOT / "services/ptt-crm-api/src/seo-content/seo-content.module.ts",
        ROOT / "services/ptt-crm-api/src/seo-content/seo-content.service.spec.ts",
        ROOT / "services/ops-web/src/app/seo/research/page.tsx",
        ROOT / "services/ops-web/src/app/seo/content/page.tsx",
        ROOT / "services/ops-web/src/app/seo/content/[id]/page.tsx",
        ROOT / "services/ops-web/src/lib/seo/caps.ts",
        ROOT / "services/ops-web/src/lib/seo/flags.ts",
        ROOT / "scripts/wave_seo_b2_gate.sh",
        ROOT / "tests/test_seo_b2_qa.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "SEO-B2-G01", "ok": not missing, "label": "B2 module files", "missing": missing}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_seo_b2_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "SEO-B2-G02",
        "ok": proc.returncode == 0,
        "label": "Python B2 QA tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_gates() -> dict[str, Any]:
    checks = [_check_module_files(), _run_python_qa()]
    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "seo_b2_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'seo_b2_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
