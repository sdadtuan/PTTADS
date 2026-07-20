"""Scheduled email client reports (Wave 2) — PG email_mkt.report_schedules."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ptt_seo.report_schedule import compute_next_run

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"
EMAIL_REPORT_TZ = "Asia/Ho_Chi_Minh"
REPORT_TYPES = ("executive", "campaign", "deliverability")


def _today_local() -> date:
    try:
        return datetime.now(ZoneInfo(EMAIL_REPORT_TZ)).date()
    except Exception:
        return date.today()


def _loads_emails(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    try:
        data = json.loads(raw or "[]")
        return [str(x).strip() for x in data if str(x).strip()] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def list_due_schedules(*, as_of: str | None = None) -> list[dict[str, Any]]:
    from ptt_jobs.db import pg_connection

    today = as_of or _today_local().isoformat()
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text, report_type, cadence, day_of_week, day_of_month,
                       recipient_emails_json, cc_emails_json, bcc_emails_json, next_run_at
                FROM {SCHEMA}.report_schedules
                WHERE active = TRUE AND next_run_at IS NOT NULL AND next_run_at <= %s::date
                ORDER BY next_run_at ASC
                """,
                (today,),
            )
            rows = []
            for r in cur.fetchall():
                rows.append(
                    {
                        "id": str(r[0]),
                        "client_id": str(r[1]),
                        "report_type": str(r[2]),
                        "cadence": str(r[3]),
                        "day_of_week": int(r[4] or 0),
                        "day_of_month": int(r[5] or 1),
                        "recipient_emails": _loads_emails(r[6]),
                        "cc_emails": _loads_emails(r[7]),
                        "bcc_emails": _loads_emails(r[8]),
                        "next_run_at": str(r[9]),
                    }
                )
    return rows


def _fetch_client_label(client_id: str) -> str:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM clients WHERE id = %s::uuid", (client_id,))
            row = cur.fetchone()
            return str(row[0]) if row else f"Client {client_id[:8]}"


def _build_summary(client_id: str, *, days: int = 28) -> dict[str, Any]:
    from ptt_email.attribution import email_attribution_summary, email_revenue_attributed
    from ptt_jobs.db import pg_connection

    summary = {"sent": 0, "opens": 0, "clicks": 0, "open_rate_pct": 0, "click_rate_pct": 0}
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {SCHEMA}.send_queue sq
                WHERE sq.client_id = %s::uuid AND sq.status IN ('sent','delivered')
                  AND COALESCE(sq.sent_at, sq.scheduled_at) >= NOW() - (%s || ' days')::interval
                """,
                (client_id, days),
            )
            sent = int(cur.fetchone()[0] or 0)
            summary["sent"] = sent
            for evt, key in (("open", "opens"), ("click", "clicks")):
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {SCHEMA}.engagement_events ee
                    WHERE ee.client_id = %s::uuid AND ee.event_type = %s
                      AND ee.occurred_at >= NOW() - (%s || ' days')::interval
                    """,
                    (client_id, evt, days),
                )
                summary[key] = int(cur.fetchone()[0] or 0)
            if sent > 0:
                summary["open_rate_pct"] = round(100.0 * summary["opens"] / sent, 2)
                summary["click_rate_pct"] = round(100.0 * summary["clicks"] / sent, 2)
            cur.execute(
                f"""
                SELECT COUNT(*) FILTER (WHERE ee.event_type IN ('bounce_hard','bounce_soft')),
                       COUNT(*) FILTER (WHERE ee.event_type = 'complaint')
                FROM {SCHEMA}.engagement_events ee
                WHERE ee.client_id = %s::uuid
                  AND ee.occurred_at >= NOW() - (%s || ' days')::interval
                """,
                (client_id, days),
            )
            bounces, complaints = cur.fetchone() or (0, 0)
            summary["bounce_rate_pct"] = round(100.0 * int(bounces or 0) / sent, 3) if sent else 0
            summary["complaint_rate_pct"] = round(100.0 * int(complaints or 0) / sent, 3) if sent else 0
    attr = email_attribution_summary(client_id, days=days)
    summary["revenue_attrib"] = attr.get("revenue_attrib") or email_revenue_attributed(client_id, days=days)
    return summary


