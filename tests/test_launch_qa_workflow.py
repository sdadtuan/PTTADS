"""Tests for LaunchQAWorkflow (Phase 3 T3)."""
from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import patch

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from ptt_temporal.activities.launch_qa import (
    fetch_launch_qa_checklist,
    mark_launch_qa_passed,
    notify_am_launch_qa,
)
from ptt_temporal.workflows.launch_qa import LaunchQAInput, LaunchQAWorkflow


class TestLaunchQAWorkflow(unittest.IsolatedAsyncioTestCase):
    @patch("ptt_agency.launch_qa.mark_launch_qa_passed", return_value={"ok": True, "status": "passed"})
    @patch(
        "ptt_agency.launch_qa.fetch_launch_qa_run",
        return_value={
            "id": "run-1",
            "status": "in_progress",
            "launch_ready": False,
            "checklist": {
                "pixel_verified": {"label": "Pixel", "completed": True},
                "qa_signoff": {"label": "QA", "completed": True},
            },
        },
    )
    async def test_checklist_complete_passes(self, _fetch, _mark) -> None:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-launch-qa",
                workflows=[LaunchQAWorkflow],
                activities=[fetch_launch_qa_checklist, mark_launch_qa_passed, notify_am_launch_qa],
            ):
                handle = await env.client.start_workflow(
                    LaunchQAWorkflow.run,
                    LaunchQAInput(
                        run_id="run-1",
                        client_id="550e8400-e29b-41d4-a716-446655440000",
                        external_campaign_id="camp-1",
                        started_by="qa@test.local",
                    ),
                    id="test-launch-qa-pass",
                    task_queue="test-launch-qa",
                    execution_timeout=timedelta(minutes=1),
                )
                result = await handle.result()
                self.assertEqual(result["status"], "passed")


if __name__ == "__main__":
    unittest.main()
