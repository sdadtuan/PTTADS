"""SEO content client-review Temporal workflow (Gate C P3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.seo_content import (
        SeoContentDecisionInput,
        SeoContentPendingInput,
        notify_am_seo_content_decision,
        notify_am_seo_content_pending,
    )


@dataclass
class SeoContentApprovalInput:
    content_id: int
    customer_id: int
    client_id: str
    title: str
    submitted_by: str


@workflow.defn(name="SeoContentApprovalWorkflow")
class SeoContentApprovalWorkflow:
    """Wait for portal/client approve/reject on SEO content in client_review."""

    def __init__(self) -> None:
        self._decision: Optional[str] = None
        self._reviewed_by: Optional[str] = None
        self._note: Optional[str] = None

    @workflow.run
    async def run(self, inp: SeoContentApprovalInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(
            notify_am_seo_content_pending,
            SeoContentPendingInput(
                content_id=inp.content_id,
                customer_id=inp.customer_id,
                client_id=inp.client_id,
                title=inp.title,
                submitted_by=inp.submitted_by,
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
            self._decision = "expired"

        await workflow.execute_activity(
            notify_am_seo_content_decision,
            SeoContentDecisionInput(
                content_id=inp.content_id,
                customer_id=inp.customer_id,
                client_id=inp.client_id,
                title=inp.title,
                submitted_by=inp.submitted_by,
                decision=self._decision or "expired",
                reviewed_by=self._reviewed_by,
                note=self._note,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        return {
            "content_id": inp.content_id,
            "decision": self._decision,
            "reviewed_by": self._reviewed_by,
            "note": self._note,
        }

    @workflow.signal
    async def approve_content(self, payload: dict) -> None:
        if self._decision is not None:
            return
        self._decision = "approved"
        self._reviewed_by = str(payload.get("reviewed_by") or "")
        self._note = payload.get("note")

    @workflow.signal
    async def reject_content(self, payload: dict) -> None:
        if self._decision is not None:
            return
        self._decision = "rejected"
        self._reviewed_by = str(payload.get("reviewed_by") or "")
        self._note = payload.get("note")
