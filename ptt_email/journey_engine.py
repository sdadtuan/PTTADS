"""Journey execution engine — segment_enter enroll + step tick (EM-11)."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ptt_email.config import email_journeys_enabled, email_send_enabled
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def _next_step_by_label(graph: dict[str, Any], current: str, label: str) -> str | None:
    edges = graph.get("edges") or []
    if isinstance(edges, list):
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("from") or edge.get("source") or "")
            if src != current:
                continue
            edge_label = str(edge.get("label") or edge.get("condition") or "default").lower()
            if edge_label == label.lower() or (label == "default" and edge_label in ("default", "")):
                tgt = str(edge.get("to") or edge.get("target") or "")
                return tgt or None
    return _next_step_key(graph, current)


def _evaluate_branch(
    cur,
    *,
    client_id: str,
    contact_id: str,
    config: dict[str, Any],
) -> bool:
    condition = str(config.get("condition_type") or config.get("condition") or "opened").lower()
    campaign_id = str(config.get("source_campaign_id") or "").strip()
    within_hours = int(config.get("within_hours") or 168)

    if condition in ("opened", "open", "engagement_open"):
        event_type = "open"
    elif condition in ("clicked", "click", "engagement_click"):
        event_type = "click"
    elif condition == "lifecycle":
        stage = str(config.get("lifecycle_stage") or "").strip()
        if not stage:
            return False
        cur.execute(
            f"SELECT lifecycle_stage FROM {SCHEMA}.contacts WHERE id = %s::uuid",
            (contact_id,),
        )
        row = cur.fetchone()
        return bool(row and str(row[0] or "") == stage)
    else:
        event_type = "open"

    clauses = [
        "ee.contact_id = %s::uuid",
        "ee.client_id = %s::uuid",
        "ee.event_type = %s",
        f"ee.occurred_at >= NOW() - INTERVAL '{within_hours} hours'",
    ]
    params: list[Any] = [contact_id, client_id, event_type]
    if campaign_id:
        clauses.append(
            f"EXISTS (SELECT 1 FROM {SCHEMA}.send_queue sq WHERE sq.id = ee.send_id AND sq.campaign_id = %s::uuid)"
        )
        params.append(campaign_id)
    cur.execute(
        f"SELECT 1 FROM {SCHEMA}.engagement_events ee WHERE {' AND '.join(clauses)} LIMIT 1",
        params,
    )
    return cur.fetchone() is not None


def enroll_contact_on_event(
    cur,
    journey_id: str,
    client_id: str,
    contact_id: str,
    first_step: str,
) -> bool:
    cur.execute(
        f"""
        INSERT INTO {SCHEMA}.journey_enrollments (
          journey_id, client_id, contact_id, current_step_key, status, next_run_at
        ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'active', NOW())
        ON CONFLICT (journey_id, contact_id) DO NOTHING
        """,
        (journey_id, client_id, contact_id, first_step),
    )
    if cur.rowcount:
        cur.execute(
            f"""
            UPDATE {SCHEMA}.journeys
            SET enrolled_count = enrolled_count + 1, updated_at = NOW()
            WHERE id = %s::uuid
            """,
            (journey_id,),
        )
        return True
    return False


def _next_step_key(graph: dict[str, Any], current: str | None) -> str | None:
    edges = graph.get("edges") or []
    if isinstance(edges, list) and edges:
        if current is None:
            nodes = graph.get("nodes") or []
            triggers = [n for n in nodes if isinstance(n, dict) and n.get("type") == "trigger"]
            start = str(triggers[0]["id"]) if triggers else None
            if not start and nodes:
                start = str(nodes[0].get("id") or "")
            current = start or None
        if not current:
            return None
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("from") or edge.get("source") or "")
            if src == current:
                tgt = str(edge.get("to") or edge.get("target") or "")
                return tgt or None
        return None

    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    if not nodes:
        return None
    keys = [str(n["id"]) for n in nodes]
    if current is None:
        for n in nodes:
            if n.get("type") == "trigger":
                idx = keys.index(str(n["id"]))
                return keys[idx + 1] if idx + 1 < len(keys) else None
        return keys[0]
    try:
        idx = keys.index(current)
        return keys[idx + 1] if idx + 1 < len(keys) else None
    except ValueError:
        return None


def _wait_until(config: dict[str, Any]) -> datetime:
    hours = float(config.get("hours") or config.get("duration_hours") or 0)
    minutes = float(config.get("minutes") or config.get("duration_minutes") or 0)
    if hours <= 0 and minutes <= 0:
        hours = 24.0
    delta = timedelta(hours=hours, minutes=minutes)
    return datetime.now(timezone.utc) + delta


def scan_segment_enter_enrollments(*, limit: int = 100) -> dict[str, Any]:
    if not email_journeys_enabled():
        return {"ok": True, "skipped": True, "reason": "journeys_disabled", "enrolled": 0}

    enrolled = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT j.id::text, j.client_id::text, j.entry_segment_id::text, j.graph_json
                FROM {SCHEMA}.journeys j
                WHERE j.status = 'active'
                  AND j.trigger_type = 'segment_enter'
                  AND j.entry_segment_id IS NOT NULL
                ORDER BY j.updated_at DESC
                LIMIT 50
                """,
            )
            journeys = cur.fetchall()
            for journey_id, client_id, segment_id, graph_raw in journeys:
                graph = graph_raw if isinstance(graph_raw, dict) else json.loads(graph_raw or "{}")
                first_step = _next_step_key(graph, None)
                if not first_step:
                    continue
                cur.execute(
                    f"""
                    SELECT sm.contact_id::text
                    FROM {SCHEMA}.segment_members sm
                    WHERE sm.segment_id = %s::uuid
                      AND NOT EXISTS (
                        SELECT 1 FROM {SCHEMA}.journey_enrollments je
                        WHERE je.journey_id = %s::uuid AND je.contact_id = sm.contact_id
                      )
                    LIMIT %s
                    """,
                    (segment_id, journey_id, limit),
                )
                for (contact_id,) in cur.fetchall():
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.journey_enrollments (
                          journey_id, client_id, contact_id, current_step_key, status, next_run_at
                        ) VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'active', NOW())
                        ON CONFLICT (journey_id, contact_id) DO NOTHING
                        """,
                        (journey_id, client_id, contact_id, first_step),
                    )
                    if cur.rowcount:
                        enrolled += 1
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journeys
                            SET enrolled_count = enrolled_count + 1, updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (journey_id,),
                        )
        conn.commit()
    logger.info("journey_enroll_scan enrolled=%s", enrolled)
    return {"ok": True, "enrolled": enrolled}


def tick_due_enrollments(*, limit: int = 50) -> dict[str, Any]:
    if not email_journeys_enabled() or not email_send_enabled():
        return {"ok": True, "skipped": True, "reason": "disabled", "processed": 0}

    processed = 0
    sends = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT je.id::text, je.journey_id::text, je.client_id::text, je.contact_id::text,
                       je.current_step_key, j.graph_json, je.meta
                FROM {SCHEMA}.journey_enrollments je
                JOIN {SCHEMA}.journeys j ON j.id = je.journey_id
                WHERE je.status = 'active'
                  AND je.next_run_at <= NOW()
                  AND j.status = 'active'
                ORDER BY je.next_run_at ASC
                LIMIT %s
                FOR UPDATE OF je SKIP LOCKED
                """,
                (limit,),
            )
            rows = cur.fetchall()
            for enroll_id, journey_id, client_id, contact_id, step_key, graph_raw, meta_raw in rows:
                graph = graph_raw if isinstance(graph_raw, dict) else json.loads(graph_raw or "{}")
                enroll_meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw or "{}")
                cur.execute(
                    f"""
                    SELECT step_type, config_json, id::text
                    FROM {SCHEMA}.journey_steps
                    WHERE journey_id = %s::uuid AND step_key = %s
                    LIMIT 1
                    """,
                    (journey_id, step_key),
                )
                step_row = cur.fetchone()
                if not step_row:
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.journey_enrollments
                        SET status = 'failed', updated_at = NOW()
                        WHERE id = %s::uuid
                        """,
                        (enroll_id,),
                    )
                    processed += 1
                    continue

                step_type, config_raw, step_id = step_row
                config = config_raw if isinstance(config_raw, dict) else json.loads(config_raw or "{}")

                if step_type == "wait":
                    if enroll_meta.get("waiting"):
                        nxt = _next_step_key(graph, step_key)
                        meta = {}
                        if not nxt:
                            cur.execute(
                                f"""
                                UPDATE {SCHEMA}.journey_enrollments
                                SET status = 'completed', completed_at = NOW(), updated_at = NOW(),
                                    meta = %s::jsonb
                                WHERE id = %s::uuid
                                """,
                                (json.dumps(meta), enroll_id),
                            )
                        else:
                            cur.execute(
                                f"""
                                UPDATE {SCHEMA}.journey_enrollments
                                SET current_step_key = %s, next_run_at = NOW(), updated_at = NOW(),
                                    meta = %s::jsonb
                                WHERE id = %s::uuid
                                """,
                                (nxt, json.dumps(meta), enroll_id),
                            )
                    else:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET next_run_at = %s, updated_at = NOW(), meta = %s::jsonb
                            WHERE id = %s::uuid
                            """,
                            (
                                _wait_until(config),
                                json.dumps({"waiting": True}),
                                enroll_id,
                            ),
                        )
                    processed += 1
                    continue

                if step_type == "exit":
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.journey_enrollments
                        SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                        WHERE id = %s::uuid
                        """,
                        (enroll_id,),
                    )
                    processed += 1
                    continue

                if step_type == "branch":
                    matched = _evaluate_branch(
                        cur,
                        client_id=client_id,
                        contact_id=contact_id,
                        config=config,
                    )
                    nxt = _next_step_by_label(graph, step_key, "yes" if matched else "no")
                    if not nxt:
                        nxt = _next_step_by_label(graph, step_key, "default")
                    if not nxt:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (enroll_id,),
                        )
                    else:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET current_step_key = %s, next_run_at = NOW(), updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (nxt, enroll_id),
                        )
                    processed += 1
                    continue

                if step_type == "send":
                    template_id = str(config.get("template_id") or "").strip()
                    if not template_id:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET status = 'failed', updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (enroll_id,),
                        )
                        processed += 1
                        continue

                    cur.execute(
                        f"""
                        SELECT ct.email, ct.first_name, ct.last_name,
                               EXISTS (
                                 SELECT 1 FROM {SCHEMA}.suppression_entries se
                                 WHERE se.email_normalized = ct.email_normalized
                                   AND (se.client_id IS NULL OR se.client_id = ct.client_id)
                                   AND se.expires_at IS NULL
                               ) AS suppressed,
                               COALESCE((
                                 SELECT cr.status FROM {SCHEMA}.consent_records cr
                                 WHERE cr.contact_id = ct.id AND cr.topic = 'marketing'
                                 ORDER BY cr.recorded_at DESC LIMIT 1
                               ), '') = 'opted_in' AS consent_ok
                        FROM {SCHEMA}.contacts ct
                        WHERE ct.id = %s::uuid
                        """,
                        (contact_id,),
                    )
                    contact = cur.fetchone()
                    if not contact or contact[3] or not contact[4]:
                        nxt = _next_step_key(graph, step_key)
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET current_step_key = %s, next_run_at = NOW(), updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (nxt or step_key, enroll_id),
                        )
                        if not nxt:
                            cur.execute(
                                f"""
                                UPDATE {SCHEMA}.journey_enrollments
                                SET status = 'completed', completed_at = NOW()
                                WHERE id = %s::uuid
                                """,
                                (enroll_id,),
                            )
                        processed += 1
                        continue

                    cur.execute(
                        f"""
                        SELECT subject_template, html_body, text_body
                        FROM {SCHEMA}.templates WHERE id = %s::uuid AND client_id = %s::uuid
                        """,
                        (template_id, client_id),
                    )
                    tmpl = cur.fetchone()
                    if not tmpl:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET status = 'failed', updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (enroll_id,),
                        )
                        processed += 1
                        continue

                    subject_template, _html, _text = tmpl
                    tracking_id = str(uuid.uuid4())
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.send_queue (
                          client_id, contact_id, status, subject_rendered,
                          personalization, tracking_id, esp_provider, journey_step_id, scheduled_at
                        )
                        SELECT %s::uuid, %s::uuid, 'pending', %s, %s::jsonb, %s::uuid,
                               w.esp_provider, %s::uuid, NOW()
                        FROM {SCHEMA}.workspaces w
                        WHERE w.client_id = %s::uuid
                        LIMIT 1
                        """,
                        (
                            client_id,
                            contact_id,
                            subject_template,
                            json.dumps({"tracking_id": tracking_id}),
                            tracking_id,
                            step_id,
                            client_id,
                        ),
                    )
                    sends += 1
                    nxt = _next_step_key(graph, step_key)
                    if not nxt:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (enroll_id,),
                        )
                    else:
                        cur.execute(
                            f"""
                            UPDATE {SCHEMA}.journey_enrollments
                            SET current_step_key = %s, next_run_at = NOW(), updated_at = NOW()
                            WHERE id = %s::uuid
                            """,
                            (nxt, enroll_id),
                        )
                    processed += 1
                    continue

                nxt = _next_step_key(graph, step_key)
                if not nxt:
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.journey_enrollments
                        SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                        WHERE id = %s::uuid
                        """,
                        (enroll_id,),
                    )
                else:
                    cur.execute(
                        f"""
                        UPDATE {SCHEMA}.journey_enrollments
                        SET current_step_key = %s, next_run_at = NOW(), updated_at = NOW()
                        WHERE id = %s::uuid
                        """,
                        (nxt, enroll_id),
                    )
                processed += 1

        conn.commit()

    if sends > 0:
        from ptt_jobs.enqueue import enqueue_job

        enqueue_job(
            "email_send_batch",
            {},
            f"email_send_batch:journey:{uuid.uuid4()}",
        )

    logger.info("journey_tick processed=%s sends=%s", processed, sends)
    return {"ok": True, "processed": processed, "sends_enqueued": sends}


def enqueue_journey_cron_jobs() -> dict[str, Any]:
    from datetime import datetime, timezone

    from ptt_email.triggers import process_pending_trigger_events

    minute = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    try:
        from ptt_jobs.enqueue import enqueue_job

        scan = enqueue_job("email_journey_enroll_scan", {}, f"email_journey_enroll_scan:{minute}")
        tick = enqueue_job("email_journey_tick", {}, f"email_journey_tick:{minute}")
        triggers = enqueue_job("email_journey_trigger_events", {}, f"email_journey_trigger_events:{minute}")
        return {"ok": True, "mode": "queue", "scan": scan, "tick": tick, "triggers": triggers}
    except Exception as exc:
        logger.warning("enqueue_journey_cron_jobs inline fallback: %s", exc)
        scan_out = scan_segment_enter_enrollments()
        tick_out = tick_due_enrollments()
        trigger_out = process_pending_trigger_events()
        return {"ok": True, "mode": "inline", "scan": scan_out, "tick": tick_out, "triggers": trigger_out}
