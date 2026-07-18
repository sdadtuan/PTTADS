"""Phase 4 prod cutover preflight checks."""
from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifacts_dir() -> Path:
    return Path(os.environ.get("PTT_ARTIFACTS_DIR") or (ROOT / ".local-dev"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def verify_phase3_qa() -> dict[str, Any]:
    path = _artifacts_dir() / "phase3-qa-gate-report.json"
    if not path.is_file():
        return {"ok": False, "error": "phase3-qa-gate-report.json missing"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": bool(data.get("ok")), "path": str(path)}


def verify_phase4_gates() -> dict[str, Any]:
    path = _artifacts_dir() / "phase4-gate-report.json"
    if not path.is_file():
        return {"ok": False, "error": "phase4-gate-report.json missing — run ./scripts/phase4_gate.sh"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": bool(data.get("ok")), "summary": data.get("summary")}


def verify_ddl_and_clickhouse() -> dict[str, Any]:
    from ptt_crm.pg_schema import pg_campaign_writes_ready

    ddl_ok = pg_campaign_writes_ready()
    ch_url = (os.environ.get("CLICKHOUSE_URL") or "").strip()
    return {
        "ok": ddl_ok,
        "pg_campaign_writes_ready": ddl_ok,
        "clickhouse_url_set": bool(ch_url),
    }


def verify_pilot_config() -> dict[str, Any]:
    if os.environ.get("PTT_CUTOVER_SKIP_PILOT", "").strip().lower() in {"1", "true", "yes"}:
        return {"ok": True, "skipped": True, "label": "pilot_config"}
    stub = os.environ.get("PTT_META_CAMPAIGN_WRITE_STUB", "0").strip().lower() in {"1", "true", "yes"}
    pilot = os.environ.get("PTT_META_CAMPAIGN_WRITE_PILOT", "0").strip().lower() in {"1", "true", "yes"}
    clients = (os.environ.get("PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS") or "").strip()
    campaigns = (os.environ.get("PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS") or "").strip()
    mode = (os.environ.get("PTT_FLASK_MONOLITH_MODE") or "readonly").strip().lower()
    issues: list[str] = []
    if os.environ.get("PTT_CUTOVER_ENV", "prod") == "prod" and stub:
        issues.append("meta_stub_should_be_off_in_prod")
    if pilot and (not clients or not campaigns):
        issues.append("pilot_lists_required_when_pilot_enabled")
    if mode not in {"readonly", "retired"}:
        issues.append(f"unexpected_flask_mode:{mode}")
    return {
        "ok": not issues,
        "flask_mode": mode,
        "meta_stub": stub,
        "meta_pilot": pilot,
        "pilot_clients_set": bool(clients),
        "pilot_campaigns_set": bool(campaigns),
        "issues": issues,
    }


def run_preflight() -> dict[str, Any]:
    steps = {
        "phase3_qa": verify_phase3_qa(),
        "phase4_gates": verify_phase4_gates(),
        "ddl_clickhouse": verify_ddl_and_clickhouse(),
        "pilot_config": verify_pilot_config(),
    }
    skip = {"pilot_config"} if steps["pilot_config"].get("skipped") else set()
    required = [k for k in steps if k not in skip]
    all_ok = all(bool(steps[k].get("ok")) for k in required)
    report = {
        "phase": "phase4_prod_cutover_preflight",
        "generated_at": _now_iso(),
        "host": socket.gethostname(),
        "ok": all_ok,
        "steps": steps,
        "summary": {
            "passed": sum(1 for k in required if steps[k].get("ok")),
            "total": len(required),
            "failed": [k for k in required if not steps[k].get("ok")],
        },
    }
    out = _artifacts_dir() / "phase4-prod-cutover-preflight.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main() -> int:
    report = run_preflight()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
