"""GSC connector — CSV import + sync runs (Spec 10.1 Phase 3)."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _start_sync_run(conn: sqlite3.Connection, customer_id: int, source: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_sync_runs (customer_id, source, status, started_at)
        VALUES (?,?,?,?)
        """,
        (customer_id, source, "running", _ts()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _finish_sync_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ok: bool,
    rows: int = 0,
    error: str = "",
) -> None:
    conn.execute(
        """
        UPDATE seo_sync_runs SET status=?, finished_at=?, rows_imported=?, error_message=?
        WHERE id=?
        """,
        ("done" if ok else "failed", _ts(), rows, error, run_id),
    )
    conn.commit()


def import_gsc_csv(
    conn: sqlite3.Connection,
    customer_id: int,
    csv_text: str,
    *,
    stat_date: str | None = None,
) -> dict[str, Any]:
    """Import Google Search Console export (Queries or Pages)."""
    run_id = _start_sync_run(conn, customer_id, "gsc_csv")
    date = (stat_date or datetime.utcnow().strftime("%Y-%m-%d"))[:10]
    reader = csv.DictReader(io.StringIO(csv_text))
    count = 0
    try:
        for row in reader:
            query = (row.get("Query") or row.get("query") or row.get("Top queries") or "").strip()
            page = (row.get("Page") or row.get("page") or row.get("Landing page") or "").strip()
            if not query and not page:
                continue
            clicks = int(float(row.get("Clicks") or row.get("clicks") or 0))
            impressions = int(float(row.get("Impressions") or row.get("impressions") or 0))
            ctr_raw = row.get("CTR") or row.get("ctr") or ""
            ctr = float(str(ctr_raw).replace("%", "") or 0)
            if ctr > 1:
                ctr = ctr / 100.0
            pos_raw = row.get("Position") or row.get("position") or row.get("Average position")
            position = float(pos_raw) if pos_raw not in (None, "") else None
            conn.execute(
                """
                INSERT INTO seo_gsc_daily_stats (
                    customer_id, stat_date, query, page, clicks, impressions, ctr, position, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(customer_id, stat_date, query, page) DO UPDATE SET
                    clicks=excluded.clicks,
                    impressions=excluded.impressions,
                    ctr=excluded.ctr,
                    position=excluded.position
                """,
                (customer_id, date, query, page, clicks, impressions, ctr, position, _ts()),
            )
            count += 1
        conn.commit()
        _finish_sync_run(conn, run_id, ok=True, rows=count)
        return {"ok": True, "run_id": run_id, "rows_imported": count, "stat_date": date}
    except Exception as exc:
        _finish_sync_run(conn, run_id, ok=False, error=str(exc))
        return {"ok": False, "run_id": run_id, "error": str(exc)}


def gsc_daily_trend(
    conn: sqlite3.Connection,
    *,
    days: int = 90,
    customer_id: int | None = None,
) -> list[dict[str, Any]]:
    """Daily clicks/impressions series for executive charts."""
    offset = max(1, days)
    sql = f"""
        SELECT stat_date AS date,
               COALESCE(SUM(clicks), 0) AS clicks,
               COALESCE(SUM(impressions), 0) AS impressions
        FROM seo_gsc_daily_stats
        WHERE stat_date >= date('now', '-{offset} days')
    """
    params: list[Any] = []
    if customer_id is not None:
        sql += " AND customer_id = ?"
        params.append(customer_id)
    sql += " GROUP BY stat_date ORDER BY stat_date ASC"
    rows = conn.execute(sql, params).fetchall()
    return [
        {
            "date": str(r["date"]),
            "clicks": int(r["clicks"] or 0),
            "impressions": int(r["impressions"] or 0),
        }
        for r in rows
    ]


def gsc_summary(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    days: int = 28,
) -> dict[str, Any]:
    offset = max(1, days)
    row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(clicks), 0) AS clicks,
            COALESCE(SUM(impressions), 0) AS impressions,
            COUNT(DISTINCT query) AS queries,
            COUNT(DISTINCT page) AS pages
        FROM seo_gsc_daily_stats
        WHERE customer_id = ?
          AND stat_date >= datetime('now', '-{offset} days')
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        return {"clicks": 0, "impressions": 0, "queries": 0, "pages": 0, "avg_ctr": 0.0}
    clicks = int(row["clicks"] or 0)
    impressions = int(row["impressions"] or 0)
    avg_ctr = round(clicks / impressions, 4) if impressions else 0.0
    return {
        "clicks": clicks,
        "impressions": impressions,
        "queries": int(row["queries"] or 0),
        "pages": int(row["pages"] or 0),
        "avg_ctr": avg_ctr,
    }


def list_sync_runs(conn: sqlite3.Connection, customer_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_sync_runs"
    params: list[Any] = []
    if customer_id is not None:
        sql += " WHERE customer_id = ?"
        params.append(customer_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        try:
            r["payload"] = json.loads(r.pop("payload_json", "{}") or "{}")
        except json.JSONDecodeError:
            r["payload"] = {}
    return rows


def get_gsc_credentials(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    row = conn.execute(
        "SELECT integrations_json FROM seo_client_settings WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    if row is None:
        return {}
    try:
        data = json.loads(row["integrations_json"] or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
