"""Campaign write Temporal activities (Phase 4 F2)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class CampaignWriteNotifyInput:
    request_id: str
    client_id: str
    external_campaign_id: str
    change_type: str
    submitted_by: str
    message: str


@dataclass
class CampaignWriteExecuteInput:
    request_id: str
    client_id: str
    external_campaign_id: str
    change_type: str
    new_value: dict[str, Any]


@activity.defn(name="notify_am_campaign_write")
async def notify_am_campaign_write(inp: CampaignWriteNotifyInput) -> dict[str, Any]:
    from ptt_agency.notifications import notify_agency_ops

    notify_agency_ops(
        recipient_id="admin",
        title=f"Campaign write — {inp.change_type}",
        body=f"{inp.message} · campaign {inp.external_campaign_id} · by {inp.submitted_by}",
        category="campaign_write",
        link_url="/crm/agency",
        meta={"request_id": inp.request_id, "client_id": inp.client_id},
        slack_prefix=":memo: [Campaign Write]",
    )
    return {"ok": True}


@activity.defn(name="execute_campaign_write")
async def execute_campaign_write(inp: CampaignWriteExecuteInput) -> dict[str, Any]:
    from ptt_agency.clients import load_channel_account_for_sync
    from ptt_meta.campaign_write import apply_daily_budget

    accounts = load_channel_account_for_sync(inp.client_id, channel="meta")
    account = next(
        (a for a in accounts if str(a.get("status")) == "active"),
        accounts[0] if accounts else None,
    )
    if not account:
        return {"ok": False, "error": "no_meta_account"}

    if inp.change_type == "daily_budget":
        budget = int(inp.new_value.get("daily_budget_vnd") or 0)
        return apply_daily_budget(
            account=account,
            external_campaign_id=inp.external_campaign_id,
            daily_budget_vnd=budget,
            client_id=inp.client_id,
        )
    return {"ok": False, "error": f"unsupported_change_type:{inp.change_type}"}


@dataclass
class MarkCampaignWriteInput:
    request_id: str
    ok: bool
    error: Optional[str] = None


@activity.defn(name="mark_campaign_write_executed")
async def mark_campaign_write_executed(inp: MarkCampaignWriteInput) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    status = "executed" if inp.ok else "execution_failed"
    row_meta: tuple[str, str, str] | None = None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE campaign_write_requests
                SET status = %s,
                    executed_at = CASE WHEN %s THEN NOW() ELSE executed_at END,
                    execution_error = %s,
                    updated_at = NOW()
                WHERE id = %s::uuid
                RETURNING client_id::text, external_campaign_id, change_type
                """,
                (status, inp.ok, inp.error, inp.request_id),
            )
            fetched = cur.fetchone()
            if fetched:
                row_meta = (str(fetched[0]), str(fetched[1]), str(fetched[2]))
        conn.commit()

    if inp.ok and row_meta and row_meta[2] == "daily_budget":
        try:
            from ptt_crm.nest_api import sync_launch_qa_budget_confirmed

            code, payload = sync_launch_qa_budget_confirmed(
                {
                    "client_id": row_meta[0],
                    "external_campaign_id": row_meta[1],
                    "request_id": inp.request_id,
                    "executed_by": "system@campaign-write",
                }
            )
            if code >= 400 or not payload.get("synced"):
                logger.warning(
                    "launch_qa budget bridge skipped request=%s code=%s payload=%s",
                    inp.request_id,
                    code,
                    payload,
                )
        except Exception as exc:
            logger.warning("launch_qa budget bridge failed request=%s: %s", inp.request_id, exc)

    return {"ok": True, "status": status}
