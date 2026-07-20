"""Scheduled SEO/AEO report delivery (P2 + P3f polish)."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

CADENCES = ("weekly", "monthly")
DASHBOARD_TYPES = ("executive", "seo", "content", "technical", "ops")
SEO_REPORT_TZ = "Asia/Ho_Chi_Minh"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _today_local() -> date:
    try:
        return datetime.now(ZoneInfo(SEO_REPORT_TZ)).date()
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


def _normalize_schedule_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["recipient_emails"] = _loads_emails(item.pop("recipient_emails_json", "[]"))
    item["cc_emails"] = _loads_emails(item.pop("cc_emails_json", "[]"))
    item["bcc_emails"] = _loads_emails(item.pop("bcc_emails_json", "[]"))
    return item


def build_report_email_html(
    *,
    customer_label: str,
    dashboard_type: str,
    report_date: str,
    summary: dict[str, Any] | None = None,
) -> str:
    summary = summary or {}
    gsc = summary.get("gsc") or {}
    rows = [
        ("Client", customer_label),
        ("Loại báo cáo", dashboard_type),
        ("Ngày báo cáo", report_date),
        ("Múi giờ", SEO_REPORT_TZ),
    ]
    if gsc:
        rows.extend(
            [
                ("GSC Clicks", str(gsc.get("clicks", "—"))),
                ("GSC Impressions", str(gsc.get("impressions", "—"))),
            ]
        )
    if summary.get("critical_issues") is not None:
        rows.append(("Critical issues", str(summary.get("critical_issues"))))
    if summary.get("aeo") and summary["aeo"].get("coverage_pct") is not None:
        rows.append(("AEO coverage", f"{summary['aeo']['coverage_pct']}%"))
    tr = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #e5e7eb;color:#6b7280'>{k}</td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #e5e7eb;font-weight:600'>{v}</td></tr>"
        for k, v in rows
    )
    return f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;color:#111827;line-height:1.5">
  <div style="max-width:560px;margin:0 auto;padding:24px">
    <p style="color:#2563eb;font-size:12px;font-weight:700;letter-spacing:.04em">PTT SEO/AEO OPS</p>
    <h2 style="margin:0 0 8px">Báo cáo tự động — {customer_label}</h2>
    <p style="color:#6b7280;margin:0 0 16px">Dashboard <strong>{dashboard_type}</strong> · PDF đính kèm</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;background:#f9fafb;border-radius:8px">{tr}</table>
    <p style="margin-top:20px;font-size:12px;color:#9ca3af">Email tự động từ PTTADS · Không trả lời email này.</p>
  </div>
</body></html>"""


