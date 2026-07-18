"""Campaign write approval workflow (Phase 4 F2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.campaign_write import (
        CampaignWriteExecuteInput,
        CampaignWriteNotifyInput,
        MarkCampaignWriteInput,
        execute_campaign_write,
        mark_campaign_write_executed,
        notify_am_campaign_write,
    )


@dataclass
class CampaignWriteApprovalInput:
    request_id: str
    client_id: str
    external_campaign_id: str
    change_type: str
    new_value: dict[str, Any]
    submitted_by: str


@workflow.defn(name="CampaignWriteApprovalWorkflow")
class CampaignWriteApprovalWorkflow:
    def __init__(self) -> None:
        self._approved: Optional[bool] = None
        self._approved_by: Optional[str] = None
        self._note: Optional[str] = None

    @workflow.run
    async def run(self, inp: CampaignWriteApprovalInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(
            notify_am_campaign_write,
            CampaignWriteNotifyInput(
                request_id=inp.request_id,
                client_id=inp.client_id,
                external_campaign_id=inp.external_campaign_id,
                change_type=inp.change_type,
                submitted_by=inp.submitted_by,
                message="Chờ admin duyệt thay đổi campaign",
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        try:
            await workflow.wait_condition(
                lambda: self._approved is not None,
                timeout=timedelta(days=3),
            )
        except TimeoutError:
            return {"request_id": inp.request_id, "status": "expired"}

        if not self._approved:
            return {
                "request_id": inp.request_id,
                "status": "rejected",
                "approved_by": self._approved_by,
            }

        outcome = await workflow.execute_activity(
            execute_campaign_write,
            CampaignWriteExecuteInput(
                request_id=inp.request_id,
                client_id=inp.client_id,
                external_campaign_id=inp.external_campaign_id,
                change_type=inp.change_type,
                new_value=inp.new_value,
            ),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )
        ok = bool(outcome.get("ok"))
        err = None if ok else str(outcome.get("error") or "execution_failed")
        await workflow.execute_activity(
            mark_campaign_write_executed,
            MarkCampaignWriteInput(request_id=inp.request_id, ok=ok, error=err),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )
        return {
            "request_id": inp.request_id,
            "status": "executed" if ok else "execution_failed",
            "approved_by": self._approved_by,
            "outcome": outcome,
        }

    @workflow.signal
    async def approve_write(self, payload: dict) -> None:
        self._approved = True
        self._approved_by = str(payload.get("approved_by") or "")
        self._note = str(payload.get("note") or "")

    @workflow.signal
    async def reject_write(self, payload: dict) -> None:
        self._approved = False
        self._approved_by = str(payload.get("approved_by") or "")
        self._note = str(payload.get("note") or "")