def run_schedule(schedule_id: str) -> dict[str, Any]:
    from ptt_email.report_export import build_email_report_pdf
    from ptt_jobs.db import pg_connection
    from ptt_seo.notify import send_email_with_attachment

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text, report_type, cadence, day_of_week, day_of_month,
                       recipient_emails_json, cc_emails_json, bcc_emails_json
                FROM {SCHEMA}.report_schedules WHERE id = %s::uuid
                """,
                (schedule_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "schedule_not_found"}
            sid, client_id, report_type, cadence, dow, dom = (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                int(row[4] or 0),
                int(row[5] or 1),
            )
            recipients = _loads_emails(row[6])
            cc = _loads_emails(row[7])
            bcc = _loads_emails(row[8])
            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.report_schedule_runs (schedule_id, status)
                VALUES (%s::uuid, 'running') RETURNING id::text
                """,
                (sid,),
            )
            run_id = str(cur.fetchone()[0])
        conn.commit()

    label = _fetch_client_label(client_id)
    summary = _build_summary(client_id)
    try:
        pdf_buf, filename = build_email_report_pdf(summary, client_label=label, report_type=report_type)
        subject = f"[PTT Email] Báo cáo {report_type} — {label}"
        body = f"Báo cáo email marketing ({report_type}) cho {label}. PDF đính kèm."
        html = f"<p>{body}</p><p>Sent: {summary.get('sent')} · Opens: {summary.get('opens')} · Revenue attrib: {summary.get('revenue_attrib')}</p>"
        mail = send_email_with_attachment(
            recipients,
            subject,
            body,
            cc_addrs=cc,
            bcc_addrs=bcc,
            html_body=html,
            attachment=pdf_buf,
            attachment_name=filename,
        )
        if not mail.get("ok"):
            raise RuntimeError(str(mail.get("error") or "send_failed"))

        next_run = compute_next_run(cadence=cadence, day_of_week=dow, day_of_month=dom)
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {SCHEMA}.report_schedules
                    SET last_sent_at = NOW(), next_run_at = %s::date, updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (next_run, sid),
                )
                cur.execute(
                    f"""
                    UPDATE {SCHEMA}.report_schedule_runs
                    SET status = 'sent', finished_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (run_id,),
                )
            conn.commit()
        return {"ok": True, "schedule_id": sid, "run_id": run_id, "mail": mail}
    except Exception as exc:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {SCHEMA}.report_schedule_runs
                    SET status = 'failed', error_message = %s, finished_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (str(exc)[:500], run_id),
                )
            conn.commit()
        return {"ok": False, "error": str(exc), "schedule_id": sid, "run_id": run_id}


def run_due_schedules(*, as_of: str | None = None) -> dict[str, Any]:
    due = list_due_schedules(as_of=as_of)
    results = []
    for sched in due:
        results.append(run_schedule(sched["id"]))
    sent = sum(1 for r in results if r.get("ok"))
    return {"ok": True, "due": len(due), "sent": sent, "results": results}


def enqueue_due_report_schedules(*, as_of: str | None = None) -> dict[str, Any]:
    from ptt_jobs.enqueue import enqueue_job

    due = list_due_schedules(as_of=as_of)
    jobs = []
    for sched in due:
        jobs.append(
            enqueue_job(
                "email_report_schedules",
                {"schedule_id": sched["id"], "client_id": sched["client_id"]},
                f"email_report_schedule:{sched['id']}:{sched.get('next_run_at')}",
                client_id=sched["client_id"],
            )
        )
    return {"ok": True, "due": len(due), "jobs": jobs}
