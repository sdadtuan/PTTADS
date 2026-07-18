"""Onboarding workflow activities (Phase 3 T2)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class OnboardingProgressInput:
    client_id: str


@dataclass
class OnboardingNotifyInput:
    client_id: str
    started_by: str
    message: str
    progress_percent: Optional[int] = None


@activity.defn(name="check_onboarding_progress")
async def check_onboarding_progress(inp: OnboardingProgressInput) -> dict[str, Any]:
    from ptt_agency.clients import onboarding_progress

    prog = onboarding_progress(inp.client_id)
    return {"client_id": inp.client_id, **prog}


@activity.defn(name="activate_client_onboarding")
async def activate_client_onboarding(inp: OnboardingProgressInput) -> dict[str, Any]:
    from ptt_agency.clients import activate_client

    try:
        client = activate_client(inp.client_id, force=False)
        return {"ok": True, "status": client.get("status"), "client_id": inp.client_id}
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "client_id": inp.client_id}


@activity.defn(name="notify_am_onboarding")
async def notify_am_onboarding(inp: OnboardingNotifyInput) -> dict[str, Any]:
    recipient = inp.started_by or "am@pttads.vn"
    title = inp.message
    body = f"Client {inp.client_id}"
    if inp.progress_percent is not None:
        body += f" — tiến độ {inp.progress_percent}%"
    meta = {"client_id": inp.client_id, "kind": "onboarding", "progress": inp.progress_percent}
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notification_inbox (recipient_id, category, title, body, link_url, meta)
                    VALUES (%s, 'onboarding', %s, %s, %s, %s::jsonb)
                    RETURNING id::text
                    """,
                    (recipient, title, body, f"/crm/agency/clients/{inp.client_id}", json.dumps(meta)),
                )
                row = cur.fetchone()
            conn.commit()
        return {"ok": True, "notification_id": row[0] if row else None}
    except Exception as exc:
        logger.warning("notify_am_onboarding fallback: %s", exc)
        return {"ok": False, "error": str(exc)}
