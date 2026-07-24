"""Wave B8 — Meta Enterprise measurement parity gates."""
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


def _check_b8_modules() -> dict[str, Any]:
    files = [
        ROOT / "docs/specs/2026-07-24-postgresql-ddl-v4-meta-enterprise.sql",
        ROOT / "scripts/apply_pg_ddl_v4_meta_enterprise.sh",
        ROOT / "deploy/env.meta-enterprise-b8.example",
        ROOT / "ptt_meta/alerts.py",
        ROOT / "ptt_meta/hub_map_suggest.py",
        ROOT / "ptt_jobs/handlers/meta_alerts_eval.py",
        ROOT / "tests/test_meta_alerts.py",
        ROOT / "services/ptt-crm-api/src/meta-alerts/meta-alerts.module.ts",
        ROOT / "services/ptt-crm-api/src/meta-alerts/meta-alerts.controller.ts",
        ROOT / "services/ptt-crm-api/src/meta-attribution.util.ts",
        ROOT / "services/ops-web/src/lib/meta/api.ts",
        ROOT / "services/ops-web/src/lib/meta/flags.ts",
        ROOT / "services/ops-web/src/components/meta/MetaHubTabs.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaCampaignTable.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaAlertsTable.tsx",
        ROOT / "services/ops-web/src/components/meta/MetaSyncStatusChip.tsx",
        ROOT / "services/portal-web/src/components/PortalAttributionFooter.tsx",
        ROOT / "services/portal-web/src/components/PerformanceTable.tsx",
        ROOT / "services/portal-web/src/components/PerformancePanel.tsx",
        ROOT / "services/portal-web/e2e/portal-b8.spec.ts",
        ROOT / "services/ops-web/e2e/meta-hub.spec.ts",
        ROOT / "services/ops-web/playwright.config.ts",
        ROOT / "services/ptt-crm-api/test/facebook-hub-b8.e2e-spec.ts",
        ROOT / "services/ptt-crm-api/src/meta-attribution.util.spec.ts",
        ROOT / "tests/test_b8_portal_qa.py",
        ROOT / "scripts/wave_b8_smoke.sh",
        ROOT / "scripts/playwright_portal_b8_e2e.sh",
        ROOT / "scripts/playwright_ops_meta_hub_e2e.sh",
        ROOT / "scripts/wave_b8_gate.sh",
    ]
    missing = [str(p.relative_to(ROOT)) for p in files if not p.is_file()]
    return {"id": "B8-G01", "ok": not missing, "label": "Wave B8 module files", "missing": missing}


def _check_alerts_flag_default() -> dict[str, Any]:
    actual = _truthy("PTT_META_ALERTS_ENABLED", "0")
    expect_off = not _truthy("WAVE_B8_EXPECT_ALERTS_ENABLED", "0")
    ok = (not actual) if expect_off else True
    return {
        "id": "B8-G02",
        "ok": ok,
        "label": "PTT_META_ALERTS_ENABLED default off",
        "actual": actual,
        "expected_off": expect_off,
    }


def _check_pg_meta_alerts_ddl() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_PG", "0"):
        return {"id": "B8-G03", "ok": True, "label": "PG meta_alerts DDL (skipped)", "skipped": True}
    try:
        from ptt_crm.pg_schema import pg_meta_alerts_ready

        ok = pg_meta_alerts_ready()
    except Exception as exc:
        ok = False
        err = str(exc)
    else:
        err = None
    return {
        "id": "B8-G03",
        "ok": ok,
        "label": "PG meta_alerts table ready",
        "error": err,
        "hint": "./scripts/apply_pg_ddl_v4_meta_enterprise.sh",
    }


