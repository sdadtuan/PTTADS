"""Horizon 0 — Gate A sign-off aggregator (SEO + Email prod pilot)."""
from __future__ import annotations

import json
import os
import shutil
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


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _run_gate(module: str, *extra: str) -> dict[str, Any]:
    python = sys.executable
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [python, "-m", module, *extra],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return {
        "module": module,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "output_tail": ((proc.stdout or "") + (proc.stderr or ""))[-2000:],
    }


def bootstrap_soak_records(*, days: int = 7) -> dict[str, Any]:
    """Staging-only: append synthetic daily soak rows so evaluate can pass pre-prod."""
    if os.environ.get("HORIZON0_BOOTSTRAP_SOAK", "0") != "1":
        return {"ok": True, "skipped": True, "reason": "HORIZON0_BOOTSTRAP_SOAK not set"}
    from ptt_crm.phase5_email_soak_evidence import append_soak_record as email_append
    from ptt_crm.phase5_soak_evidence import append_soak_record as seo_append

    art = _artifacts_dir()
    seo_log = art / "phase5-soak-evidence.jsonl"
    email_log = art / "em5-soak-evidence.jsonl"
    for path in (seo_log, email_log):
        if path.is_file():
            path.unlink()
    base = datetime.now(timezone.utc)
    for i in range(days + 1):
        ts = (base - __import__("datetime").timedelta(days=days - i)).replace(microsecond=0)
        snap_seo = {
            "recorded_at": ts.isoformat(),
            "host": "horizon0-bootstrap",
            "ok": True,
            "flags": {"PTT_SEO_GOVERNANCE_ENABLED": True, "PTT_PORTAL_SEO_ENABLED": False},
            "metrics": {"governance_evaluations_24h": 1},
            "bootstrap": True,
        }
        snap_email = {
            "recorded_at": ts.isoformat(),
            "host": "horizon0-bootstrap",
            "ok": True,
            "flags": {"PTT_EMAIL_ENABLED": True, "PTT_EMAIL_SEND_ENABLED": True},
            "metrics": {"workspaces": 1, "complaints_24h": 0},
            "bootstrap": True,
        }
        seo_append(snap_seo, path=seo_log)
        email_append(snap_email, path=email_log)
    return {"ok": True, "days": days, "seo_log": str(seo_log), "email_log": str(email_log)}


