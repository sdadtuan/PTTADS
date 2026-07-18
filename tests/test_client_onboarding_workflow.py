"""Tests for ClientOnboardingWorkflow (Phase 3 T2)."""
from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import patch

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from ptt_temporal.activities.onboarding import (
    activate_client_onboarding,
    check_onboarding_progress,
    notify_am_onboarding,
)
from ptt_temporal.workflows.client_onboarding import ClientOnboardingInput, ClientOnboardingWorkflow


class TestClientOnboardingWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_completes_when_progress_100(self) -> None:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            with patch(
                "ptt_agency.clients.onboarding_progress",
                return_value={"percent": 100, "total": 12, "completed": 12},
            ), patch(
                "ptt_agency.clients.activate_client",
                return_value={"id": "550e8400-e29b-41d4-a716-446655440000", "status": "active", "code": "DEMO"},
            ):
                async with Worker(
                    env.client,
                    task_queue="test-onboarding",
                    workflows=[ClientOnboardingWorkflow],
                    activities=[notify_am_onboarding, check_onboarding_progress, activate_client_onboarding],
                ):
                    handle = await env.client.start_workflow(
                        ClientOnboardingWorkflow.run,
                        ClientOnboardingInput(
                            client_id="550e8400-e29b-41d4-a716-446655440000",
                            started_by="am@test.local",
                        ),
                        id="test-onboarding-complete",
                        task_queue="test-onboarding",
                        execution_timeout=timedelta(minutes=2),
                    )
                    result = await handle.result()
                    self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
