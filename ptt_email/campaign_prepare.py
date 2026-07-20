"""Populate send_queue after campaign approval (EM-6) + eligibility v2 (EM-10)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ptt_email.config import email_send_enabled
from ptt_email.eligibility import (
    contact_over_frequency_cap,
    in_quiet_hours,
    load_quiet_hours_rule,
    next_send_after_quiet_hours,
)
from ptt_email.experiments import resolve_subject_for_contact
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def prepare_campaign(campaign_id: str, *, client_id: str | None = None) -> dict[str, Any]:
    if not email_send_enabled():
        return {"ok": False, "error": "send_disabled", "skipped": True}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT cam.id::text, cam.client_id::text, cam.status, cam.segment_id::text,
                       cam.template_id::text, cam.audience_count, w.daily_send_cap,
                       w.frequency_cap_7d, w.timezone
                FROM {SCHEMA}.campaigns cam
                JOIN {SCHEMA}.workspaces w ON w.id = cam.workspace_id
                WHERE cam.id = %s::uuid
                """,
                (campaign_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "campaign_not_found"}
            (
                cam_id,
                cam_client_id,
                status,
                segment_id,
                template_id,
                _audience_count,
                daily_cap,
                frequency_cap_7d,
                workspace_tz,
            ) = row
            if client_id and str(cam_client_id) != str(client_id):
                return {"ok": False, "error": "client_mismatch"}
            if status not in {"approved", "scheduled"}:
                return {"ok": False, "error": "invalid_status", "status": status}

            if not segment_id:
                return {"ok": False, "error": "segment_required"}

            cur.execute(
                f"""
                SELECT sm.contact_id::text
                FROM {SCHEMA}.segment_members sm
                WHERE sm.segment_id = %s::uuid
                """,
                (segment_id,),
            )
            contact_ids = [str(r[0]) for r in cur.fetchall()]
            if not contact_ids:
                return {"ok": False, "error": "empty_segment"}

            cur.execute(
                f"""
                SELECT ct.id::text, ct.email_normalized,
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
                WHERE ct.id = ANY(%s::uuid[])
                """,
                (contact_ids,),
            )
            eligible_rows = [r for r in cur.fetchall() if not r[2] and r[3]]

            cur.execute(
                f"""
                SELECT subject_template, html_body, text_body
                FROM {SCHEMA}.templates WHERE id = %s::uuid
                """,
                (template_id,),
            )
            tmpl = cur.fetchone()
            if not tmpl:
                return {"ok": False, "error": "template_not_found"}
            subject_template, _html_body, _text_body = tmpl

            quiet_rule = load_quiet_hours_rule(cur)
            now = datetime.now(timezone.utc)
            defer_until = (
                next_send_after_quiet_hours(
                    now=now,
                    quiet_config=quiet_rule,
                    workspace_tz=str(workspace_tz or "Asia/Ho_Chi_Minh"),
                )
                if in_quiet_hours(
                    now=now,
                    quiet_config=quiet_rule,
                    workspace_tz=str(workspace_tz or "Asia/Ho_Chi_Minh"),
                )
                else now
            )

            enqueued = 0
            skipped = 0
            freq_skipped = 0
            cap = int(daily_cap or 10000)
            freq_cap = int(frequency_cap_7d or 0)

            for contact_id, _email_norm, _sup, _consent in eligible_rows:
                if enqueued >= cap:
                    skipped += 1
                    continue
                if freq_cap > 0 and contact_over_frequency_cap(cur, contact_id, freq_cap):
                    freq_skipped += 1
                    skipped += 1
                    continue
                cur.execute(
                    f"""
                    SELECT 1 FROM {SCHEMA}.send_queue
                    WHERE campaign_id = %s::uuid AND contact_id = %s::uuid
                      AND status NOT IN ('cancelled', 'failed')
                    LIMIT 1
                    """,
                    (cam_id, contact_id),
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                tracking_id = str(uuid.uuid4())
                import json

                subject_rendered, exp_meta = resolve_subject_for_contact(
                    campaign_id=cam_id,
                    contact_id=contact_id,
                    default_subject=subject_template,
                )
                personalization = json.dumps({"tracking_id": tracking_id, **exp_meta})
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.send_queue (
                      client_id, campaign_id, contact_id, status, subject_rendered,
                      personalization, tracking_id, esp_provider, scheduled_at
                    )
                    SELECT %s::uuid, %s::uuid, %s::uuid, 'pending', %s, %s::jsonb, %s::uuid,
                           w.esp_provider, %s
                    FROM {SCHEMA}.workspaces w
                    WHERE w.client_id = %s::uuid
                    LIMIT 1
                    """,
                    (
                        cam_client_id,
                        cam_id,
                        contact_id,
                        subject_rendered,
                        personalization,
                        tracking_id,
                        defer_until,
                        cam_client_id,
                    ),
                )
                enqueued += 1

            cur.execute(
                f"""
                UPDATE {SCHEMA}.campaigns
                SET status = 'sending', audience_count = %s, updated_at = NOW()
                WHERE id = %s::uuid
                """,
                (enqueued, cam_id),
            )
        conn.commit()

    logger.info(
        "campaign_prepare campaign=%s enqueued=%s skipped=%s freq_skipped=%s",
        campaign_id,
        enqueued,
        skipped,
        freq_skipped,
    )

    batch_job = None
    if enqueued > 0 and defer_until <= now:
        from ptt_jobs.enqueue import enqueue_job

        batch_job = enqueue_job(
            "email_send_batch",
            {"campaign_id": cam_id, "client_id": cam_client_id},
            f"email_send_batch:{cam_id}",
            client_id=str(cam_client_id),
        )

    return {
        "ok": True,
        "campaign_id": cam_id,
        "client_id": cam_client_id,
        "enqueued": enqueued,
        "skipped": skipped,
        "freq_skipped": freq_skipped,
        "deferred_until": defer_until.isoformat() if defer_until > now else None,
        "send_batch_job_id": batch_job.get("id") if batch_job else None,
    }
