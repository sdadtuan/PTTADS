"""EM-5 Email Marketing prod pilot gate pack (Gate A)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PHASE_REPORTS: tuple[tuple[str, str], ...] = (
    ("em-0", "phase0-email-hub-kickoff-report.json"),
    ("em-1", "phase1-email-ops-report.json"),
    ("em-2", "phase2-email-send-mvp-report.json"),
    ("em-3", "phase3-email-enterprise-report.json"),
    ("em-4", "phase4-email-portal-report.json"),
)

WAVE_GATE_REPORTS: tuple[tuple[str, str], ...] = (
    ("em-6", "phase6-email-send-platform-report.json"),
    ("em-7", "phase7-email-wave2-report.json"),
    ("em-8", "phase8-email-wave3-report.json"),
    ("em-8b", "phase8b-email-wave3b-report.json"),
)


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _run_pytest_email() -> dict[str, Any]:
    python = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    py_cmd = [python, "-m", "pytest", "tests/test_email_mkt_phase5_gates.py", "-q", "--tb=no"]
    py_proc = subprocess.run(py_cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
    nest_cwd = ROOT / "services" / "ptt-crm-api"
    nest_proc = subprocess.run(
        ["npm", "test", "--", "email-marketing", "portal-email"],
        cwd=str(nest_cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    ok = py_proc.returncode == 0 and nest_proc.returncode == 0
    tail = (
        "pytest:\n"
        + ((py_proc.stdout or "") + (py_proc.stderr or ""))[-1500:]
        + "\nnest:\n"
        + ((nest_proc.stdout or "") + (nest_proc.stderr or ""))[-1500:]
    )
    return {
        "id": "EM5-G01",
        "ok": ok,
        "label": "Email tests (pytest + Nest jest)",
        "pytest_returncode": py_proc.returncode,
        "nest_returncode": nest_proc.returncode,
        "output_tail": tail,
    }


def _check_prior_phase_reports() -> dict[str, Any]:
    skip = os.environ.get("EM5_SKIP_PRIOR_REPORTS", "0") == "1"
    artifacts = _artifacts_dir()
    missing: list[str] = []
    failed: list[str] = []
    found: list[str] = []
    for phase, name in PHASE_REPORTS:
        path = artifacts / name
        if not path.is_file():
            missing.append(name)
            continue
        found.append(name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("ok"):
                failed.append(name)
        except json.JSONDecodeError:
            failed.append(name)
    ok = skip or (not missing and not failed)
    return {
        "id": "EM5-G02",
        "ok": ok,
        "label": "Prior EM-0..EM-4 gate reports",
        "skipped": skip,
        "found": found,
        "missing": missing,
        "failed": failed,
        "artifacts_dir": str(artifacts),
    }


def _check_wave_gate_reports() -> dict[str, Any]:
    include = os.environ.get("EM5_INCLUDE_WAVE_GATES", "0") == "1"
    skip = (not include) or os.environ.get("EM5_SKIP_WAVE_REPORTS", "0") == "1"
    artifacts = _artifacts_dir()
    missing: list[str] = []
    failed: list[str] = []
    found: list[str] = []
    for phase, name in WAVE_GATE_REPORTS:
        path = artifacts / name
        if not path.is_file():
            missing.append(name)
            continue
        found.append(name)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not data.get("ok"):
                failed.append(name)
        except json.JSONDecodeError:
            failed.append(name)
    ok = skip or (not missing and not failed)
    return {
        "id": "EM5-G08",
        "ok": ok,
        "label": "Wave 1–3b gate reports (EM-6..EM-8b)",
        "skipped": skip,
        "found": found,
        "missing": missing,
        "failed": failed,
        "artifacts_dir": str(artifacts),
    }


def _check_feature_flags() -> dict[str, Any]:
    expected = {
        "PTT_EMAIL_ENABLED": os.environ.get("EM5_EXPECT_EMAIL_ENABLED", "1") == "1",
        "PTT_EMAIL_SEND_ENABLED": os.environ.get("EM5_EXPECT_SEND_ENABLED", "1") == "1",
        "PTT_EMAIL_JOURNEYS_ENABLED": os.environ.get("EM5_EXPECT_JOURNEYS_ENABLED", "0") == "1",
        "PTT_EMAIL_PORTAL_ENABLED": os.environ.get("EM5_EXPECT_PORTAL_ENABLED", "0") == "1",
    }
    actual = {
        "PTT_EMAIL_ENABLED": _flag("PTT_EMAIL_ENABLED"),
        "PTT_EMAIL_SEND_ENABLED": _flag("PTT_EMAIL_SEND_ENABLED"),
        "PTT_EMAIL_JOURNEYS_ENABLED": _flag("PTT_EMAIL_JOURNEYS_ENABLED", "0"),
        "PTT_EMAIL_PORTAL_ENABLED": _flag("PTT_EMAIL_PORTAL_ENABLED", "0"),
    }
    if os.environ.get("EM5_EXPECT_ESP_DRY_RUN") is not None:
        expected["PTT_EMAIL_ESP_DRY_RUN"] = os.environ.get("EM5_EXPECT_ESP_DRY_RUN", "1") == "1"
        from ptt_email.config import email_esp_dry_run

        actual["PTT_EMAIL_ESP_DRY_RUN"] = email_esp_dry_run()
    ok = actual == expected
    return {
        "id": "EM5-G03",
        "ok": ok,
        "label": "Email feature flags",
        "actual": actual,
        "expected": expected,
    }


def _nest_email_smoke() -> dict[str, Any]:
    skip = os.environ.get("EM5_SKIP_NEST_SMOKE", "0") == "1"
    if skip:
        return {"id": "EM5-G04", "ok": True, "label": "Nest email hub smoke", "skipped": True}
    base = (os.environ.get("OPS_E2E_API_URL") or os.environ.get("PTT_API_URL") or "http://127.0.0.1:3000").rstrip(
        "/"
    )
    try:
        health = urllib.request.urlopen(f"{base}/health", timeout=5)
        health_ok = health.status == 200
    except (urllib.error.URLError, TimeoutError) as exc:
        return {
            "id": "EM5-G04",
            "ok": False,
            "label": "Nest email hub smoke",
            "error": str(exc),
            "base_url": base,
        }
    hub_ok = False
    token = ""
    try:
        login_body = json.dumps({"email": "staff@demo.local", "password": "demo123"}).encode()
        req = urllib.request.Request(
            f"{base}/api/v1/staff/auth/login",
            data=login_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            token = str(data.get("access_token") or "")
        if token:
            hub_req = urllib.request.Request(
                f"{base}/api/v1/email/hub?days=7",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(hub_req, timeout=10) as resp:
                hub = json.loads(resp.read().decode())
                hub_ok = hub.get("ok") is True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        hub_ok = False
    ok = health_ok and (hub_ok or os.environ.get("PTT_CRM_API_AUTH_DISABLED") == "1")
    return {
        "id": "EM5-G04",
        "ok": ok,
        "label": "Nest email hub smoke",
        "health_ok": health_ok,
        "hub_ok": hub_ok,
        "base_url": base,
    }


def _build_frontends() -> dict[str, Any]:
    skip = os.environ.get("EM5_SKIP_BUILD", "0") == "1"
    if skip:
        return {"id": "EM5-G05", "ok": True, "label": "ops-web + portal-web build", "skipped": True}
    env = {**os.environ}
    steps: list[dict[str, Any]] = []
    ok = True
    for name, cwd in (
        ("ops-web", ROOT / "services" / "ops-web"),
        ("portal-web", ROOT / "services" / "portal-web"),
    ):
        proc = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        step_ok = proc.returncode == 0
        ok = ok and step_ok
        steps.append(
            {
                "app": name,
                "ok": step_ok,
                "returncode": proc.returncode,
                "tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
            }
        )
    return {"id": "EM5-G05", "ok": ok, "label": "ops-web + portal-web build", "steps": steps}


def _check_soak() -> dict[str, Any]:
    from ptt_crm.phase5_email_soak_evidence import evaluate_soak_gate

    skip = os.environ.get("EM5_SKIP_SOAK", "1") == "1"
    if skip:
        return {"id": "EM5-G06", "ok": True, "label": "EM-5 email soak", "skipped": True}
    result = evaluate_soak_gate()
    result["id"] = "EM5-G06"
    return result


def _check_signoff_template() -> dict[str, Any]:
    template = ROOT / "docs" / "evidence" / "em5-email-pilot-signoff.template.json"
    signoff = _artifacts_dir() / "em5-email-pilot-signoff.json"
    has_template = template.is_file()
    has_signoff = signoff.is_file()
    require_signoff = os.environ.get("EM5_REQUIRE_SIGNOFF", "0") == "1"
    ok = has_template and (has_signoff or not require_signoff)
    return {
        "id": "EM5-G07",
        "ok": ok,
        "label": "Pilot sign-off artifact",
        "template": str(template),
        "signoff_path": str(signoff),
        "signoff_present": has_signoff,
        "require_signoff": require_signoff,
    }


def run_gates(*, refresh_prior: bool = False) -> dict[str, Any]:
    if refresh_prior or os.environ.get("EM5_REFRESH_PRIOR_GATES", "0") == "1":
        scripts = [
            "phase0_email_hub_kickoff_gate.sh",
            "phase1_email_ops_gate.sh",
            "phase2_email_send_mvp_gate.sh",
            "phase3_email_enterprise_gate.sh",
            "phase4_email_portal_gate.sh",
        ]
        if os.environ.get("EM5_INCLUDE_WAVE_GATES", "0") == "1":
            scripts.extend(
                [
                    "phase6_email_send_platform_gate.sh",
                    "phase7_email_wave2_gate.sh",
                    "phase8_email_wave3_gate.sh",
                    "phase8b_email_wave3b_gate.sh",
                ]
            )
        for script in scripts:
            path = ROOT / "scripts" / script
            if path.is_file():
                subprocess.run(["bash", str(path)], cwd=str(ROOT), check=False)

    checks = [
        _run_pytest_email(),
        _check_prior_phase_reports(),
        _check_wave_gate_reports(),
        _check_feature_flags(),
        _nest_email_smoke(),
        _build_frontends(),
        _check_soak(),
        _check_signoff_template(),
    ]
    ok = all(c.get("ok") for c in checks)
    report = {
        "phase": "em-5",
        "component": "email_prod_pilot_gate_a",
        "ok": ok,
        "generated_at": _now_iso(),
        "checks": checks,
        "env_hint": "deploy/env.em5-prod.example",
        "runbook": "docs/runbooks/email-marketing-prod-pilot-checklist.md",
    }
    out = _artifacts_dir() / "phase5-email-pilot-gate-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    refresh = "--refresh-prior" in sys.argv
    report = run_gates(refresh_prior=refresh)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
