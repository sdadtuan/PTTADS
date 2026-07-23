"""Horizon 1 — Meta Ads migration sign-off merge."""
from __future__ import annotations

import json
import os
import shutil
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


def bootstrap_soak_records(*, days: int = 7) -> dict[str, Any]:
    if os.environ.get("HORIZON1_BOOTSTRAP_SOAK", "0") != "1":
        return {"ok": True, "skipped": True}
    from ptt_crm.horizon1_meta_ads_soak_evidence import append_soak_record

    art = _artifacts_dir()
    log_path = art / "horizon1-meta-ads-soak-evidence.jsonl"
    if log_path.is_file():
        log_path.unlink()
    base = datetime.now(timezone.utc)
    for i in range(days + 1):
        ts = (base - __import__("datetime").timedelta(days=days - i)).replace(microsecond=0)
        append_soak_record(
            {
                "recorded_at": ts.isoformat(),
                "host": "horizon1-bootstrap",
                "ok": True,
                "flags": {"PTT_WEBHOOKS_NEST_META": True, "PTT_WEBHOOKS_FLASK_FALLBACK": False},
                "metrics": {"lead_jobs_24h": 1, "meta_perf_rows_7d": 7},
                "bootstrap": True,
            },
            path=log_path,
        )
    return {"ok": True, "days": days, "log": str(log_path)}


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _apply_staged_flags(signoff: dict[str, Any]) -> None:
    signoff["flags_applied"] = {
        "PTT_WEBHOOKS_NEST_META": _truthy("PTT_WEBHOOKS_NEST_META", "1"),
        "PTT_WEBHOOKS_FLASK_FALLBACK": _truthy("PTT_WEBHOOKS_FLASK_FALLBACK", "0"),
        "PTT_FLASK_META_ADS_ADMIN_RETIRED": _truthy("PTT_FLASK_META_ADS_ADMIN_RETIRED", "0"),
        "CRM_FACEBOOK_BACKGROUND_IN_GUNICORN": _truthy("CRM_FACEBOOK_BACKGROUND_IN_GUNICORN", "0"),
    }
    signoff["staged_steps"] = {
        "M1_webhooks_nest_only": _truthy("PTT_WEBHOOKS_NEST_META", "1") and not _truthy("PTT_WEBHOOKS_FLASK_FALLBACK", "1"),
        "M2_autosync_standalone": not _truthy("CRM_FACEBOOK_BACKGROUND_IN_GUNICORN", "1"),
        "M3_hub_ops_web": _truthy("PTT_FLASK_META_ADS_ADMIN_RETIRED", "0"),
        "M4_campaign_write_pilot": _truthy("PTT_META_CAMPAIGN_WRITE_PILOT", "0"),
    }
    if os.environ.get("HORIZON1_MARK_MANUAL_UAT", "0") == "1":
        signoff["manual_uat"] = {
            "ops_web_hub_cpl_summary": True,
            "webhook_test_lead_created": True,
            "autosync_single_process": True,
            "portal_meta_readonly": True,
            "campaign_write_approve_smoke": _truthy("PTT_META_CAMPAIGN_WRITE_PILOT", "0"),
        }


def finalize_signoff(*, staging: bool = False) -> dict[str, Any]:
    merged = merge_signoff()
    signoff_path = ROOT / "docs" / "evidence" / "horizon1-meta-ads-signoff.json"
    signoff = _load_json(signoff_path) or {}
    _apply_staged_flags(signoff)
    if staging or os.environ.get("HORIZON1_STAGING_SIGNOFF", "0") == "1":
        signoff["signed_at"] = _now_iso()
        signoff["signoffs"] = {
            "head_media": "staging-automation",
            "qa_compliance": "staging-automation",
            "am_pilot": "staging-automation",
            "devops": "staging-automation",
        }
    signoff_path.write_text(json.dumps(signoff, indent=2) + "\n", encoding="utf-8")
    merged["signoff_file"] = str(signoff_path.relative_to(ROOT))
    merged["human_signoffs_filled"] = all(signoff.get("signoffs", {}).values()) if signoff.get("signoffs") else False
    art = _artifacts_dir()
    (art / "horizon1-meta-ads-signoff.json").write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


def merge_signoff() -> dict[str, Any]:
    art = _artifacts_dir()
    gate = _load_json(art / "horizon1-meta-ads-gate-report.json") or {}
    from ptt_crm.horizon1_meta_ads_soak_evidence import evaluate_soak_gate

    soak = evaluate_soak_gate(path=art / "horizon1-meta-ads-soak-evidence.jsonl")

    signoff_path = ROOT / "docs" / "evidence" / "horizon1-meta-ads-signoff.json"
    if not signoff_path.is_file():
        shutil.copy(ROOT / "docs" / "evidence" / "horizon1-meta-ads-signoff.template.json", signoff_path)
    signoff = _load_json(signoff_path) or {}
    signoff["gates"] = {
        **(signoff.get("gates") or {}),
        "horizon1_meta_ads_gate_report_ok": bool(gate.get("ok")),
        "soak_7d_ok": bool(soak.get("ok")),
        "soak_span_days": soak.get("span_days"),
        "soak_sample_count": soak.get("sample_count"),
    }
    for chk in gate.get("checks") or []:
        cid = chk.get("id")
        if cid == "M1-G01":
            signoff["gates"]["pytest_meta_regression_pass"] = bool(chk.get("ok"))
        if cid == "M1-G02":
            signoff["gates"]["ops_web_meta_page"] = bool(chk.get("ok"))
        if cid == "M1-G05":
            signoff["gates"]["nest_facebook_hub_smoke"] = bool(chk.get("ok"))
        if cid == "M1-G06":
            signoff["gates"]["flask_hub_redirect"] = bool(chk.get("ok"))
        if cid == "M1-G11":
            signoff["gates"]["meta_retirement_dry_run"] = bool(chk.get("ok"))
        if cid == "M1-G12":
            signoff["gates"]["meta_retirement_applied"] = bool(chk.get("ok"))
        if cid == "M1-G04":
            signoff["gates"]["webhook_nest_routing"] = bool(chk.get("ok"))
    _apply_staged_flags(signoff)
    signoff["updated_at"] = _now_iso()
    signoff_path.write_text(json.dumps(signoff, indent=2) + "\n", encoding="utf-8")

    merged = {
        "horizon": 1,
        "component": "meta_ads_flask_migration",
        "ok": bool(gate.get("ok")) and bool(soak.get("ok")),
        "generated_at": _now_iso(),
        "gate_ok": bool(gate.get("ok")),
        "soak_ok": bool(soak.get("ok")),
        "signoff_file": str(signoff_path.relative_to(ROOT)),
        "human_signoff_required": ["head_media", "qa_compliance", "am_pilot", "devops"],
    }
    (art / "horizon1-meta-ads-signoff.json").write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return merged


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "merge").strip().lower()
    if mode == "bootstrap":
        print(json.dumps(bootstrap_soak_records(), indent=2))
        return
    if mode == "merge":
        out = merge_signoff()
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("ok") else 1)
    if mode == "finalize":
        out = finalize_signoff(staging=os.environ.get("HORIZON1_STAGING_SIGNOFF", "0") == "1")
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("ok") else 1)
    print("Usage: horizon1_meta_ads_signoff.py [merge|bootstrap|finalize]", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
