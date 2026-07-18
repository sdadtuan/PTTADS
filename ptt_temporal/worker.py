#!/usr/bin/env python3
"""Run PTT Temporal worker (Phase 3 T1/T2/T3/T4)."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from temporalio.client import Client
from temporalio.worker import Worker

from ptt_temporal.activities.creative import (
    notify_am_creative_decision,
    notify_am_creative_pending,
)
from ptt_temporal.activities.launch_qa import (
    fetch_launch_qa_checklist,
    mark_launch_qa_passed,
    notify_am_launch_qa,
)
from ptt_temporal.activities.onboarding import (
    activate_client_onboarding,
    check_onboarding_progress,
    notify_am_onboarding,
)
from ptt_temporal.config import task_queue, temporal_address, temporal_namespace
from ptt_temporal.workflows.campaign_write_approval import CampaignWriteApprovalWorkflow
from ptt_temporal.workflows.client_onboarding import ClientOnboardingWorkflow
from ptt_temporal.workflows.creative_approval import CreativeApprovalWorkflow
from ptt_temporal.workflows.launch_qa import LaunchQAWorkflow
from ptt_temporal.activities.campaign_write import (
    execute_campaign_write,
    mark_campaign_write_executed,
    notify_am_campaign_write,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("ptt_temporal.worker")


async def main() -> None:
    addr = temporal_address()
    ns = temporal_namespace()
    queue = task_queue()
    logger.info("Connecting Temporal %s namespace=%s queue=%s", addr, ns, queue)
    client = await Client.connect(addr, namespace=ns)
    worker = Worker(
        client,
        task_queue=queue,
        workflows=[CreativeApprovalWorkflow, ClientOnboardingWorkflow, LaunchQAWorkflow, CampaignWriteApprovalWorkflow],
        activities=[
            notify_am_creative_pending,
            notify_am_creative_decision,
            check_onboarding_progress,
            activate_client_onboarding,
            notify_am_onboarding,
            fetch_launch_qa_checklist,
            mark_launch_qa_passed,
            notify_am_launch_qa,
            notify_am_campaign_write,
            execute_campaign_write,
            mark_campaign_write_executed,
        ],
    )
    logger.info("Worker started (creative + onboarding + launch QA + campaign write)")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
