"""Deliverability automation — bounce/complaint scan, auto-pause, alerts (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.config import email_complaint_pause_pct, email_deliverability_alerts_enabled

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def process_pending_suppressions(*, hours: int = 24) -> dict[str, Any]:
    """Ensure bounce/complaint engagement events have suppression entries."""
    from ptt_jobs.db import pg_connection

    processed = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ee.id::text, ee.client_id::text, ee.send_id::text, ee.event_type,
                       ct.email_normalized
                FROM {SCHEMA}.engagement_events ee
                JOIN {SCHEMA}.contacts ct ON ct.id = ee.contact_id
                WHERE ee.event_type IN ('bounce_hard', 'complaint', 'unsubscribe')
                  AND ee.occurred_at >= NOW() - (%s || ' hours')::interval
                """,
                (max(1, hours),),
            )
            for _eid, client_id, send_id, event_type, email_norm in cur.fetchall():
                reason = {
                    "bounce_hard": "hard_bounce",
                    "complaint": "complaint",
                    "unsubscribe": "unsubscribe",
                }[event_type]
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.suppression_entries
                      (client_id, email_normalized, reason, scope, source_send_id, created_by)
                    SELECT %s::uuid, %s, %s, 'client', %s::uuid, 'deliverability_scan'
                    WHERE NOT EXISTS (
                      SELECT 1 FROM {SCHEMA}.suppression_entries se
                      WHERE se.client_id = %s::uuid AND se.email_normalized = %s
                        AND se.reason = %s AND se.expires_at IS NULL
                    )
                    """,
                    (client_id, email_norm, reason, send_id, client_id, email_norm, reason),
                )
                if cur.rowcount:
                    processed += 1
                if event_type == "bounce_hard" and send_id:
                    cur.execute(
                        f"UPDATE {SCHEMA}.send_queue SET status = 'bounced' WHERE id = %s::uuid",
                        (send_id,),
                    )
        conn.commit()
    return {"ok": True, "suppressions_added": processed}


def scan_complaint_rates(*, days: int = 1) -> dict[str, Any]:
    """Pause domains exceeding complaint threshold; optional Slack alert."""
    from ptt_jobs.db import pg_connection

    threshold = email_complaint_pause_pct()
    paused: list[str] = []
    alerts: list[dict[str, Any]] = []

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT d.id::text, d.domain, d.client_id::text,
                       COUNT(*) FILTER (WHERE sq.status IN ('sent','delivered')) AS sent,
                       COUNT(*) FILTER (WHERE ee.event_type = 'complaint') AS complaints
                FROM {SCHEMA}.domains d
                LEFT JOIN {SCHEMA}.send_queue sq ON sq.client_id = d.client_id
                  AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - (%s || ' days')::interval
                LEFT JOIN {SCHEMA}.engagement_events ee ON ee.client_id = d.client_id
                  AND ee.event_type = 'complaint'
                  AND ee.occurred_at >= NOW() - (%s || ' days')::interval
                WHERE d.status = 'active'
                GROUP BY d.id, d.domain, d.client_id
                HAVING COUNT(*) FILTER (WHERE sq.status IN ('sent','delivered')) > 0
                """,
                (max(1, days), max(1, days)),
            )
            for domain_id, domain, client_id, sent, complaints in cur.fetchall():
                sent_n = int(sent or 0)
                comp_n = int(complaints or 0)
                if sent_n <= 0:
                    continue
                rate = 100.0 * comp_n / sent_n
                if rate >= threshold:
                    cur.execute(
                        f"UPDATE {SCHEMA}.domains SET status = 'paused' WHERE id = %s::uuid",
                        (domain_id,),
                    )
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.audit_log (client_id, actor, action, entity_type, entity_id, after_json)
                        VALUES (%s::uuid, 'deliverability_scan', 'domain_auto_paused', 'domain', %s::uuid, %s::jsonb)
                        """,
                        (
                            client_id,
                            domain_id,
                            __import__("json").dumps({"complaint_rate_pct": round(rate, 3), "domain": domain}),
                        ),
                    )
                    paused.append(domain)
                    alerts.append({"domain": domain, "client_id": client_id, "complaint_rate_pct": round(rate, 3)})
        conn.commit()

    if alerts and email_deliverability_alerts_enabled():
        _notify_deliverability(alerts)

    return {"ok": True, "paused_domains": paused, "alerts": alerts}


def run_deliverability_scan(*, hours: int = 24) -> dict[str, Any]:
    suppress = process_pending_suppressions(hours=hours)
    rates = scan_complaint_rates(days=1)
    return {"ok": True, "suppression": suppress, "complaint_scan": rates}


def _notify_deliverability(alerts: list[dict[str, Any]]) -> None:
    try:
        from ptt_seo.slack_notify import notify_slack_for_alert

        for alert in alerts:
            notify_slack_for_alert(
                alert_type="email_deliverability",
                message=(
                    f"Complaint rate {alert.get('complaint_rate_pct')}% on {alert.get('domain')} "
                    f"— domain auto-paused"
                ),
                link="/email/deliverability",
            )
    except Exception as exc:
        logger.debug("slack deliverability alert: %s", exc)
    try:
        from ptt_agency.notifications import notify_agency_ops

        for alert in alerts:
            notify_agency_ops(
                recipient_id="admin",
                title=f"Deliverability alert — {alert.get('domain')}",
                body=f"Complaint rate {alert.get('complaint_rate_pct')}% — domain paused",
                category="email_deliverability",
                link_url="/email/deliverability",
                meta=alert,
                slack_prefix=":rotating_light: [Email Deliverability]",
            )
    except Exception as exc:
        logger.debug("agency notify deliverability: %s", exc)
