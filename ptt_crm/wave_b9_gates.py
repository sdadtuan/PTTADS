"""Wave B9 — Meta Enterprise Conversion OS / tracking gates."""
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


def _check_b9_modules() -> dict[str, Any]:
    files = [
        ROOT / "docs/specs/2026-07-24-postgresql-ddl-v5-meta-conversion.sql",
        ROOT / "scripts/apply_pg_ddl_v5_meta_conversion.sh",
        ROOT / "deploy/env.meta-enterprise-b9.example",
        ROOT / "ptt_meta/conversion_rules.py",
        ROOT / "ptt_meta/conversion_sync.py",
        ROOT / "ptt_meta/tracking_health.py",
        ROOT / "ptt_meta/insights_archive.py",
        ROOT / "ptt_jobs/handlers/meta_conversion_sync.py",
        ROOT / "ptt_jobs/handlers/meta_conversion_eval.py",
        ROOT / "ptt_jobs/handlers/meta_insights_archive.py",
        ROOT / "ptt_jobs/handlers/meta_alerts_eval.py",
        ROOT / "tests/test_conversion_rules.py",
        ROOT / "tests/test_conversion_sync.py",
        ROOT / "tests/test_tracking_health.py",
        ROOT / "tests/test_insights_archive.py",
        ROOT / "tests/test_capi_dispatch.py",
        ROOT / "services/ptt-crm-api/src/meta-tracking/meta-tracking.module.ts",
        ROOT / "services/ptt-crm-api/src/meta-tracking/launch-qa-meta.util.ts",
        ROOT / "services/ptt-crm-api/src/launch-qa/launch-qa-meta-bridge.service.ts",
        ROOT / "services/ptt-crm-api/test/meta-tracking-b9.e2e-spec.ts",
        ROOT / "services/ops-web/src/app/meta/tracking/page.tsx",
        ROOT / "services/ops-web/src/app/meta/tracking/MetaTrackingContent.tsx",
        ROOT / "services/ops-web/src/lib/meta/api.ts",
        ROOT / "services/ops-web/src/lib/meta/flags.ts",
        ROOT / "services/ops-web/src/components/meta/MetaTrackingKpiGrid.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaPreflightChecklist.tsx",
        ROOT / "services/ops-web/e2e/meta-tracking.spec.ts",
        ROOT / "services/ops-web/playwright.config.ts",
        ROOT / "tests/test_b9_tracking_qa.py",
        ROOT / "scripts/wave_b9_gate.sh",
        ROOT / "scripts/wave_b9_smoke.sh",
        ROOT / "scripts/playwright_ops_meta_tracking_e2e.sh",
        ROOT / "scripts/b9_tracking_soak_record.sh",
        ROOT / "scripts/b9_tracking_pilot_preflight.sh",
        ROOT / "ptt_crm/b9_tracking_soak_evidence.py",
        ROOT / "docs/runbooks/b9-tracking-pilot-soak.md",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B9-G01", "ok": not missing, "label": "Wave B9 module files", "missing": missing}


def _check_tracking_flag_default() -> dict[str, Any]:
    actual = _truthy("PTT_META_TRACKING_ENABLED", "0")
    expect_off = not _truthy("WAVE_B9_EXPECT_TRACKING_ENABLED", "0")
    ok = (not actual) if expect_off else True
    return {
        "id": "B9-G02",
        "ok": ok,
        "label": "PTT_META_TRACKING_ENABLED default off in gate env",
        "actual": actual,
        "expected_off": expect_off,
    }


def _check_pg_meta_conversion_ddl() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_PG", "0"):
        return {"id": "B9-G03", "ok": True, "label": "PG meta_conversion_rules DDL (skipped)", "skipped": True}
    try:
        from ptt_crm.pg_schema import pg_meta_conversion_rules_ready

        ok = pg_meta_conversion_rules_ready()
    except Exception as exc:
        ok = False
        err = str(exc)
    else:
        err = None
    return {
        "id": "B9-G03",
        "ok": ok,
        "label": "PG meta_conversion_rules table ready",
        "error": err,
        "hint": "./scripts/apply_pg_ddl_v5_meta_conversion.sh",
    }


def _run_conversion_rules_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_conversion_rules",
            "tests.test_conversion_sync",
            "-v",
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B9-G04",
        "ok": ok,
        "label": "unittest conversion_rules + conversion_sync",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_capi_tracking_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_capi_dispatch",
            "tests.test_tracking_health",
            "tests.test_insights_archive",
            "tests.test_meta_alerts",
            "tests.test_b9_tracking_soak_evidence",
            "-v",
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B9-G05",
        "ok": ok,
        "label": "unittest capi_dispatch + tracking_health + archive + alerts",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_build() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_BUILD", "0"):
        return {"id": "B9-G06", "ok": True, "label": "Nest build (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(api), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B9-G06",
        "ok": ok,
        "label": "Nest build (ptt-crm-api)",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_jest_b9() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_JEST", "0"):
        return {"id": "B9-G07", "ok": True, "label": "Nest jest B9 meta-tracking (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    unit = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=meta-tracking|launch-qa-meta", "--silent"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    e2e = subprocess.run(
        ["npm", "run", "test:e2e", "--", "--testPathPattern=meta-tracking-b9", "--silent"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    ok = unit.returncode == 0 and e2e.returncode == 0
    return {
        "id": "B9-G07",
        "ok": ok,
        "label": "Nest jest + e2e B9 meta-tracking",
        "unit_returncode": unit.returncode,
        "e2e_returncode": e2e.returncode,
        "tail": (unit.stdout or unit.stderr or e2e.stdout or e2e.stderr)[-800:],
    }


def _run_ops_web_build() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_BUILD", "0"):
        return {"id": "B9-G08", "ok": True, "label": "ops-web build (skipped)", "skipped": True}
    ops = ROOT / "services/ops-web"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(ops), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B9-G08",
        "ok": ok,
        "label": "ops-web build",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_b9_tracking_qa_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_b9_tracking_qa", "-v"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B9-G09",
        "ok": ok,
        "label": "unittest tests.test_b9_tracking_qa",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_portal_regression() -> dict[str, Any]:
    portal_qa = ROOT / "tests/test_b8_portal_qa.py"
    if not portal_qa.is_file():
        portal = ROOT / "services/portal-web"
        if _truthy("WAVE_B9_SKIP_BUILD", "0"):
            return {
                "id": "B9-G10",
                "ok": True,
                "label": "Portal regression (B8 QA absent, skipped)",
                "skipped": True,
                "hint": "Merge B8 for test_b8_portal_qa.py",
            }
        proc = subprocess.run(["npm", "run", "build"], cwd=str(portal), capture_output=True, text=True)
        ok = proc.returncode == 0
        return {
            "id": "B9-G10",
            "ok": ok,
            "label": "portal-web build (B8 QA absent)",
            "returncode": proc.returncode,
            "tail": (proc.stdout or proc.stderr)[-400:],
        }
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_b8_portal_qa", "-v"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B9-G10",
        "ok": ok,
        "label": "Portal B8 static regression (test_b8_portal_qa)",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_wave_b8_gate() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_B8_GATE", "0"):
        return {"id": "B9-G11", "ok": True, "label": "Wave B8 regression gate (skipped)", "skipped": True}
    b8 = ROOT / "ptt_crm/wave_b8_gates.py"
    if not b8.is_file():
        return {
            "id": "B9-G11",
            "ok": True,
            "label": "Wave B8 regression gate (module absent — merge B8 branch)",
            "skipped": True,
            "hint": "feat/meta-b8-enterprise-hub-alerts",
        }
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.wave_b8_gates"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "WAVE_B8_SKIP_BUILD": "1",
            "WAVE_B8_SKIP_JEST": "1",
            "WAVE_B8_SKIP_E2E": "1",
            "WAVE_B8_SKIP_B7_GATE": "1",
            "WAVE_B8_SKIP_HORIZON1": "1",
        },
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B9-G11",
        "ok": ok,
        "label": "Wave B8 regression gate",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def _run_horizon1_gate() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_HORIZON1", "0"):
        return {"id": "B9-G12", "ok": True, "label": "Horizon 1 meta regression (skipped)", "skipped": True}
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.horizon1_meta_ads_gates"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "HORIZON1_SKIP_NEST_SMOKE": os.environ.get("HORIZON1_SKIP_NEST_SMOKE", "1"),
            "HORIZON1_SKIP_SOAK": os.environ.get("HORIZON1_SKIP_SOAK", "1"),
        },
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B9-G12",
        "ok": ok,
        "label": "Horizon 1 meta ads gates",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def _run_b9_soak_evaluate() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_SOAK", "1"):
        return {"id": "B9-G13", "ok": True, "label": "B9 tracking soak evaluate (skipped)", "skipped": True}
    try:
        from ptt_crm.b9_tracking_soak_evidence import evaluate_soak_gate

        result = evaluate_soak_gate()
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    ok = bool(result.get("ok"))
    return {
        "id": "B9-G13",
        "ok": ok,
        "label": "B9 tracking pilot soak (30d)",
        "result": result,
        "hint": "./scripts/b9_tracking_soak_record.sh daily during pilot",
    }


def _run_playwright_meta_tracking() -> dict[str, Any]:
    if _truthy("WAVE_B9_SKIP_E2E", "1"):
        return {"id": "B9-G14", "ok": True, "label": "Playwright E2E-M4 meta tracking (skipped)", "skipped": True}
    script = ROOT / "scripts/playwright_ops_meta_tracking_e2e.sh"
    proc = subprocess.run(["bash", str(script)], cwd=str(ROOT), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B9-G14",
        "ok": ok,
        "label": "Playwright ops /meta/tracking E2E-M4",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
        "hint": "Start Nest + ops-web with PTT_META_TRACKING_ENABLED=1; set WAVE_B9_SKIP_E2E=0",
    }


def run_wave_b9_gates() -> dict[str, Any]:
    checks = [
        _check_b9_modules(),
        _check_tracking_flag_default(),
        _check_pg_meta_conversion_ddl(),
        _run_conversion_rules_tests(),
        _run_capi_tracking_tests(),
        _run_nest_build(),
        _run_nest_jest_b9(),
        _run_ops_web_build(),
        _run_b9_tracking_qa_tests(),
        _run_portal_regression(),
        _run_wave_b8_gate(),
        _run_horizon1_gate(),
        _run_b9_soak_evaluate(),
        _run_playwright_meta_tracking(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"wave": "b9", "ok": ok, "generated_at": _now_iso(), "checks": checks}
    out = _artifacts_dir() / "wave-b9-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wave": "b9", "ok": ok}, ensure_ascii=False))
    if not ok:
        for c in checks:
            if not c.get("ok"):
                print(f"FAIL {c.get('id')} {c.get('label')}", file=sys.stderr)
        sys.exit(1)
    return report


if __name__ == "__main__":
    run_wave_b9_gates()
