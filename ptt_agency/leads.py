"""Leads linked to agency clients (SQLite CRM bridge)."""
from __future__ import annotations

from typing import Any


def list_leads_for_client(client_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    """Leads whose meta_json.agency_client_id matches PG client UUID."""
    from ptt_crm.leads_read import list_leads_v1

    cid = (client_id or "").strip()
    if not cid:
        return []
    rows, _ = list_leads_v1(client_id=cid, limit=min(max(limit, 1), 200))
    return rows
