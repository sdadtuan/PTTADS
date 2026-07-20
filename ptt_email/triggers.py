"""Journey event triggers — engagement → enrollment (EM-12)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_email.config import email_journeys_enabled
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def record_trigger_event(
    *,
    client_id: str,
    contact_id: str,
    event_type: str,
    source_send_id: str | None = None,
    source_campaign_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    if not email_journeys_enabled():
        return
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.journey_trigger_events (
                  client_id, contact_id, event_type, source_send_id, source_campaign_id, meta
                ) VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s::uuid, %s::jsonb)
                """,
                (
                    client_id,
                    contact_id,
                    event_type,
                    source_send_id,
                    source_campaign_id,
                    json.dumps(meta or {}),
                ),
            )
        conn.commit()


def process_pending_trigger_events(*, limit: int = 200) -> dict[str, Any]:
    if not email_journeys_enabled():
        return {"ok": True, "skipped": True, "processed": 0}

    from ptt_email.journey_engine import enroll_contact_on_event, _next_step_key

    processed = 0
    enrolled = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text, contact_id::text, event_type,
                       source_campaign_id::text, meta
                FROM {SCHEMA}.journey_trigger_events
                WHERE processed_at IS NULL
                ORDER BY occurred_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (limit,),
            )
            events = cur.fetchall()
            for event_id, client_id, contact_id, event_type, source_campaign_id, meta_raw in events:
                meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw or "{}")
                trigger_map = {
                    "open": "event_open",
                    "click": "event_click",
                }
                trigger_type = trigger_map.get(event_type)
                if not trigger_type:
                    cur.execute(
                        f"UPDATE {SCHEMA}.journey_trigger_events SET processed_at = NOW() WHERE id = %s::uuid",
                        (event_id,),
                    )
                    processed += 1
                    continue

                cur.execute(
                    f"""
                    SELECT j.id::text, j.graph_json
                    FROM {SCHEMA}.journeys j
                    WHERE j.client_id = %s::uuid
                      AND j.status = 'active'
                      AND j.trigger_type = %s
                    """,
                    (client_id, trigger_type),
                )
                journeys = cur.fetchall()
                for journey_id, graph_raw in journeys:
                    graph = graph_raw if isinstance(graph_raw, dict) else json.loads(graph_raw or "{}")
                    trigger_node = None
                    for node in graph.get("nodes") or []:
                        if isinstance(node, dict) and node.get("type") == "trigger":
                            cfg = node.get("config") or {}
                            req_campaign = str(cfg.get("source_campaign_id") or "").strip()
                            if req_campaign and source_campaign_id and req_campaign != source_campaign_id:
                                continue
                            trigger_node = node
                            break
                    if not trigger_node:
                        continue
                    first_step = _next_step_key(graph, str(trigger_node.get("id")))
                    if not first_step:
                        continue
                    out = enroll_contact_on_event(cur, journey_id, client_id, contact_id, first_step)
                    if out:
                        enrolled += 1

                cur.execute(
                    f"UPDATE {SCHEMA}.journey_trigger_events SET processed_at = NOW() WHERE id = %s::uuid",
                    (event_id,),
                )
                processed += 1
        conn.commit()

    logger.info("journey_trigger_events processed=%s enrolled=%s", processed, enrolled)
    return {"ok": True, "processed": processed, "enrolled": enrolled}
