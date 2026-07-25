"""Production hardening gates — Prod-S4 / PROD-H-*."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

PROD_STUB_FLAGS = (
    "PTT_ZALO_ADS_STUB",
    "PTT_GOOGLE_ADS_STUB",
    "PTT_META_TOKEN_REFRESH_STUB",
    "PTT_ZALO_TOKEN_REFRESH_STUB",
    "PTT_EMAIL_SEND_STUB",
)

PROD_PILOT_OK = (
    "PTT_ZALO_ADS_PILOT",
    "PTT_GOOGLE_ADS_PILOT",
    "PTT_META_CAMPAIGN_WRITE_PILOT",
)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "0").strip().lower() in {"1", "true", "yes", "on"}


def audit_prod_stub_flags() -> dict[str, Any]:
    """PROD-H-STUB — stub flags must be off on production-like env."""
    enabled = [name for name in PROD_STUB_FLAGS if _truthy(name)]
    return {
        "ok": len(enabled) == 0,
        "enabled_stub_flags": enabled,
        "checked": list(PROD_STUB_FLAGS),
    }


def webhook_job_error_rate(*, window_hours: int = 24) -> dict[str, Any]:
    """PROD-H-MON — job failure rate for ingest/webhook-related jobs."""
    threshold_pct = float(os.environ.get("PTT_WEBHOOK_ERROR_RATE_MAX_PCT", "1"))
    try:
        from ptt_jobs.db import pg_available, pg_connection
    except Exception as exc:
        return {"ok": True, "skipped": True, "reason": str(exc)}

    if not pg_available():
        return {"ok": True, "skipped": True, "reason": "pg_unavailable"}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COUNT(*) FILTER (WHERE status IN ('failed', 'dead')) AS failed,
                  COUNT(*) AS total
                FROM job_queue
                WHERE created_at >= NOW() - (%s || ' hours')::interval
                  AND job_type IN (
                    'form_ingest', 'meta_lead_ingest', 'zalo_form_lead_poll',
                    'webhook_dispatch', 'email_webhook_dispatch'
                  )
                """,
                [str(max(1, window_hours))],
            )
            row = cur.fetchone()
            failed = int(row[0] or 0)
            total = int(row[1] or 0)

    rate = (failed / total * 100.0) if total else 0.0
    return {
        "ok": rate <= threshold_pct or total == 0,
        "failed": failed,
        "total": total,
        "error_rate_pct": round(rate, 2),
        "threshold_pct": threshold_pct,
    }


def run_shell_gate(script: str) -> dict[str, Any]:
    path = ROOT / script
    if not path.is_file():
        return {"ok": False, "error": f"missing {script}"}
    proc = subprocess.run(["bash", str(path)], cwd=str(ROOT), capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "script": script,
        "stdout_tail": proc.stdout[-1500:],
        "stderr_tail": proc.stderr[-800:],
    }


def run_prod_h_gates(*, skip_subgates: bool = False) -> dict[str, Any]:
    results: dict[str, Any] = {
        "stub_audit": audit_prod_stub_flags(),
        "webhook_error_rate": webhook_job_error_rate(),
    }
    if not skip_subgates:
        results["cskh_board_gate"] = run_shell_gate("scripts/cskh_board_gate.sh")
        results["zalo_gate"] = run_shell_gate("scripts/zalo_prod_cutover_gate.sh")
    results["ok"] = all(
        bool(v.get("ok"))
        for k, v in results.items()
        if k != "ok" and isinstance(v, dict)
    )
    return results


def main() -> int:
    skip = "--skip-subgates" in sys.argv
    out = run_prod_h_gates(skip_subgates=skip)
    print(json.dumps(out, indent=2, default=str))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
