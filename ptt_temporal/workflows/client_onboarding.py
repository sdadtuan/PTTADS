"""Client onboarding Temporal workflow (Phase 3 T2)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.onboarding import (
        OnboardingNotifyInput,
        OnboardingProgressInput,
        activate_client_onboarding,
        check_onboarding_progress,
        notify_am_onboarding,
    )


@dataclass
class ClientOnboardingInput:
    client_id: str
    started_by: str


@workflow.defn(name="ClientOnboardingWorkflow")
class ClientOnboardingWorkflow:
    def __init__(self) -> None:
        self._nudge = False

    @workflow.run
    async def run(self, inp: ClientOnboardingInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(
            notify_am_onboarding,
            OnboardingNotifyInput(
                client_id=inp.client_id,
                started_by=inp.started_by,
                message="Onboarding workflow started",
                progress_percent=0,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        deadline = workflow.now() + timedelta(days=90)
        while workflow.now() < deadline:
            prog = await workflow.execute_activity(
                check_onboarding_progress,
                OnboardingProgressInput(client_id=inp.client_id),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry,
            )
            pct = int(prog.get("percent") or 0)
            if pct >= 100:
                act = await workflow.execute_activity(
                    activate_client_onboarding,
                    OnboardingProgressInput(client_id=inp.client_id),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry,
                )
                await workflow.execute_activity(
                    notify_am_onboarding,
                    OnboardingNotifyInput(
                        client_id=inp.client_id,
                        started_by=inp.started_by,
                        message="Onboarding hoàn tất — client active",
                        progress_percent=100,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry,
                )
                return {"client_id": inp.client_id, "status": "completed", "activate": act}

            self._nudge = False
            try:
                await workflow.wait_condition(
                    lambda: self._nudge,
                    timeout=timedelta(hours=6),
                )
            except TimeoutError:
                pass

        return {"client_id": inp.client_id, "status": "timeout"}

    @workflow.signal
    async def checklist_updated(self, _payload: dict) -> None:
        self._nudge = True
