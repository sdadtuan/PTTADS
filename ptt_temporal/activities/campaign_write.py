"""Campaign write Temporal activities (Phase 4 F2 / Prod-Z4)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
    channel: str = "meta"


@dataclass
class CampaignWriteExecuteInput:
    request_id: str
    client_id: str
    external_campaign_id: str
    change_type: str
    new_value: dict[str, Any]
    channel: str = "meta"


@activity.defn(name="notify_am_campaign_write")
async def notify_am_campaign_write(inp: CampaignWriteNotifyInput) -> dict[str, Any]:
    from ptt_agency.notifications import notify_agency_ops

    channel_label = (inp.channel or "meta").upper()
    notify_agency_ops(
        recipient_id="admin",
        title=f"Campaign write [{channel_label}] — {inp.change_type}",
        body=f"{inp.message} · campaign {inp.external_campaign_id} · by {inp.submitted_by}",
        category="campaign_write",
        link_url="/crm/campaign-writes",
        meta={"request_id": inp.request_id, "client_id": inp.client_id, "channel": inp.channel},
        slack_prefix=":memo: [Campaign Write]",
    )
    return {"ok": True}


def _pick_active_account(accounts: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (a for a in accounts if str(a.get("status")) == "active"),
        accounts[0] if accounts else None,
    )


def _execute_meta_write(inp: CampaignWriteExecuteInput, account: dict[str, Any]) -> dict[str, Any]:
    from ptt_meta.campaign_write import apply_daily_budget

    if inp.change_type == "daily_budget":
        budget = int(inp.new_value.get("daily_budget_vnd") or 0)
        return apply_daily_budget(
            account=account,
            external_campaign_id=inp.external_campaign_id,
            daily_budget_vnd=budget,
            client_id=inp.client_id,
        )
    return {"ok": False, "error": f"unsupported_change_type:{inp.change_type}"}


def _execute_zalo_write(inp: CampaignWriteExecuteInput, account: dict[str, Any]) -> dict[str, Any]:
    from ptt_zalo.campaign_write import apply_campaign_status, apply_daily_budget, create_campaign

    if inp.change_type == "create_campaign":
        new_value = dict(inp.new_value or {})
        new_value.setdefault("pending_ref", inp.external_campaign_id)
        return create_campaign(
            account=account,
            new_value=new_value,
            client_id=inp.client_id,
        )
    if inp.change_type == "status":
        status = str(inp.new_value.get("status") or inp.new_value.get("effective_status") or "")
        return apply_campaign_status(
            account=account,
            external_campaign_id=inp.external_campaign_id,
            status=status,
            client_id=inp.client_id,
        )
    if inp.change_type == "daily_budget":
        budget = int(inp.new_value.get("daily_budget_vnd") or 0)
        return apply_daily_budget(
            account=account,
            external_campaign_id=inp.external_campaign_id,
            daily_budget_vnd=budget,
            client_id=inp.client_id,
        )
    return {"ok": False, "error": f"unsupported_change_type:{inp.change_type}"}


@activity.defn(name="execute_campaign_write")
async def execute_campaign_write(inp: CampaignWriteExecuteInput) -> dict[str, Any]:
    from ptt_agency.clients import load_channel_account_for_sync

    channel = (inp.channel or "meta").strip().lower()
    accounts = load_channel_account_for_sync(inp.client_id, channel=channel)
    account = _pick_active_account(accounts)
    if not account:
        return {"ok": False, "error": f"no_{channel}_account"}

    if channel == "zalo":
        return _execute_zalo_write(inp, account)
    if channel == "meta":
        return _execute_meta_write(inp, account)
    return {"ok": False, "error": f"unsupported_channel:{channel}"}


@dataclass
class MarkCampaignWriteInput:
    request_id: str
    ok: bool
    error: Optional[str] = None
    execution_outcome: dict[str, Any] = field(default_factory=dict)


@activity.defn(name="mark_campaign_write_executed")
async def mark_campaign_write_executed(inp: MarkCampaignWriteInput) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    status = "executed" if inp.ok else "execution_failed"
    row_meta: tuple[str, str, str, str] | None = None
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
                RETURNING client_id::text, external_campaign_id, change_type, channel
                """,
                (status, inp.ok, inp.error, inp.request_id),
            )
            fetched = cur.fetchone()
            if fetched:
                row_meta = (str(fetched[0]), str(fetched[1]), str(fetched[2]), str(fetched[3]))
        conn.commit()

    if inp.ok and row_meta:
        client_id, external_campaign_id, change_type, channel = row_meta
        if change_type == "daily_budget" and channel == "meta":
            try:
                from ptt_crm.nest_api import sync_launch_qa_budget_confirmed

                code, payload = sync_launch_qa_budget_confirmed(
                    {
                        "client_id": client_id,
                        "external_campaign_id": external_campaign_id,
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

        if change_type == "create_campaign" and channel == "zalo":
            outcome = inp.execution_outcome or {}
            mapped_id = str(outcome.get("external_campaign_id") or external_campaign_id or "").strip()
            if mapped_id.startswith("pending:"):
                mapped_id = str(outcome.get("external_campaign_id") or "").strip()
            if mapped_id:
                try:
                    from ptt_crm.nest_api import auto_hub_map_from_campaign_write

                    code, payload = auto_hub_map_from_campaign_write(
                        {
                            "client_id": client_id,
                            "channel": "zalo",
                            "external_campaign_id": mapped_id,
                            "external_campaign_name": outcome.get("external_campaign_name"),
                            "external_account_id": outcome.get("external_account_id"),
                            "request_id": inp.request_id,
                        }
                    )
                    if code >= 400 or not payload.get("ok"):
                        logger.warning(
                            "zalo auto hub map skipped request=%s code=%s payload=%s",
                            inp.request_id,
                            code,
                            payload,
                        )
                except Exception as exc:
                    logger.warning("zalo auto hub map failed request=%s: %s", inp.request_id, exc)

    return {"ok": True, "status": status}
