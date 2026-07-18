"""Tests for CampaignWriteApprovalWorkflow (Phase 4 F2)."""
from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from ptt_temporal.activities.campaign_write import (
    execute_campaign_write,
    mark_campaign_write_executed,
    notify_am_campaign_write,
)
from ptt_temporal.workflows.campaign_write_approval import (
    CampaignWriteApprovalInput,
    CampaignWriteApprovalWorkflow,
)


class TestCampaignWriteWorkflow(unittest.IsolatedAsyncioTestCase):
    @patch("ptt_agency.notifications.notify_agency_ops")
    @patch("ptt_jobs.db.pg_connection")
    @patch("ptt_meta.campaign_write.apply_daily_budget", return_value={"ok": True, "stub": True})
    @patch(
        "ptt_agency.clients.load_channel_account_for_sync",
        return_value=[{"status": "active", "external_account_id": "act_123"}],
    )
    async def test_approve_then_execute(self, _accounts, _budget, mock_pg, _notify) -> None:
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-campaign-write",
                workflows=[CampaignWriteApprovalWorkflow],
                activities=[
                    notify_am_campaign_write,
                    execute_campaign_write,
                    mark_campaign_write_executed,
                ],
            ):
                handle = await env.client.start_workflow(
                    CampaignWriteApprovalWorkflow.run,
                    CampaignWriteApprovalInput(
                        request_id="550e8400-e29b-41d4-a716-446655440001",
                        client_id="550e8400-e29b-41d4-a716-446655440000",
                        external_campaign_id="120210123456789",
                        change_type="daily_budget",
                        new_value={"daily_budget_vnd": 500000},
                        submitted_by="am@pttads.vn",
                    ),
                    id="test-campaign-write-approve",
                    task_queue="test-campaign-write",
                    execution_timeout=timedelta(minutes=1),
                )
                await handle.signal(
                    CampaignWriteApprovalWorkflow.approve_write,
                    {"approved_by": "admin@pttads.vn", "note": "ok"},
                )
                result = await handle.result()
                self.assertEqual(result["status"], "executed")
                self.assertEqual(result["approved_by"], "admin@pttads.vn")

    @patch("ptt_agency.notifications.notify_agency_ops")
    async def test_reject_skips_execute(self, _notify) -> None:
        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-campaign-write-reject",
                workflows=[CampaignWriteApprovalWorkflow],
                activities=[notify_am_campaign_write],
            ):
                handle = await env.client.start_workflow(
                    CampaignWriteApprovalWorkflow.run,
                    CampaignWriteApprovalInput(
                        request_id="550e8400-e29b-41d4-a716-446655440002",
                        client_id="550e8400-e29b-41d4-a716-446655440000",
                        external_campaign_id="120210123456789",
                        change_type="daily_budget",
                        new_value={"daily_budget_vnd": 300000},
                        submitted_by="am@pttads.vn",
                    ),
                    id="test-campaign-write-reject",
                    task_queue="test-campaign-write-reject",
                    execution_timeout=timedelta(minutes=1),
                )
                await handle.signal(
                    CampaignWriteApprovalWorkflow.reject_write,
                    {"approved_by": "admin@pttads.vn", "note": "no"},
                )
                result = await handle.result()
                self.assertEqual(result["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
