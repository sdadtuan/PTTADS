"""Crawl import tracking + stale crawl reminders (Gate D)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def record_crawl_import(conn: sqlite3.Connection, customer_id: int, rows_imported: int) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_crawl_import_log (customer_id, rows_imported, imported_at)
        VALUES (?,?,?)
        """,
        (customer_id, max(0, int(rows_imported)), _ts()),
    )
    conn.commit()
    return int(cur.lastrowid)


def last_crawl_import_at(conn: sqlite3.Connection, customer_id: int) -> str | None:
    row = conn.execute(
        """
        SELECT imported_at FROM seo_crawl_import_log
        WHERE customer_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    return str(row["imported_at"]) if row and row["imported_at"] else None


def run_crawl_reminders(
    conn: sqlite3.Connection,
    *,
    max_age_days: int = 30,
) -> dict[str, Any]:
    """Alert clients with no crawl CSV import in N days."""
    from ptt_seo.automation import create_alert

    cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """
        SELECT DISTINCT customer_id FROM seo_client_settings
        UNION SELECT DISTINCT customer_id FROM seo_technical_issues
        """
    ).fetchall()
    created: list[dict[str, Any]] = []
    for row in rows:
        cid = int(row["customer_id"])
        last = last_crawl_import_at(conn, cid)
        if last and last >= cutoff:
            continue
        msg = (
            f"Chưa import crawl CSV trong {max_age_days} ngày"
            if last
            else f"Chưa từng import crawl CSV — upload Screaming Frog export"
        )
        aid = create_alert(
            conn,
            customer_id=cid,
            alert_type="crawl_stale",
            severity="warn",
            message=msg,
            link=f"/crm/seo/technical?customer_id={cid}",
        )
        if aid:
            created.append({"alert_id": aid, "customer_id": cid})
    return {"ok": True, "reminders": len(created), "alerts": created}
