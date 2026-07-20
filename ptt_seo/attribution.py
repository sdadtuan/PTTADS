"""Organic revenue attribution from GA4 daily stats (Gate E7)."""
from __future__ import annotations

import sqlite3
from typing import Any


def _organic_filter_sql() -> str:
    return """
        (
            LOWER(source_medium) LIKE '%organic%'
            OR LOWER(source_medium) = 'google / organic'
            OR LOWER(source_medium) LIKE 'google / organic%'
        )
    """


def _days_filter_sql(days: int) -> str:
    d = max(1, days)
    return f"stat_date >= date('now', '-{d} days')"


def organic_revenue_total(conn: sqlite3.Connection, customer_id: int, *, days: int = 28) -> float:
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(revenue), 0) AS total
        FROM seo_ga4_daily_stats
        WHERE customer_id = ?
          AND {_days_filter_sql(days)}
          AND {_organic_filter_sql()}
        """,
        (customer_id,),
    ).fetchone()
    return float(row["total"] or 0) if row else 0.0


def organic_attribution_summary(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    days: int = 28,
) -> dict[str, Any]:
    row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(sessions), 0) AS sessions,
            COALESCE(SUM(users), 0) AS users,
            COALESCE(SUM(conversions), 0) AS conversions,
            COALESCE(SUM(revenue), 0) AS revenue,
            COUNT(DISTINCT landing_page) AS landing_pages
        FROM seo_ga4_daily_stats
        WHERE customer_id = ?
          AND {_days_filter_sql(days)}
          AND {_organic_filter_sql()}
        """,
        (customer_id,),
    ).fetchone()
    if row is None:
        return {
            "customer_id": customer_id,
            "days": days,
            "sessions": 0,
            "users": 0,
            "conversions": 0.0,
            "revenue": 0.0,
            "landing_pages": 0,
            "revenue_per_session": 0.0,
            "conversion_rate": 0.0,
        }
    sessions = int(row["sessions"] or 0)
    revenue = float(row["revenue"] or 0)
    conversions = float(row["conversions"] or 0)
    return {
        "customer_id": customer_id,
        "days": days,
        "sessions": sessions,
        "users": int(row["users"] or 0),
        "conversions": round(conversions, 2),
        "revenue": round(revenue, 2),
        "landing_pages": int(row["landing_pages"] or 0),
        "revenue_per_session": round(revenue / sessions, 4) if sessions else 0.0,
        "conversion_rate": round(conversions / sessions, 4) if sessions else 0.0,
    }


def top_organic_landing_pages(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    days: int = 28,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT
            landing_page,
            COALESCE(SUM(sessions), 0) AS sessions,
            COALESCE(SUM(revenue), 0) AS revenue,
            COALESCE(SUM(conversions), 0) AS conversions
        FROM seo_ga4_daily_stats
        WHERE customer_id = ?
          AND {_days_filter_sql(days)}
          AND {_organic_filter_sql()}
          AND landing_page != ''
        GROUP BY landing_page
        ORDER BY revenue DESC, sessions DESC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        sessions = int(r["sessions"] or 0)
        revenue = float(r["revenue"] or 0)
        conversions = float(r["conversions"] or 0)
        out.append(
            {
                "landing_page": r["landing_page"],
                "sessions": sessions,
                "revenue": round(revenue, 2),
                "conversions": round(conversions, 2),
                "revenue_per_session": round(revenue / sessions, 4) if sessions else 0.0,
            }
        )
    return out
