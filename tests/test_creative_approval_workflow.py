"""Tests for CreativeApprovalWorkflow (Phase 3 T4)."""
from __future__ import annotations

import unittest
from datetime import timedelta

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from ptt_temporal.activities.creative import (
    notify_am_creative_decision,
    notify_am_creative_pending,
)
from ptt_temporal.workflows.creative_approval import CreativeApprovalInput, CreativeApprovalWorkflow


class TestCreativeApprovalWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_approve_signal_completes(self) -> None:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-creative",
                workflows=[CreativeApprovalWorkflow],
                activities=[notify_am_creative_pending, notify_am_creative_decision],
            ):
                handle = await env.client.start_workflow(
                    CreativeApprovalWorkflow.run,
                    CreativeApprovalInput(
                        creative_id="c-1",
                        client_id="550e8400-e29b-41d4-a716-446655440000",
                        title="Test Banner",
                        version=1,
                        submitted_by="am@test.local",
                    ),
                    id="test-creative-approve",
                    task_queue="test-creative",
                    execution_timeout=timedelta(minutes=1),
                )
                await handle.signal(
                    CreativeApprovalWorkflow.approve_creative,
                    {"reviewed_by": "client@test.local", "note": "OK"},
                )
                result = await handle.result()
                self.assertEqual(result["decision"], "approved")
                self.assertEqual(result["reviewed_by"], "client@test.local")

    async def test_reject_signal_completes(self) -> None:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-creative",
                workflows=[CreativeApprovalWorkflow],
                activities=[notify_am_creative_pending, notify_am_creative_decision],
            ):
                handle = await env.client.start_workflow(
                    CreativeApprovalWorkflow.run,
                    CreativeApprovalInput(
                        creative_id="c-2",
                        client_id="550e8400-e29b-41d4-a716-446655440000",
                        title="Reject Me",
                        version=2,
                        submitted_by="am@test.local",
                    ),
                    id="test-creative-reject",
                    task_queue="test-creative",
                    execution_timeout=timedelta(minutes=1),
                )
                await handle.signal(
                    CreativeApprovalWorkflow.reject_creative,
                    {"reviewed_by": "client@test.local", "note": "Wrong copy"},
                )
                result = await handle.result()
                self.assertEqual(result["decision"], "rejected")
                self.assertEqual(result["note"], "Wrong copy")


if __name__ == "__main__":
    unittest.main()
