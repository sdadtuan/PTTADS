"""Email journey workflow — long-running automation state (EM-12)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.email_journey import EmailJourneyBootstrapInput, bootstrap_email_journey


@dataclass
class EmailJourneyInput:
    journey_id: str
    client_id: str
    journey_name: str
    activated_by: str


@workflow.defn(name="EmailJourneyWorkflow")
class EmailJourneyWorkflow:
    def __init__(self) -> None:
        self._paused: bool = False
        self._stopped: bool = False
        self._note: Optional[str] = None

    @workflow.run
    async def run(self, inp: EmailJourneyInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        bootstrap = await workflow.execute_activity(
            bootstrap_email_journey,
            EmailJourneyBootstrapInput(journey_id=inp.journey_id, client_id=inp.client_id),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry,
        )
        await workflow.wait_condition(lambda: self._paused or self._stopped)
        return {
            "journey_id": inp.journey_id,
            "status": "stopped" if self._stopped else "paused",
            "note": self._note,
            "bootstrap": bootstrap,
        }

    @workflow.signal
    async def pause_journey(self, payload: dict) -> None:
        self._paused = True
        self._note = str(payload.get("note") or "")

    @workflow.signal
    async def stop_journey(self, payload: dict) -> None:
        self._stopped = True
        self._note = str(payload.get("note") or "")
