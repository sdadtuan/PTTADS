"""Launch QA Temporal workflow (Phase 3 T3)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ptt_temporal.activities.launch_qa import (
        LaunchQaNotifyInput,
        LaunchQaRunInput,
        fetch_launch_qa_checklist,
        mark_launch_qa_passed,
        notify_am_launch_qa,
    )


@dataclass
class LaunchQAInput:
    run_id: str
    client_id: str
    external_campaign_id: str
    started_by: str
    campaign_name: Optional[str] = None


@workflow.defn(name="LaunchQAWorkflow")
class LaunchQAWorkflow:
    def __init__(self) -> None:
        self._nudge = False

    @workflow.run
    async def run(self, inp: LaunchQAInput) -> dict:
        retry = RetryPolicy(maximum_attempts=3)
        await workflow.execute_activity(
            notify_am_launch_qa,
            LaunchQaNotifyInput(
                run_id=inp.run_id,
                client_id=inp.client_id,
                started_by=inp.started_by,
                message="Launch QA started",
                external_campaign_id=inp.external_campaign_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        deadline = workflow.now() + timedelta(days=14)
        while workflow.now() < deadline:
            state = await workflow.execute_activity(
                fetch_launch_qa_checklist,
                LaunchQaRunInput(run_id=inp.run_id),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry,
            )
            if not state.get("ok"):
                return {"run_id": inp.run_id, "status": "error", "detail": state}
            if int(state.get("percent") or 0) >= 100:
                result = await workflow.execute_activity(
                    mark_launch_qa_passed,
                    LaunchQaRunInput(run_id=inp.run_id),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry,
                )
                await workflow.execute_activity(
                    notify_am_launch_qa,
                    LaunchQaNotifyInput(
                        run_id=inp.run_id,
                        client_id=inp.client_id,
                        started_by=inp.started_by,
                        message="Launch QA passed — launch_ready",
                        external_campaign_id=inp.external_campaign_id,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=retry,
                )
                return {"run_id": inp.run_id, "status": "passed", "result": result}

            self._nudge = False
            try:
                await workflow.wait_condition(lambda: self._nudge, timeout=timedelta(hours=4))
            except TimeoutError:
                pass

        return {"run_id": inp.run_id, "status": "timeout"}

    @workflow.signal
    async def checklist_updated(self, _payload: dict) -> None:
        self._nudge = True
