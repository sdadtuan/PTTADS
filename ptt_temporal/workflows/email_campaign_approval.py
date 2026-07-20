"""Email campaign approval workflow (EM-6)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.email_campaign import (
        EmailCampaignNotifyInput,
        EmailCampaignPrepareInput,
        enqueue_email_campaign_prepare,
        notify_email_campaign_pending,
    )


@dataclass
class EmailCampaignApprovalInput:
    campaign_id: str
    client_id: str
    campaign_name: str
    submitted_by: str


@workflow.defn(name="EmailCampaignApprovalWorkflow")
class EmailCampaignApprovalWorkflow:
    def __init__(self) -> None:
        self._decision: Optional[str] = None
        self._reviewed_by: Optional[str] = None
        self._note: Optional[str] = None

    @workflow.run
    async def run(self, inp: EmailCampaignApprovalInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(
            notify_email_campaign_pending,
            EmailCampaignNotifyInput(
                campaign_id=inp.campaign_id,
                client_id=inp.client_id,
                campaign_name=inp.campaign_name,
                submitted_by=inp.submitted_by,
                message="Chờ phê duyệt trước khi gửi",
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(days=14),
            )
        except TimeoutError:
            return {"campaign_id": inp.campaign_id, "status": "expired"}

        if self._decision != "approved":
            return {
                "campaign_id": inp.campaign_id,
                "status": self._decision or "rejected",
                "reviewed_by": self._reviewed_by,
            }

        outcome = await workflow.execute_activity(
            enqueue_email_campaign_prepare,
            EmailCampaignPrepareInput(
                campaign_id=inp.campaign_id,
                client_id=inp.client_id,
                approved_by=self._reviewed_by or "unknown",
            ),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )
        return {
            "campaign_id": inp.campaign_id,
            "status": "prepare_enqueued",
            "reviewed_by": self._reviewed_by,
            "outcome": outcome,
        }

    @workflow.signal
    async def approve_campaign(self, payload: dict) -> None:
        if self._decision is not None:
            return
        self._decision = "approved"
        self._reviewed_by = str(payload.get("reviewed_by") or payload.get("approved_by") or "")
        self._note = payload.get("note")

    @workflow.signal
    async def reject_campaign(self, payload: dict) -> None:
        if self._decision is not None:
            return
        self._decision = "rejected"
        self._reviewed_by = str(payload.get("reviewed_by") or payload.get("approved_by") or "")
        self._note = payload.get("note")