def _run_meta_alerts_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_meta_alerts", "-v"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B8-G04",
        "ok": ok,
        "label": "unittest tests.test_meta_alerts",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_build() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_BUILD", "0"):
        return {"id": "B8-G05", "ok": True, "label": "Nest build (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(api), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B8-G05",
        "ok": ok,
        "label": "Nest build (ptt-crm-api)",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_b7_gate() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_B7_GATE", "0"):
        return {"id": "B8-G06", "ok": True, "label": "Wave B7 regression gate (skipped)", "skipped": True}
    proc = subprocess.run(
        [sys.executable, "-m", "ptt_crm.wave_b7_gates"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "WAVE_B7_SKIP_JEST": "1",
            "WAVE_B7_SKIP_BUILD": "1",
            "WAVE_B7_SKIP_B6_GATE": "1",
        },
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B8-G06",
        "ok": ok,
        "label": "Wave B7 regression gate",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def _run_portal_qa_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_b8_portal_qa", "-v"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    return {
        "id": "B8-G07",
        "ok": ok,
        "label": "unittest tests.test_b8_portal_qa",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_nest_jest_b8() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_JEST", "0"):
        return {"id": "B8-G08", "ok": True, "label": "Nest jest B8 attribution (skipped)", "skipped": True}
    api = ROOT / "services/ptt-crm-api"
    unit = subprocess.run(
        ["npm", "test", "--", "--testPathPattern=meta-attribution", "--silent"],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    e2e = subprocess.run(
        [
            "npm",
            "run",
            "test:e2e",
            "--",
            "--testPathPattern=performance|facebook-hub-b8",
            "--silent",
        ],
        cwd=str(api),
        capture_output=True,
        text=True,
    )
    ok = unit.returncode == 0 and e2e.returncode == 0
    return {
        "id": "B8-G08",
        "ok": ok,
        "label": "Nest jest B8 (meta-attribution + performance + hub e2e)",
        "unit_returncode": unit.returncode,
        "e2e_returncode": e2e.returncode,
        "tail": ((unit.stdout or unit.stderr) + (e2e.stdout or e2e.stderr))[-800:],
    }


def _run_ops_web_build() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_BUILD", "0"):
        return {"id": "B8-G09", "ok": True, "label": "ops-web build (skipped)", "skipped": True}
    ops = ROOT / "services/ops-web"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(ops), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B8-G09",
        "ok": ok,
        "label": "ops-web build",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_portal_web_build() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_BUILD", "0"):
        return {"id": "B8-G10", "ok": True, "label": "portal-web build (skipped)", "skipped": True}
    portal = ROOT / "services/portal-web"
    proc = subprocess.run(["npm", "run", "build"], cwd=str(portal), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B8-G10",
        "ok": ok,
        "label": "portal-web build",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
    }


def _run_playwright_portal_b8() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_E2E", "1"):
        return {"id": "B8-G11", "ok": True, "label": "Playwright portal B8 (skipped)", "skipped": True}
    script = ROOT / "scripts/playwright_portal_b8_e2e.sh"
    proc = subprocess.run(["bash", str(script)], cwd=str(ROOT), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B8-G11",
        "ok": ok,
        "label": "Playwright portal B8 E2E",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
        "hint": "Start Nest + portal + PG seed; set WAVE_B8_SKIP_E2E=0",
    }


def _run_playwright_ops_meta() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_E2E", "1"):
        return {"id": "B8-G12", "ok": True, "label": "Playwright ops meta hub (skipped)", "skipped": True}
    script = ROOT / "scripts/playwright_ops_meta_hub_e2e.sh"
    proc = subprocess.run(["bash", str(script)], cwd=str(ROOT), capture_output=True, text=True)
    ok = proc.returncode == 0
    return {
        "id": "B8-G12",
        "ok": ok,
        "label": "Playwright ops meta hub E2E",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-800:],
        "hint": "Start Nest + ops-web; set WAVE_B8_SKIP_E2E=0",
    }


def _run_horizon1_gate() -> dict[str, Any]:
    if _truthy("WAVE_B8_SKIP_HORIZON1", "0"):
        return {"id": "B8-G13", "ok": True, "label": "Horizon 1 meta regression (skipped)", "skipped": True}
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
        "id": "B8-G13",
        "ok": ok,
        "label": "Horizon 1 meta ads gates",
        "returncode": proc.returncode,
        "tail": (proc.stdout or proc.stderr)[-400:],
    }


def run_wave_b8_gates() -> dict[str, Any]:
    checks = [
        _check_b8_modules(),
        _check_alerts_flag_default(),
        _check_pg_meta_alerts_ddl(),
        _run_meta_alerts_tests(),
        _run_nest_build(),
        _run_b7_gate(),
        _run_portal_qa_tests(),
        _run_nest_jest_b8(),
        _run_ops_web_build(),
        _run_portal_web_build(),
        _run_playwright_portal_b8(),
        _run_playwright_ops_meta(),
        _run_horizon1_gate(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {"wave": "b8", "ok": ok, "generated_at": _now_iso(), "checks": checks}
    out = _artifacts_dir() / "wave-b8-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wave": "b8", "ok": ok}, ensure_ascii=False))
    if not ok:
        for c in checks:
            if not c.get("ok"):
                print(f"FAIL {c.get('id')} {c.get('label')}", file=sys.stderr)
        sys.exit(1)
    return report


if __name__ == "__main__":
    run_wave_b8_gates()
