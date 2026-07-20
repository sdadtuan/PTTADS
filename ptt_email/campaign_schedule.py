"""Scheduled campaign runner — enqueue prepare when due (EM-10)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def run_due_scheduled_campaigns(*, limit: int = 20) -> dict[str, Any]:
    due: list[tuple[str, str]] = []
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text
                FROM {SCHEMA}.campaigns
                WHERE status = 'scheduled'
                  AND scheduled_at IS NOT NULL
                  AND scheduled_at <= NOW()
                ORDER BY scheduled_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            due = [(str(r[0]), str(r[1])) for r in cur.fetchall()]

    if not due:
        return {"ok": True, "processed": 0, "jobs": []}

    from ptt_jobs.enqueue import enqueue_job

    jobs: list[dict[str, Any]] = []
    for campaign_id, client_id in due:
        job = enqueue_job(
            "email_campaign_prepare",
            {"campaign_id": campaign_id, "client_id": client_id},
            f"email_campaign_prepare:{campaign_id}",
            client_id=client_id,
        )
        jobs.append({"campaign_id": campaign_id, "job_id": job.get("id")})
        logger.info("scheduled campaign due campaign=%s job=%s", campaign_id, job.get("id"))

    return {"ok": True, "processed": len(jobs), "jobs": jobs}


def enqueue_due_scheduled_campaigns() -> dict[str, Any]:
    """Idempotent enqueue for minute cron — worker runs run_due_scheduled_campaigns."""
    from datetime import datetime, timezone

    minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    idem = f"email_campaign_schedule_due:{minute}"
    try:
        from ptt_jobs.enqueue import enqueue_job

        job = enqueue_job("email_campaign_schedule_due", {}, idem)
        return {"ok": True, "mode": "queue", "job": job}
    except Exception as exc:
        logger.warning("enqueue_due_scheduled_campaigns inline fallback: %s", exc)
        outcome = run_due_scheduled_campaigns()
        return {"ok": True, "mode": "inline", **outcome}
