"""Hub campaign PG write path (Phase 3 D1 dual-write)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_crm.config import hub_pg_primary
from ptt_crm.hub_pg_read import pg_hub_campaigns_ready
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def upsert_hub_campaign_from_sqlite(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Mirror SQLite crm_campaigns row → hub_campaigns when PG primary flag on."""
    if not hub_pg_primary() or not pg_hub_campaigns_ready():
        return None
    sqlite_id = int(rec.get("id") or 0)
    if sqlite_id <= 0:
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hub_campaigns (
                    sqlite_campaign_id, code, name, channel, external_ref,
                    utm_campaign, notes, active, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (sqlite_campaign_id) DO UPDATE SET
                    code = EXCLUDED.code,
                    name = EXCLUDED.name,
                    channel = EXCLUDED.channel,
                    external_ref = EXCLUDED.external_ref,
                    utm_campaign = EXCLUDED.utm_campaign,
                    notes = EXCLUDED.notes,
                    active = EXCLUDED.active,
                    updated_at = NOW()
                RETURNING id, sqlite_campaign_id
                """,
                (
                    sqlite_id,
                    str(rec.get("code") or ""),
                    str(rec.get("name") or ""),
                    str(rec.get("channel") or "other"),
                    str(rec.get("external_ref") or ""),
                    str(rec.get("utm_campaign") or ""),
                    str(rec.get("notes") or ""),
                    bool(int(rec.get("active") or 1)),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        return None
    return {"pg_id": int(row[0]), "sqlite_campaign_id": int(row[1])}
