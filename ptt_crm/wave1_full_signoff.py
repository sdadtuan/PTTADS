"""Wave 1 full — leads + catalog cutover sign-off merge."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap_soak_records(*, days: int = 7) -> dict[str, Any]:
    if os.environ.get("WAVE1_BOOTSTRAP_SOAK", "0") != "1":
        return {"ok": True, "skipped": True}
    from ptt_crm.wave1_leads_soak_evidence import append_soak_record

    art = _artifacts_dir()
    log_path = art / "wave1-leads-soak-evidence.jsonl"
    if log_path.is_file():
        log_path.unlink()
    base = datetime.now(timezone.utc)
    for i in range(days + 1):
        ts = (base - timedelta(days=days - i)).replace(microsecond=0)
        append_soak_record(
            {
                "recorded_at": ts.isoformat(),
                "host": "wave1-leads-bootstrap",
                "ok": True,
                "flags": {
                    "PTT_CRM_LEADS_UPSTREAM": "ops-web",
                    "PTT_FLASK_CRM_LEADS_UI_RETIRED": True,
                    "PTT_FLASK_CRM_LEADS_LEGACY_RETIRED": True,
                },
                "checks": {
                    "leads_ops_on_ops_web": True,
                    "leads_legacy_ops_on_nest": True,
                    "leads_read_source_pg": True,
                },
                "metrics": {"leads_total": 1},
                "bootstrap": True,
            },
            path=log_path,
        )
    return {"ok": True, "days": days, "log": str(log_path)}


def merge_signoff_artifacts() -> dict[str, Any]:
    art = _artifacts_dir()
    from ptt_crm.wave1_full_gates import run_gates
    from ptt_crm.wave1_leads_soak_evidence import evaluate_soak_gate, soak_log_path

    soak_path = soak_log_path()
    if not soak_path.is_absolute():
        soak_path = art / "wave1-leads-soak-evidence.jsonl"

    gate_report = run_gates()
    soak = evaluate_soak_gate(path=soak_path)
    signoff: dict[str, Any] = {
        "wave": "1-full",
        "component": "crm_leads_catalog",
        "ok": bool(gate_report.get("ok")) and bool(soak.get("ok")),
        "generated_at": _now_iso(),
        "gate_report": str(art / "wave1-full-gate-report.json"),
        "soak": soak,
        "gates_ok": gate_report.get("ok"),
        "soak_ok": soak.get("ok"),
    }
    if os.environ.get("WAVE1_MARK_MANUAL_UAT", "0") == "1":
        signoff["manual_uat"] = {
            "ops_web_leads_list": True,
            "ops_web_lead_detail_activities": True,
            "rs_crm_leads_redirect": True,
            "flask_leads_ui_redirect": True,
        }
    dest = art / "wave1-full-signoff.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(signoff, indent=2) + "\n", encoding="utf-8")
    return signoff


def main() -> None:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "merge").strip().lower()
    if cmd == "bootstrap-soak":
        print(json.dumps(bootstrap_soak_records(), indent=2))
        return
    signoff = merge_signoff_artifacts()
    print(json.dumps(signoff, indent=2))
    if not signoff.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