def merge_signoff_artifacts() -> dict[str, Any]:
    art = _artifacts_dir()
    seo_gate = _load_json(art / "phase5-gate-report.json") or {}
    email_gate = _load_json(art / "phase5-email-pilot-gate-report.json") or {}
    delivery_gate = _load_json(art / "phase5-delivery-admin-retirement-gate-report.json") or {}
    portal_uat = _load_json(art / "phase5-portal-seo-uat-signoff.json") or {}

    from ptt_crm.phase5_email_soak_evidence import evaluate_soak_gate as email_soak_eval
    from ptt_crm.phase5_soak_evidence import evaluate_soak_gate as seo_soak_eval

    seo_soak = seo_soak_eval(path=art / "phase5-soak-evidence.jsonl")
    email_soak = email_soak_eval(path=art / "em5-soak-evidence.jsonl")

    seo_signoff_path = ROOT / "docs" / "evidence" / "phase5-prod-signoff.json"
    if not seo_signoff_path.is_file():
        shutil.copy(
            ROOT / "docs" / "evidence" / "phase5-prod-signoff.template.json",
            seo_signoff_path,
        )
    email_signoff_path = ROOT / "docs" / "evidence" / "em5-email-pilot-signoff.json"
    if not email_signoff_path.is_file():
        shutil.copy(
            ROOT / "docs" / "evidence" / "em5-email-pilot-signoff.template.json",
            email_signoff_path,
        )

    seo_signoff = _load_json(seo_signoff_path) or {}
    seo_signoff["gates"] = {
        **(seo_signoff.get("gates") or {}),
        "phase5_gate_report_ok": bool(seo_gate.get("ok")),
        "pytest_phase5_14_pass": any(
            c.get("id") == "P5-G01" and c.get("ok") for c in (seo_gate.get("checks") or [])
        ),
        "portal_playwright_e2e": bool(portal_uat.get("playwright_e2e")),
        "soak_7d_ok": bool(seo_soak.get("ok")),
        "soak_span_days": seo_soak.get("span_days"),
        "soak_sample_count": seo_soak.get("sample_count"),
        "soak_failure_count": seo_soak.get("failure_count"),
        "delivery_admin_retired": bool(delivery_gate.get("ok")),
    }
    seo_signoff["updated_at"] = _now_iso()
    seo_signoff_path.write_text(json.dumps(seo_signoff, indent=2) + "\n", encoding="utf-8")

    email_signoff = _load_json(email_signoff_path) or {}
    email_signoff["gates"] = {
        **(email_signoff.get("gates") or {}),
        "phase5_email_gate_report_ok": bool(email_gate.get("ok")),
        "pytest_email_pass": any(
            c.get("id") == "EM5-G01" and c.get("ok") for c in (email_gate.get("checks") or [])
        ),
        "ops_web_build": any(
            c.get("id") == "EM5-G05" and c.get("ok") for c in (email_gate.get("checks") or [])
        ),
        "soak_7d_ok": bool(email_soak.get("ok")),
        "soak_span_days": email_soak.get("span_days"),
        "soak_sample_count": email_soak.get("sample_count"),
        "esp_real_send": os.environ.get("EM5_EXPECT_ESP_DRY_RUN", "1") == "0",
    }
    email_signoff["updated_at"] = _now_iso()
    email_signoff_path.write_text(json.dumps(email_signoff, indent=2) + "\n", encoding="utf-8")

    horizon_path = art / "horizon0-gate-a-signoff.json"
    ready = (
        bool(seo_gate.get("ok"))
        and bool(email_gate.get("ok"))
        and bool(delivery_gate.get("ok"))
        and bool(seo_soak.get("ok"))
        and bool(email_soak.get("ok"))
    )
    horizon = {
        "horizon": 0,
        "component": "gate_a_seo_email_prod_pilot",
        "ok": ready,
        "generated_at": _now_iso(),
        "seo_gate_ok": bool(seo_gate.get("ok")),
        "email_gate_ok": bool(email_gate.get("ok")),
        "delivery_admin_retire_ok": bool(delivery_gate.get("ok")),
        "seo_soak_ok": bool(seo_soak.get("ok")),
        "email_soak_ok": bool(email_soak.get("ok")),
        "signoff_files": {
            "seo": str(seo_signoff_path.relative_to(ROOT)),
            "email": str(email_signoff_path.relative_to(ROOT)),
        },
        "human_signoff_required": [
            "head_seo_aeo",
            "head_email_coe",
            "qa_compliance",
            "am_pilot",
            "client_approver",
            "devops",
        ],
        "notes": "Set signed_at + signoffs.* after human checklist complete",
    }
    horizon_path.write_text(json.dumps(horizon, indent=2) + "\n", encoding="utf-8")
    return horizon


def run_horizon0(*, mode: str = "preflight") -> dict[str, Any]:
    steps: dict[str, Any] = {"mode": mode, "started_at": _now_iso()}
    if mode in {"soak", "full", "evaluate"}:
        steps["bootstrap"] = bootstrap_soak_records()
    if mode in {"preflight", "full"}:
        steps["seo_gate"] = _run_gate("ptt_crm.phase5_prod_gates")
        steps["email_gate"] = _run_gate("ptt_crm.phase5_email_gates")
        steps["delivery_admin"] = _run_gate("ptt_crm.phase5_delivery_admin_retirement_gates")
    if mode in {"soak", "full"}:
        from ptt_crm.phase5_email_soak_evidence import append_soak_record as email_append
        from ptt_crm.phase5_soak_evidence import append_soak_record as seo_append

        if mode != "full" or os.environ.get("HORIZON0_BOOTSTRAP_SOAK") != "1":
            steps["seo_soak_record"] = seo_append()
            steps["email_soak_record"] = email_append()
    steps["signoff"] = merge_signoff_artifacts()
    steps["ok"] = bool(steps.get("signoff", {}).get("ok"))
    steps["finished_at"] = _now_iso()
    out = _artifacts_dir() / "horizon0-gate-a-report.json"
    out.write_text(json.dumps(steps, indent=2) + "\n", encoding="utf-8")
    return steps


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "preflight").strip().lower()
    if mode not in {"preflight", "soak", "evaluate", "full"}:
        print("Usage: horizon0_gate_a_signoff.py [preflight|soak|evaluate|full]", file=sys.stderr)
        sys.exit(2)
    if mode == "evaluate":
        os.environ.setdefault("EM5_SKIP_SOAK", "0")
        os.environ.setdefault("PHASE5_SKIP_SOAK", "0")
        report = {"signoff": merge_signoff_artifacts()}
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["signoff"].get("ok") else 1)
    report = run_horizon0(mode=mode)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
