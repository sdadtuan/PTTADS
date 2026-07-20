"""Phase 5 prod gate pack — governance, portal bridge, experiments + soak."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PHASE5_PYTEST_GLOBS: tuple[str, ...] = (
    "tests/test_seo_aeo_phase5_governance.py",
    "tests/test_seo_aeo_phase5_experimentation.py",
    "tests/test_seo_aeo_phase5_portal_bridge.py",
)


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_pytest() -> dict[str, Any]:
    python = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    cmd = [python, "-m", "pytest", *PHASE5_PYTEST_GLOBS, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    tail = ((proc.stdout or "") + (proc.stderr or ""))[-3000:]
    return {
        "id": "P5-G01",
        "ok": proc.returncode == 0,
        "label": "Phase 5 pytest",
        "returncode": proc.returncode,
        "output_tail": tail,
    }


def _check_feature_flags() -> dict[str, Any]:
    from ptt_seo.experimentation import experiments_enabled
    from ptt_seo.governance import governance_enabled
    from ptt_seo.portal_bridge import portal_seo_enabled

    expected_governance = os.environ.get("PHASE5_EXPECT_GOVERNANCE", "1") == "1"
    expected_portal = os.environ.get("PHASE5_EXPECT_PORTAL", "0") == "1"
    expected_experiments = os.environ.get("PHASE5_EXPECT_EXPERIMENTS", "0") == "1"
    gov = governance_enabled()
    portal = portal_seo_enabled()
    exp = experiments_enabled()
    ok = (
        gov == expected_governance
        and portal == expected_portal
        and exp == expected_experiments
    )
    return {
        "id": "P5-G02",
        "ok": ok,
        "label": "Phase 5 feature flags",
        "actual": {
            "PTT_SEO_GOVERNANCE_ENABLED": gov,
            "PTT_PORTAL_SEO_ENABLED": portal,
            "PTT_SEO_EXPERIMENTS_ENABLED": exp,
        },
        "expected": {
            "PTT_SEO_GOVERNANCE_ENABLED": expected_governance,
            "PTT_PORTAL_SEO_ENABLED": expected_portal,
            "PTT_SEO_EXPERIMENTS_ENABLED": expected_experiments,
        },
    }


def _check_portal_signoff() -> dict[str, Any]:
    path = _artifacts_dir() / "phase5-portal-seo-uat-signoff.json"
    if not path.is_file():
        skip = os.environ.get("PHASE5_SKIP_PORTAL_SIGNOFF", "0") == "1"
        return {
            "id": "P5-G03",
            "ok": skip,
            "label": "Portal SEO UAT sign-off",
            "skipped": skip,
            "error": None if skip else "missing_signoff",
            "path": str(path),
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    ok = bool(data.get("playwright_e2e"))
    return {
        "id": "P5-G03",
        "ok": ok,
        "label": "Portal SEO UAT sign-off",
        "playwright_e2e": data.get("playwright_e2e"),
        "path": str(path),
    }


def _check_soak() -> dict[str, Any]:
    from ptt_crm.phase5_soak_evidence import evaluate_soak_gate

    skip = os.environ.get("PHASE5_SKIP_SOAK", "1") == "1"
    if skip:
        return {"id": "P5-G04", "ok": True, "label": "Phase 5 soak", "skipped": True}
    result = evaluate_soak_gate()
    result["id"] = "P5-G04"
    return result


def run_gates() -> dict[str, Any]:
    checks = [_run_pytest(), _check_feature_flags(), _check_portal_signoff(), _check_soak()]
    ok = all(c.get("ok") for c in checks)
    report = {
        "phase": "5",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "notes": "Run ./scripts/phase5_prod_cutover_gate.sh. Soak: ./scripts/phase5_soak_record.sh daily x7.",
    }
    dest = _artifacts_dir() / "phase5-gate-report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run_gates()
    print(json.dumps(report, indent=2))
    if not report.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
