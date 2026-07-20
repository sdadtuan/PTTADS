"""GA4 connector — summary queries (Phase 4 OAuth sync)."""
from __future__ import annotations

import sqlite3
from typing import Any


def ga4_summary(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    days: int = 28,
) -> dict[str, Any]:
    d = max(1, days)
    row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(sessions), 0) AS sessions,
            COALESCE(SUM(users), 0) AS users,
            COALESCE(SUM(pageviews), 0) AS pageviews,
            COALESCE(SUM(conversions), 0) AS conversions,
            COALESCE(SUM(revenue), 0) AS revenue,
            COUNT(DISTINCT landing_page) AS landing_pages,
            AVG(bounce_rate) AS avg_bounce_rate
        FROM seo_ga4_daily_stats
        WHERE customer_id = ?
          AND stat_date >= date('now', '-{d} days')
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        return {
            "sessions": 0,
            "users": 0,
            "pageviews": 0,
            "conversions": 0.0,
            "revenue": 0.0,
            "landing_pages": 0,
            "avg_bounce_rate": 0.0,
        }
    return {
        "sessions": int(row["sessions"] or 0),
        "users": int(row["users"] or 0),
        "pageviews": int(row["pageviews"] or 0),
        "conversions": round(float(row["conversions"] or 0), 2),
        "revenue": round(float(row["revenue"] or 0), 2),
        "landing_pages": int(row["landing_pages"] or 0),
        "avg_bounce_rate": round(float(row["avg_bounce_rate"] or 0), 4),
    }
