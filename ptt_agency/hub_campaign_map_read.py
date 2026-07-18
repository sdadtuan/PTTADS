"""Read hub_campaign_map rows for Agency UI (Phase 2 P2 #10)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def list_hub_campaign_maps(
    client_id: str,
    *,
    channel: str | None = None,
    active_only: bool = True,
    limit: int = 100,
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 200))
    clauses = ["client_id = %s::uuid"]
    params: list[Any] = [client_id]
    if channel:
        clauses.append("channel = %s")
        params.append(channel.strip().lower())
    if active_only:
        clauses.append("active IS TRUE")
    where = " AND ".join(clauses)
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT hub_campaign_id, channel, external_campaign_id, external_campaign_name,
                           target_cpl_vnd, active, updated_at
                    FROM hub_campaign_map
                    WHERE {where}
                    ORDER BY external_campaign_name NULLS LAST, external_campaign_id
                    LIMIT %s
                    """,
                    [*params, lim],
                )
                cols = [d[0] for d in cur.description]
                rows = []
                for row in cur.fetchall():
                    rec = dict(zip(cols, row))
                    target = rec.get("target_cpl_vnd")
                    rows.append(
                        {
                            "hub_campaign_id": int(rec["hub_campaign_id"]) if rec.get("hub_campaign_id") is not None else None,
                            "channel": rec.get("channel") or "meta",
                            "external_campaign_id": rec.get("external_campaign_id"),
                            "external_campaign_name": rec.get("external_campaign_name"),
                            "target_cpl_vnd": float(target) if target is not None else None,
                            "active": bool(rec.get("active")),
                            "updated_at": rec["updated_at"].isoformat() if rec.get("updated_at") else None,
                            "hub_url": (
                                f"/crm/hub?campaign_id={int(rec['hub_campaign_id'])}"
                                if rec.get("hub_campaign_id") is not None
                                else "/crm/hub"
                            ),
                        }
                    )
        return {"ok": True, "client_id": client_id, "maps": rows, "count": len(rows)}
    except Exception as exc:
        logger.debug("list_hub_campaign_maps: %s", exc)
        return {"ok": False, "error": str(exc), "maps": []}
