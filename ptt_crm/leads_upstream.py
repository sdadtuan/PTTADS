"""Proxy GET /api/v1/leads to NestJS when PTT_LEADS_READ_UPSTREAM=nest (Phase 1b Bước 8)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_crm.config import leads_read_upstream
from ptt_crm.dual_run import fetch_nest_json

logger = logging.getLogger(__name__)


def nest_upstream_enabled() -> bool:
    return leads_read_upstream() == "nest"


def proxy_list_leads(query: str = "") -> tuple[dict[str, Any], int]:
    status, body, err = fetch_nest_json("/api/v1/leads", query=query)
    if err:
        logger.warning("nest upstream list failed: %s", err)
        return {"error": err, "upstream": "nest"}, 502
    return body or {}, status


def proxy_get_lead(lead_id: int) -> tuple[dict[str, Any], int]:
    status, body, err = fetch_nest_json(f"/api/v1/leads/{lead_id}")
    if err:
        logger.warning("nest upstream get lead_id=%s failed: %s", lead_id, err)
        return {"error": err, "upstream": "nest"}, 502
    if status == 404:
        return body or {"error": "Not found"}, 404
    return body or {}, status
