"""Hub campaign PG read path (Phase 3 Track D1)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_crm.config import hub_read_source_pg
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def pg_hub_campaigns_ready() -> bool:
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'hub_campaigns'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_hub_campaigns_ready: %s", exc)
        return False


def list_hub_campaigns(*, active_only: bool = True, limit: int = 200) -> list[dict[str, Any]]:
    if not hub_read_source_pg() or not pg_hub_campaigns_ready():
        return []
    lim = max(1, min(int(limit), 500))
    clause = "WHERE active IS TRUE" if active_only else ""
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, sqlite_campaign_id, code, name, channel, external_ref,
                       utm_campaign, notes, active, created_at, updated_at
                FROM hub_campaigns
                {clause}
                ORDER BY name
                LIMIT %s
                """,
                (lim,),
            )
            cols = [d[0] for d in cur.description]
            out: list[dict[str, Any]] = []
            for row in cur.fetchall():
                rec = dict(zip(cols, row))
                out.append(
                    {
                        "id": int(rec["sqlite_campaign_id"] or rec["id"]),
                        "pg_id": int(rec["id"]),
                        "code": rec.get("code") or "",
                        "name": rec.get("name") or "",
                        "channel": rec.get("channel") or "other",
                        "external_ref": rec.get("external_ref") or "",
                        "utm_campaign": rec.get("utm_campaign") or "",
                        "notes": rec.get("notes") or "",
                        "active": bool(rec.get("active")),
                        "created_at": rec["created_at"].isoformat() if rec.get("created_at") else None,
                        "updated_at": rec["updated_at"].isoformat() if rec.get("updated_at") else None,
                    }
                )
            return out


def get_hub_campaign(campaign_id: int) -> dict[str, Any] | None:
    if not hub_read_source_pg() or not pg_hub_campaigns_ready():
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sqlite_campaign_id, code, name, channel, external_ref,
                       utm_campaign, notes, active, created_at, updated_at
                FROM hub_campaigns
                WHERE sqlite_campaign_id = %s OR id = %s
                LIMIT 1
                """,
                (campaign_id, campaign_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            rec = dict(zip(cols, row))
            return {
                "id": int(rec["sqlite_campaign_id"] or rec["id"]),
                "pg_id": int(rec["id"]),
                "code": rec.get("code") or "",
                "name": rec.get("name") or "",
                "channel": rec.get("channel") or "other",
                "external_ref": rec.get("external_ref") or "",
                "utm_campaign": rec.get("utm_campaign") or "",
                "notes": rec.get("notes") or "",
                "active": bool(rec.get("active")),
            }
