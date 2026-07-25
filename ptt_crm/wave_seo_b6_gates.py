"""Wave SEO Phase 6 (B6) — BI + Gate D/E enterprise gates."""
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
        ROOT / "services/ptt-crm-api/src/seo-bi/seo-bi.module.ts",
        ROOT / "services/ptt-crm-api/src/seo-bi/seo-bi.controller.ts",
        ROOT / "services/ptt-crm-api/src/seo-cron/seo-cron.module.ts",
        ROOT / "services/ptt-crm-api/src/seo-cron/seo-cron.controller.ts",
        ROOT / "services/ptt-crm-api/src/seo-cms/seo-cms.module.ts",
        ROOT / "services/ptt-crm-api/src/seo-cms/seo-cms.controller.ts",
        ROOT / "services/ptt-crm-api/src/seo-technical/seo-crawl-internal.controller.ts",
        ROOT / "services/ops-web/src/app/seo/bi/page.tsx",
        ROOT / "services/ops-web/src/app/seo/cms/page.tsx",
        ROOT / "ptt_jobs/handlers/seo_clickhouse_export.py",
        ROOT / "deploy/env.seo-bi-gate-de.example",
        ROOT / "deploy/clickhouse/init-seo-daily-facts.sql",
        ROOT / "deploy/grafana/seo-ops-dashboard.json",
        ROOT / "scripts/wave_seo_b6_gate.sh",
        ROOT / "tests/test_seo_b6_qa.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "SEO-B6-G01", "ok": not missing, "label": "B6 module files", "missing": missing}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_seo_b6_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "SEO-B6-G02",
        "ok": proc.returncode == 0,
        "label": "Python B6 QA tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _check_infra_artifacts() -> dict[str, Any]:
    checks = {
        "clickhouse_ddl": (ROOT / "deploy/clickhouse/init-seo-daily-facts.sql").is_file(),
        "grafana_dashboard": (ROOT / "deploy/grafana/seo-ops-dashboard.json").is_file(),
        "gate_d_timer": (ROOT / "deploy/ptt-seo-gate-d.timer").is_file(),
        "ch_export_timer": (ROOT / "deploy/ptt-seo-clickhouse-export.timer").is_file(),
        "gate_d_deploy": (ROOT / "scripts/staging_seo_gate_d_deploy.sh").is_file(),
        "gate_e_deploy": (ROOT / "scripts/staging_seo_gate_e_deploy.sh").is_file(),
    }
    ok = all(checks.values())
    return {"id": "SEO-B6-G03", "ok": ok, "label": "Gate D/E infra artifacts", "checks": checks}


def run_gates() -> dict[str, Any]:
    checks = [_check_module_files(), _run_python_qa(), _check_infra_artifacts()]
    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "seo_b6_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'seo_b6_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
