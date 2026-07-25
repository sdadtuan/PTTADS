"""Webhook / ingest job health monitor (PROD-H-MON)."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def webhook_health_enabled() -> bool:
    return os.environ.get("PTT_WEBHOOK_HEALTH_MONITOR", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def evaluate_webhook_health(*, dry_run: bool = False) -> dict[str, Any]:
    from ptt_crm.prod_h_gates import webhook_job_error_rate

    out = webhook_job_error_rate()
    if out.get("skipped") or out.get("ok"):
        return {**out, "alert_sent": False}

    if dry_run:
        return {**out, "dry_run": True, "alert_sent": False}

    try:
        from ptt_agency.notifications import notify_agency_ops

        notify_agency_ops(
            recipient_id="admin",
            title="Webhook / ingest error rate cao",
            body=(
                f"Tỷ lệ job failed {out.get('error_rate_pct')}% "
                f"(ngưỡng {out.get('threshold_pct')}%) trong 24h — "
                f"{out.get('failed')}/{out.get('total')} jobs."
            ),
            category="webhook_health",
            link_url="/agency/jobs",
            meta=out,
            email_env="PTT_AGENCY_SLA_ALERT_EMAIL",
            slack_prefix=":rotating_light: [PTT Webhook Health]",
        )
        return {**out, "alert_sent": True}
    except Exception as exc:
        logger.warning("webhook health alert failed: %s", exc)
        return {**out, "alert_sent": False, "alert_error": str(exc)}
