"""Email campaign Temporal activities (EM-6)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class EmailCampaignPrepareInput:
    campaign_id: str
    client_id: str
    approved_by: str


@activity.defn(name="enqueue_email_campaign_prepare")
async def enqueue_email_campaign_prepare(inp: EmailCampaignPrepareInput) -> dict[str, Any]:
    from ptt_jobs.enqueue import enqueue_job

    job = enqueue_job(
        "email_campaign_prepare",
        {"campaign_id": inp.campaign_id, "client_id": inp.client_id},
        f"email_prepare:{inp.campaign_id}",
        client_id=inp.client_id,
    )
    logger.info(
        "Temporal enqueue email_campaign_prepare campaign=%s by=%s job=%s",
        inp.campaign_id,
        inp.approved_by,
        job.get("id"),
    )
    return {"ok": True, "job_id": job.get("id")}


@dataclass
class EmailCampaignNotifyInput:
    campaign_id: str
    client_id: str
    campaign_name: str
    submitted_by: str
    message: str


@activity.defn(name="notify_email_campaign_pending")
async def notify_email_campaign_pending(inp: EmailCampaignNotifyInput) -> dict[str, Any]:
    try:
        from ptt_agency.notifications import notify_agency_ops

        notify_agency_ops(
            recipient_id="admin",
            title=f"Email campaign — {inp.campaign_name}",
            body=f"{inp.message} · by {inp.submitted_by}",
            category="email_campaign",
            link_url="/email/campaigns",
            meta={"campaign_id": inp.campaign_id, "client_id": inp.client_id},
            slack_prefix=":email: [Email Campaign]",
        )
    except Exception as exc:
        logger.debug("notify_email_campaign_pending: %s", exc)
    return {"ok": True}
