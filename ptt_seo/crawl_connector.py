"""Scheduled crawl connector — webhook ingest + schedule (Gate E2)."""
from __future__ import annotations

import csv
import io
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_crawl_schedule(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM seo_crawl_schedules WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    return dict(row) if row else None


def upsert_crawl_schedule(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    existing = get_crawl_schedule(conn, customer_id)
    secret = str(payload.get("webhook_secret") or "").strip()
    if not secret and existing:
        secret = str(existing.get("webhook_secret") or "")
    if not secret:
        secret = secrets.token_urlsafe(24)
    freq = max(7, int(payload.get("frequency_days") or 30))
    active = 1 if payload.get("active", True) else 0
    conn.execute(
        """
        INSERT INTO seo_crawl_schedules (
            customer_id, frequency_days, webhook_secret, last_ingest_at, active, updated_at
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(customer_id) DO UPDATE SET
            frequency_days = excluded.frequency_days,
            webhook_secret = excluded.webhook_secret,
            active = excluded.active,
            updated_at = excluded.updated_at
        """,
        (
            customer_id,
            freq,
            secret,
            existing.get("last_ingest_at") if existing else None,
            active,
            _ts(),
        ),
    )
    conn.commit()
    result = get_crawl_schedule(conn, customer_id)
    assert result is not None
    return result


def verify_crawl_secret(conn: sqlite3.Connection, customer_id: int, secret: str) -> bool:
    row = get_crawl_schedule(conn, customer_id)
    if row is None or not row.get("active"):
        return False
    expected = str(row.get("webhook_secret") or "")
    return bool(expected and secrets.compare_digest(expected, secret.strip()))


def ingest_crawl_payload(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    csv_text: str | None = None,
    rows: list[dict[str, Any]] | None = None,
    crm_conn: Any | None = None,
) -> dict[str, Any]:
    """Accept CSV text or row dicts from external crawl tool."""
    from ptt_seo.technical import import_crawl_csv

    if csv_text:
        count = import_crawl_csv(conn, customer_id, csv_text, crm_conn=crm_conn)
    elif rows:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["url", "issue_type", "severity", "description"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "url": row.get("url") or "",
                    "issue_type": row.get("issue_type") or row.get("type") or "crawl",
                    "severity": row.get("severity") or "medium",
                    "description": row.get("description") or row.get("message") or "",
                }
            )
        count = import_crawl_csv(conn, customer_id, buf.getvalue(), crm_conn=crm_conn)
    else:
        raise ValueError("Thiếu csv_text hoặc rows")

    conn.execute(
        """
        UPDATE seo_crawl_schedules SET last_ingest_at = ?, updated_at = ?
        WHERE customer_id = ?
        """,
        (_ts(), _ts(), customer_id),
    )
    conn.commit()
    return {"ok": True, "rows_imported": count, "customer_id": customer_id}


def run_crawl_schedule_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    """Alert when scheduled crawl ingest is overdue."""
    from ptt_seo.automation import create_alert

    rows = conn.execute(
        "SELECT * FROM seo_crawl_schedules WHERE active = 1",
    ).fetchall()
    created: list[dict[str, Any]] = []
    now = datetime.utcnow()
    for row in rows:
        sched = dict(row)
        cid = int(sched["customer_id"])
        freq = int(sched.get("frequency_days") or 30)
        last = sched.get("last_ingest_at")
        if last:
            try:
                last_dt = datetime.strptime(str(last)[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                last_dt = None
        else:
            last_dt = None
        if last_dt and (now - last_dt).days < freq:
            continue
        msg = (
            f"Crawl connector quá hạn ({freq} ngày) — gửi export tới webhook"
            if last_dt
            else f"Chưa nhận crawl webhook — cấu hình Screaming Frog / Sitebulb push"
        )
        aid = create_alert(
            conn,
            customer_id=cid,
            alert_type="crawl_connector_due",
            severity="warn",
            message=msg,
            link=f"/crm/seo/technical?customer_id={cid}",
        )
        if aid:
            created.append({"alert_id": aid, "customer_id": cid})
    return {"ok": True, "due_alerts": len(created), "alerts": created}


def crawl_connector_enabled() -> bool:
    return os.getenv("PTT_CRAWL_CONNECTOR_ENABLED", "1").strip().lower() not in ("0", "false", "no")