def compute_next_run(
    *,
    cadence: str,
    day_of_week: int = 0,
    day_of_month: int = 1,
    from_date: date | None = None,
) -> str:
    """Return ISO date string for next scheduled run."""
    today = from_date or _today_local()
    cadence = (cadence or "weekly").lower()
    if cadence == "monthly":
        dom = max(1, min(28, int(day_of_month or 1)))
        candidate = date(today.year, today.month, dom)
        if candidate <= today:
            month = today.month + 1
            year = today.year
            if month > 12:
                month = 1
                year += 1
            candidate = date(year, month, dom)
        return candidate.isoformat()
    # weekly — day_of_week 0=Monday
    dow = int(day_of_week or 0) % 7
    days_ahead = (dow - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (today + timedelta(days=days_ahead)).isoformat()


def list_schedules(
    conn: sqlite3.Connection,
    customer_id: int | None = None,
    *,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_report_schedules WHERE 1=1"
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY customer_id, id DESC"
    rows = [_normalize_schedule_row(dict(r)) for r in conn.execute(sql, params).fetchall()]
    return rows


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM seo_report_schedules WHERE id = ?", (schedule_id,)
    ).fetchone()
    if row is None:
        return None
    return _normalize_schedule_row(dict(row))


def create_schedule(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    cadence = str(payload.get("cadence") or "weekly").lower()
    if cadence not in CADENCES:
        raise ValueError("cadence phải là weekly hoặc monthly")
    dtype = str(payload.get("dashboard_type") or "executive").lower()
    if dtype not in DASHBOARD_TYPES:
        raise ValueError("dashboard_type không hợp lệ")
    emails = payload.get("recipient_emails") or []
    cc_emails = payload.get("cc_emails") or []
    bcc_emails = payload.get("bcc_emails") or []
    if not isinstance(emails, list) or not any(str(e).strip() for e in emails):
        raise ValueError("Cần ít nhất một email nhận báo cáo")
    ts = _ts()
    next_run = compute_next_run(
        cadence=cadence,
        day_of_week=int(payload.get("day_of_week") or 0),
        day_of_month=int(payload.get("day_of_month") or 1),
    )
    cur = conn.execute(
        """
        INSERT INTO seo_report_schedules (
            customer_id, dashboard_type, cadence, day_of_week, day_of_month,
            recipient_emails_json, cc_emails_json, bcc_emails_json,
            active, next_run_at, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            dtype,
            cadence,
            int(payload.get("day_of_week") or 0),
            int(payload.get("day_of_month") or 1),
            json.dumps([str(e).strip() for e in emails if str(e).strip()], ensure_ascii=False),
            json.dumps([str(e).strip() for e in cc_emails if str(e).strip()], ensure_ascii=False),
            json.dumps([str(e).strip() for e in bcc_emails if str(e).strip()], ensure_ascii=False),
            1 if payload.get("active", True) else 0,
            next_run,
            ts,
            ts,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_schedule(conn: sqlite3.Connection, schedule_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    row = get_schedule(conn, schedule_id)
    if row is None:
        raise ValueError("Schedule không tồn tại")
    cadence = str(payload.get("cadence") or row["cadence"]).lower()
    dtype = str(payload.get("dashboard_type") or row["dashboard_type"]).lower()
    emails = payload.get("recipient_emails", row["recipient_emails"])
    cc_emails = payload.get("cc_emails", row.get("cc_emails") or [])
    bcc_emails = payload.get("bcc_emails", row.get("bcc_emails") or [])
    active = payload.get("active", row["active"])
    dow = int(payload.get("day_of_week", row["day_of_week"]))
    dom = int(payload.get("day_of_month", row["day_of_month"]))
    next_run = compute_next_run(cadence=cadence, day_of_week=dow, day_of_month=dom)
    conn.execute(
        """
        UPDATE seo_report_schedules SET
            dashboard_type=?, cadence=?, day_of_week=?, day_of_month=?,
            recipient_emails_json=?, cc_emails_json=?, bcc_emails_json=?,
            active=?, next_run_at=?, updated_at=?
        WHERE id=?
        """,
        (
            dtype,
            cadence,
            dow,
            dom,
            json.dumps([str(e).strip() for e in emails if str(e).strip()], ensure_ascii=False),
            json.dumps([str(e).strip() for e in cc_emails if str(e).strip()], ensure_ascii=False),
            json.dumps([str(e).strip() for e in bcc_emails if str(e).strip()], ensure_ascii=False),
            1 if active else 0,
            next_run,
            _ts(),
            schedule_id,
        ),
    )
    conn.commit()
    return get_schedule(conn, schedule_id) or {}


def delete_schedule(conn: sqlite3.Connection, schedule_id: int) -> bool:
    cur = conn.execute("DELETE FROM seo_report_schedules WHERE id = ?", (schedule_id,))
    conn.commit()
    return int(cur.rowcount or 0) > 0


def list_due_schedules(conn: sqlite3.Connection, *, as_of: str | None = None) -> list[dict[str, Any]]:
    today = as_of or _today_local().isoformat()
    rows = conn.execute(
        """
        SELECT * FROM seo_report_schedules
        WHERE active = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
        ORDER BY next_run_at ASC, id ASC
        """,
        (today,),
    ).fetchall()
    return [_normalize_schedule_row(dict(r)) for r in rows]


def run_schedule(
    conn: sqlite3.Connection,
    schedule_id: int,
    *,
    crm_conn: Any | None = None,
) -> dict[str, Any]:
    schedule = get_schedule(conn, schedule_id)
    if schedule is None:
        raise ValueError("Schedule không tồn tại")
    ts = _ts()
    run_id_row = conn.execute(
        """
        INSERT INTO seo_report_schedule_runs (schedule_id, status, created_at)
        VALUES (?, 'running', ?)
        """,
        (schedule_id, ts),
    )
    run_id = int(run_id_row.lastrowid)
    conn.commit()

    customer_id = int(schedule["customer_id"])
    dtype = str(schedule["dashboard_type"])
    label = f"Client #{customer_id}"
    if crm_conn is not None:
        cu = crm_conn.execute(
            "SELECT name FROM crm_customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if cu:
            label = cu["name"] if isinstance(cu, dict) else cu[0]

    try:
        from ptt_seo.report import dashboard
        from ptt_seo.report_export import build_dashboard_pdf
        from ptt_seo.notify import send_email_with_attachment, smtp_configured

        data = dashboard(conn, customer_id=customer_id, dashboard_type=dtype)
        try:
            pdf_buf, filename = build_dashboard_pdf(data, customer_label=label)
        except RuntimeError as exc:
            pdf_buf, filename = None, ""
            mail_result = {"ok": True, "skipped": True, "error": str(exc)}
        else:
            report_date = _today_local().isoformat()
            subject = f"SEO/AEO Report — {label} ({dtype})"
            plain = (
                f"Báo cáo SEO/AEO tự động ({dtype}).\n"
                f"Client: {label}\n"
                f"Ngày: {report_date} ({SEO_REPORT_TZ})\n"
            )
            html = build_report_email_html(
                customer_label=label,
                dashboard_type=dtype,
                report_date=report_date,
                summary=data,
            )
            if smtp_configured() and pdf_buf is not None:
                mail_result = send_email_with_attachment(
                    schedule["recipient_emails"],
                    subject,
                    plain,
                    cc_addrs=schedule.get("cc_emails") or [],
                    bcc_addrs=schedule.get("bcc_emails") or [],
                    html_body=html,
                    attachment=pdf_buf,
                    attachment_name=filename,
                )
            else:
                mail_result = {"ok": True, "skipped": True, "error": "smtp_not_configured"}

        next_run = compute_next_run(
            cadence=schedule["cadence"],
            day_of_week=int(schedule["day_of_week"]),
            day_of_month=int(schedule["day_of_month"]),
        )
        sent_ts = _ts()
        conn.execute(
            """
            UPDATE seo_report_schedules
            SET last_sent_at=?, next_run_at=?, updated_at=?
            WHERE id=?
            """,
            (sent_ts, next_run, sent_ts, schedule_id),
        )
        status = "sent" if mail_result.get("ok") and not mail_result.get("skipped") else "skipped"
        err = "" if mail_result.get("ok") else str(mail_result.get("error") or "send_failed")
        conn.execute(
            """
            UPDATE seo_report_schedule_runs
            SET status=?, error_message=?, sent_at=?
            WHERE id=?
            """,
            (status, err, sent_ts if status == "sent" else None, run_id),
        )
        conn.commit()
        if not mail_result.get("ok") and not mail_result.get("skipped"):
            try:
                from ptt_seo.slack_notify import notify_slack_report_failed

                notify_slack_report_failed(
                    schedule_id=schedule_id,
                    customer_label=label,
                    dashboard_type=dtype,
                    error=err or "send_failed",
                )
            except Exception:
                pass
        return {
            "ok": True,
            "schedule_id": schedule_id,
            "run_id": run_id,
            "status": status,
            "mail": mail_result,
            "next_run_at": next_run,
        }
    except Exception as exc:
        err_msg = str(exc)[:500]
        conn.execute(
            """
            UPDATE seo_report_schedule_runs
            SET status='failed', error_message=?
            WHERE id=?
            """,
            (err_msg, run_id),
        )
        conn.commit()
        try:
            from ptt_seo.slack_notify import notify_slack_report_failed

            notify_slack_report_failed(
                schedule_id=schedule_id,
                customer_label=label,
                dashboard_type=dtype,
                error=err_msg,
            )
        except Exception:
            pass
        return {"ok": False, "schedule_id": schedule_id, "run_id": run_id, "error": str(exc)}


def run_due_schedules(conn: sqlite3.Connection, *, crm_conn: Any | None = None) -> dict[str, Any]:
    due = list_due_schedules(conn)
    results = []
    for s in due:
        results.append(run_schedule(conn, int(s["id"]), crm_conn=crm_conn))
    return {"ok": True, "processed": len(results), "results": results}


def enqueue_due_report_schedules() -> dict[str, Any]:
    from datetime import date as date_cls

    idem = f"seo_report_schedules:{date_cls.today().isoformat()}"
    payload: dict[str, Any] = {"as_of": date_cls.today().isoformat()}
    try:
        from ptt_jobs.enqueue import enqueue_job

        job = enqueue_job("seo_report_schedules", payload, idem)
        return {"ok": True, "mode": "queue", "job": job}
    except Exception:
        from ptt_seo.db import crm_connection, seo_write

        with crm_connection() as crm, seo_write() as seo:
            outcome = run_due_schedules(seo, crm_conn=crm)
        return {"ok": True, "mode": "inline", **outcome}


def process_seo_report_schedules_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from ptt_seo.db import crm_connection, seo_write

    with crm_connection() as crm, seo_write() as seo:
        return run_due_schedules(seo, crm_conn=crm)
