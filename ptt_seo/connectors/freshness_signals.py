"""Freshness signals — GSC/GA4 traffic deltas per content URL (Phase 4B)."""
from __future__ import annotations

import sqlite3
from typing import Any


def content_url_path(item: dict[str, Any]) -> str:
    """Best-effort URL path for matching GSC page / GA4 landing_page."""
    import json

    slug = str(item.get("slug") or "").strip()
    brief = item.get("brief_json") or item.get("brief") or {}
    if isinstance(brief, str):
        try:
            brief = json.loads(brief or "{}")
        except json.JSONDecodeError:
            brief = {}
    if not isinstance(brief, dict):
        brief = {}
    url = str(brief.get("primary_url") or brief.get("url") or slug).strip()
    return url


def _sum_metric(
    conn: sqlite3.Connection,
    customer_id: int,
    url_path: str,
    *,
    table: str,
    page_col: str,
    metric_col: str,
    days_back_start: int,
    days_back_end: int,
) -> int:
    if not url_path:
        return 0
    like = f"%{url_path.strip('/')}%"
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM({metric_col}), 0) AS total
        FROM {table}
        WHERE customer_id = ?
          AND {page_col} LIKE ?
          AND stat_date >= date('now', ?)
          AND stat_date < date('now', ?)
        """,
        (
            customer_id,
            like,
            f"-{days_back_start} days",
            f"-{days_back_end} days",
        ),
    ).fetchone()
    return int(row["total"] or 0) if row else 0


def gsc_clicks_windows(
    conn: sqlite3.Connection,
    customer_id: int,
    url_path: str,
) -> tuple[int, int]:
    """Return (current_28d, previous_28d) click sums for URL path."""
    current = _sum_metric(
        conn,
        customer_id,
        url_path,
        table="seo_gsc_daily_stats",
        page_col="page",
        metric_col="clicks",
        days_back_start=28,
        days_back_end=0,
    )
    previous = _sum_metric(
        conn,
        customer_id,
        url_path,
        table="seo_gsc_daily_stats",
        page_col="page",
        metric_col="clicks",
        days_back_start=56,
        days_back_end=28,
    )
    return current, previous


def ga4_sessions_windows(
    conn: sqlite3.Connection,
    customer_id: int,
    url_path: str,
) -> tuple[int, int]:
    current = _sum_metric(
        conn,
        customer_id,
        url_path,
        table="seo_ga4_daily_stats",
        page_col="landing_page",
        metric_col="sessions",
        days_back_start=28,
        days_back_end=0,
    )
    previous = _sum_metric(
        conn,
        customer_id,
        url_path,
        table="seo_ga4_daily_stats",
        page_col="landing_page",
        metric_col="sessions",
        days_back_start=56,
        days_back_end=28,
    )
    return current, previous


def traffic_delta_pct(current: int, previous: int) -> float | None:
    if previous <= 0:
        return None
    return round(100.0 * (current - previous) / previous, 2)


def collect_signals(
    conn: sqlite3.Connection,
    customer_id: int,
    item: dict[str, Any],
) -> dict[str, Any]:
    url_path = content_url_path(item)
    gsc_cur, gsc_prev = gsc_clicks_windows(conn, customer_id, url_path)
    ga4_cur, ga4_prev = ga4_sessions_windows(conn, customer_id, url_path)
    combined_cur = gsc_cur + ga4_cur
    combined_prev = gsc_prev + ga4_prev
    delta = traffic_delta_pct(combined_cur, combined_prev)
    return {
        "url_path": url_path,
        "gsc_clicks_current": gsc_cur,
        "gsc_clicks_previous": gsc_prev,
        "ga4_sessions_current": ga4_cur,
        "ga4_sessions_previous": ga4_prev,
        "traffic_delta_pct": delta,
    }
