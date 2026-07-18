"""Creative approval Temporal workflow (Phase 3 T4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.creative import (
        NotifyDecisionInput,
        NotifyPendingInput,
        notify_am_creative_decision,
        notify_am_creative_pending,
    )


@dataclass
class CreativeApprovalInput:
    creative_id: str
    client_id: str
    title: str
    version: int
    submitted_by: str


@workflow.defn(name="CreativeApprovalWorkflow")
class CreativeApprovalWorkflow:
    """Wait for client portal approve/reject signal; notify AM."""

    def __init__(self) -> None:
        self._decision: Optional[str] = None
        self._reviewed_by: Optional[str] = None
        self._note: Optional[str] = None

    @workflow.run
    async def run(self, inp: CreativeApprovalInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(
            notify_am_creative_pending,
            NotifyPendingInput(
                creative_id=inp.creative_id,
                client_id=inp.client_id,
                title=inp.title,
                version=inp.version,
                submitted_by=inp.submitted_by,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(days=7),
            )
        except TimeoutError:
            self._decision = "expired"

        await workflow.execute_activity(
            notify_am_creative_decision,
            NotifyDecisionInput(
                creative_id=inp.creative_id,
                client_id=inp.client_id,
                title=inp.title,
                version=inp.version,
                submitted_by=inp.submitted_by,
                decision=self._decision or "expired",
                reviewed_by=self._reviewed_by,
                note=self._note,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        return {
            "creative_id": inp.creative_id,
            "decision": self._decision,
            "reviewed_by": self._reviewed_by,
            "note": self._note,
        }

    @workflow.signal
    async def approve_creative(self, payload: dict) -> None:
        if self._decision is not None:
            return
        self._decision = "approved"
        self._reviewed_by = str(payload.get("reviewed_by") or "")
        self._note = payload.get("note")

    @workflow.signal
    async def reject_creative(self, payload: dict) -> None:
        if self._decision is not None:
            return
        self._decision = "rejected"
        self._reviewed_by = str(payload.get("reviewed_by") or "")
        self._note = payload.get("note")
