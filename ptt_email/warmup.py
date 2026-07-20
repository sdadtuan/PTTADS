"""Domain warm-up stage management (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.config import warmup_volume_for_stage

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def tick_warmup(*, client_id: str | None = None) -> dict[str, Any]:
    """Advance warm_up_stage for domains with recent sends and cap below max."""
    from ptt_jobs.db import pg_connection

    updated = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            filter_sql = ""
            params: list[Any] = []
            if client_id:
                filter_sql = " AND d.client_id = %s::uuid"
                params.append(client_id)
            cur.execute(
                f"""
                SELECT d.id::text, d.warm_up_stage, d.domain, d.client_id::text
                FROM {SCHEMA}.domains d
                WHERE d.status = 'active' {filter_sql}
                """,
                params,
            )
            rows = cur.fetchall()
            for domain_id, stage, domain, cid in rows:
                stage = int(stage or 0)
                if stage >= 5:
                    continue
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {SCHEMA}.send_queue sq
                    JOIN {SCHEMA}.workspaces w ON w.client_id = sq.client_id
                    WHERE sq.client_id = %s::uuid
                      AND sq.status IN ('sent', 'delivered')
                      AND sq.sent_at >= NOW() - INTERVAL '7 days'
                    """,
                    (cid,),
                )
                sent_7d = int(cur.fetchone()[0] or 0)
                cap = warmup_volume_for_stage(stage)
                if sent_7d >= cap * 0.8 and stage < 5:
                    new_stage = stage + 1
                    new_cap = warmup_volume_for_stage(new_stage)
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.domains
                        SET warm_up_stage = %s, daily_volume_cap = %s
                        WHERE id = %s::uuid
                        """,
                        (new_stage, new_cap, domain_id),
                    )
                    updated += 1
                    logger.info("warmup advanced domain=%s stage=%s cap=%s", domain, new_stage, new_cap)
        conn.commit()
    return {"ok": True, "updated": updated}
