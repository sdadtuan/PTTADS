"""Wave SEO Phase 7 (B7) — Gate A go-live & ops-web retirement gates."""
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
        ROOT / "services/ptt-crm-api/src/seo-gate-a/seo-gate-a.module.ts",
        ROOT / "services/ptt-crm-api/src/seo-gate-a/seo-gate-a.controller.ts",
        ROOT / "services/ops-web/src/app/seo/gate-a/page.tsx",
        ROOT / "deploy/env.seo-gate-a-prod.example",
        ROOT / "deploy/nginx-seo-gate-a-redirect.conf",
        ROOT / "docs/evidence/seo-gate-a-signoff.template.json",
        ROOT / "scripts/seo_gate_a_cutover_gate.sh",
        ROOT / "scripts/seo_gate_a_pack.sh",
        ROOT / "scripts/wave_seo_b7_gate.sh",
        ROOT / "tests/test_seo_b7_qa.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "SEO-B7-G01", "ok": not missing, "label": "B7 Gate A module files", "missing": missing}


def _run_python_qa() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_seo_b7_qa", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "id": "SEO-B7-G02",
        "ok": proc.returncode == 0,
        "label": "Python B7 QA tests",
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def _check_ops_web_routes() -> dict[str, Any]:
    huong_dan = (ROOT / "docs/huong-dan-seo-aeo-ops.md").read_text(encoding="utf-8")
    bad = "/crm/seo" in huong_dan.split("## 5. Hướng dẫn từng module")[0]
    ops_nav = (ROOT / "services/ops-web/src/components/OpsNav.tsx").read_text(encoding="utf-8")
    has_gate_a = "/seo/gate-a" in ops_nav
    return {
        "id": "SEO-B7-G03",
        "ok": not bad and has_gate_a,
        "label": "ops-web routes + huong-dan (no /crm/seo in overview)",
        "huong_dan_crm_seo_in_overview": bad,
        "ops_nav_gate_a": has_gate_a,
    }


def _check_nginx_redirect() -> dict[str, Any]:
    nginx = ROOT / "deploy/nginx-seo-gate-a-redirect.conf"
    text = nginx.read_text(encoding="utf-8") if nginx.is_file() else ""
    ok = "/crm/seo/" in text and "/seo$1" in text
    return {"id": "SEO-B7-G04", "ok": ok, "label": "Nginx /crm/seo → /seo redirect", "path": str(nginx)}


def _run_prior_wave_gates() -> dict[str, Any]:
    if os.environ.get("WAVE_SEO_B7_SKIP_PRIOR", "0") == "1":
        return {"id": "SEO-B7-G05", "ok": True, "label": "Prior wave gates B2–B6", "skipped": True}
    env = {**os.environ, "WAVE_SEO_B5_SKIP_JEST": "1"}
    scripts = [
        "scripts/wave_seo_b2_gate.sh",
        "scripts/wave_seo_b3_gate.sh",
        "scripts/wave_seo_b4_gate.sh",
        "scripts/wave_seo_b5_gate.sh",
        "scripts/wave_seo_b6_gate.sh",
    ]
    failed: list[str] = []
    for rel in scripts:
        proc = subprocess.run(["bash", rel], cwd=ROOT, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            failed.append(rel)
    return {
        "id": "SEO-B7-G05",
        "ok": not failed,
        "label": "Prior wave gates B2–B6",
        "failed": failed,
    }


def run_gates() -> dict[str, Any]:
    checks = [
        _check_module_files(),
        _run_python_qa(),
        _check_ops_web_routes(),
        _check_nginx_redirect(),
        _run_prior_wave_gates(),
    ]
    ok = all(c["ok"] for c in checks)
    report = {"ok": ok, "phase": "7", "gate": "A", "generated_at": _now_iso(), "checks": checks}
    out_dir = _artifacts_dir() / "wave-gates"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "seo_b7_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run_gates()
    for check in report["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"[{status}] {check['id']}: {check['label']}")
    print(f"Report: {_artifacts_dir() / 'wave-gates' / 'seo_b7_gate_report.json'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
