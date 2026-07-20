"""Temporal activities — email journey automation (EM-12)."""
from __future__ import annotations

from dataclasses import dataclass

from temporalio import activity


@dataclass
class EmailJourneyBootstrapInput:
    journey_id: str
    client_id: str


@activity.defn(name="bootstrap_email_journey")
async def bootstrap_email_journey(inp: EmailJourneyBootstrapInput) -> dict:
    from ptt_email.journey_engine import enqueue_journey_cron_jobs

    out = enqueue_journey_cron_jobs()
    return {"journey_id": inp.journey_id, "client_id": inp.client_id, "cron": out}
