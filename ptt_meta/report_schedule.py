"""Scheduled Meta client reports — public.meta_report_schedules (Prod-S2)."""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from ptt_jobs.channel_hub_fetch import fetch_meta_hub_for_client, portal_performance_link
from ptt_jobs.report_schedule_gate import check_channel_report_gate
from ptt_meta.report_export import build_meta_hub_pdf
from ptt_seo.notify import send_email_with_attachment
from ptt_seo.report_schedule import compute_next_run

logger = logging.getLogger(__name__)

SCHEDULE_TABLE = "meta_report_schedules"
RUNS_TABLE = "meta_report_schedule_runs"
REPORT_TZ = "Asia/Ho_Chi_Minh"


def _today_local() -> date:
    try:
        return datetime.now(ZoneInfo(REPORT_TZ)).date()
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
                SELECT id::text, client_id::text, report_scope, export_format, window_days,
                       cadence, day_of_week, day_of_month,
                       recipient_emails_json, cc_emails_json, bcc_emails_json,
                       portal_link_enabled, next_run_at
                FROM {SCHEDULE_TABLE}
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
                        "report_scope": str(r[2]),
                        "export_format": str(r[3]),
                        "window_days": int(r[4] or 7),
                        "cadence": str(r[5]),
                        "day_of_week": int(r[6] or 0),
                        "day_of_month": int(r[7] or 1),
                        "recipient_emails": _loads_emails(r[8]),
                        "cc_emails": _loads_emails(r[9]),
                        "bcc_emails": _loads_emails(r[10]),
                        "portal_link_enabled": bool(r[11]),
                        "next_run_at": str(r[12]),
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


def _build_attachment(hub: dict[str, Any], export_format: str, label: str) -> tuple[Any, str, str]:
    fmt = export_format.strip().lower()
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["client", "spend", "leads_crm", "cpl", "unmapped", "over_target"])
        for c in hub.get("clients") or []:
            writer.writerow(
                [
                    c.get("code") or c.get("name") or c.get("id"),
                    c.get("spend"),
                    c.get("leads_crm"),
                    c.get("cpl"),
                    c.get("unmapped_campaigns"),
                    c.get("over_target_rows"),
                ]
            )
        content = buf.getvalue().encode("utf-8")
        filename = f"meta-hub-{hub.get('date_from')}_{hub.get('date_to')}.csv"
        return io.BytesIO(content), filename, "text/csv"
    pdf_buf, filename = build_meta_hub_pdf(hub, customer_label=label)
    return pdf_buf, filename, "application/pdf"


def run_schedule(schedule_id: str) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text, report_scope, export_format, window_days,
                       cadence, day_of_week, day_of_month,
                       recipient_emails_json, cc_emails_json, bcc_emails_json, portal_link_enabled
                FROM {SCHEDULE_TABLE} WHERE id = %s::uuid
                """,
                (schedule_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "schedule_not_found"}
            schedule = {
                "id": str(row[0]),
                "client_id": str(row[1]),
                "report_scope": str(row[2]),
                "export_format": str(row[3]),
                "window_days": int(row[4] or 7),
                "cadence": str(row[5]),
                "day_of_week": int(row[6] or 0),
                "day_of_month": int(row[7] or 1),
                "recipient_emails": _loads_emails(row[8]),
                "cc_emails": _loads_emails(row[9]),
                "bcc_emails": _loads_emails(row[10]),
                "portal_link_enabled": bool(row[11]),
            }
            cur.execute(
                f"INSERT INTO {RUNS_TABLE} (schedule_id, status) VALUES (%s::uuid, 'running') RETURNING id::text",
                (schedule_id,),
            )
            run_id = str(cur.fetchone()[0])
        conn.commit()

    gate = check_channel_report_gate(
        channel="meta",
        client_id=schedule["client_id"],
        window_days=schedule["window_days"],
    )
    if not gate.get("ok"):
        _finish_run(run_id, schedule_id, schedule, status="skipped", error=gate.get("reason"))
        return {"ok": True, "skipped": True, "reason": gate.get("reason"), "gate": gate}

    label = _fetch_client_label(schedule["client_id"])
    hub = fetch_meta_hub_for_client(client_id=schedule["client_id"], window_days=schedule["window_days"])
    if not hub.get("ok", True):
        _finish_run(run_id, schedule_id, schedule, status="failed", error=hub.get("error"))
        return {"ok": False, "error": hub.get("error")}

    try:
        attachment, filename, _mime = _build_attachment(hub, schedule["export_format"], label)
        portal_link = ""
        if schedule["portal_link_enabled"]:
            portal_link = portal_performance_link(schedule["client_id"], "meta")
        subject = f"[PTT Meta] Báo cáo {schedule['export_format'].upper()} — {label}"
        body = f"Báo cáo Meta Ads cho {label} ({hub.get('date_from')} → {hub.get('date_to')})."
        if portal_link:
            body += f"\n\nXem live trên portal: {portal_link}"
        html = f"<p>{body.replace(chr(10), '<br/>')}</p>"
        mail = send_email_with_attachment(
            schedule["recipient_emails"],
            subject,
            body,
            cc_addrs=schedule["cc_emails"],
            bcc_addrs=schedule["bcc_emails"],
            html_body=html,
            attachment=attachment,
            attachment_name=filename,
        )
        if not mail.get("ok"):
            raise RuntimeError(str(mail.get("error") or "send_failed"))
        _finish_run(run_id, schedule_id, schedule, status="sent")
        return {"ok": True, "schedule_id": schedule_id, "run_id": run_id, "mail": mail}
    except Exception as exc:
        logger.exception("meta report schedule failed: %s", exc)
        _finish_run(run_id, schedule_id, schedule, status="failed", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _finish_run(
    run_id: str,
    schedule_id: str,
    schedule: dict[str, Any],
    *,
    status: str,
    error: str | None = None,
) -> None:
    from ptt_jobs.db import pg_connection

    next_run = compute_next_run(
        cadence=schedule["cadence"],
        day_of_week=schedule["day_of_week"],
        day_of_month=schedule["day_of_month"],
    )
    with pg_connection() as conn:
        with conn.cursor() as cur:
            if status == "sent":
                cur.execute(
                    f"""
                    UPDATE {SCHEDULE_TABLE}
                    SET last_sent_at = NOW(), next_run_at = %s::date, updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (next_run, schedule_id),
                )
            cur.execute(
                f"""
                UPDATE {RUNS_TABLE}
                SET status = %s, error_message = %s, finished_at = NOW()
                WHERE id = %s::uuid
                """,
                (status, (error or "")[:500] or None, run_id),
            )
        conn.commit()


def run_due_schedules(*, as_of: str | None = None) -> dict[str, Any]:
    due = list_due_schedules(as_of=as_of)
    results = []
    for item in due:
        results.append(run_schedule(item["id"]))
    return {"ok": True, "count": len(due), "results": results}
