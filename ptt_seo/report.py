"""Reporting dashboards (Spec 6.10 Phase 3)."""
from __future__ import annotations

import sqlite3
from typing import Any

from ptt_seo.connectors.gsc import gsc_daily_trend, gsc_summary, list_sync_runs
from ptt_seo.content import count_by_status
from ptt_seo.technical import count_open_critical, severity_matrix


def _aeo_coverage(conn: Any, customer_id: int) -> dict[str, Any]:
    try:
        from ptt_seo.aeo import aeo_coverage_summary

        return aeo_coverage_summary(customer_id)
    except Exception:
        return {"total": 0, "visible": 0, "coverage_pct": 0.0}


def dashboard(
    conn: sqlite3.Connection,
    *,
    customer_id: int | None = None,
    dashboard_type: str = "executive",
) -> dict[str, Any]:
    cid_filter = customer_id
    base: dict[str, Any] = {"type": dashboard_type, "customer_id": customer_id}

    if dashboard_type == "executive":
        gsc = gsc_summary(conn, cid_filter) if cid_filter else _aggregate_gsc(conn)
        gsc_trend = gsc_daily_trend(conn, days=28, customer_id=cid_filter) if cid_filter else []
        authority = {}
        attribution = {}
        if cid_filter:
            try:
                from ptt_seo.authority import authority_summary

                authority = authority_summary(conn, cid_filter)
            except Exception:
                authority = {}
            try:
                from ptt_seo.attribution import (
                    organic_attribution_summary,
                    top_organic_landing_pages,
                )

                attribution = {
                    "summary": organic_attribution_summary(conn, cid_filter, days=28),
                    "top_pages": top_organic_landing_pages(conn, cid_filter, days=28, limit=10),
                }
            except Exception:
                attribution = {}
        return {
            **base,
            "days": 28,
            "gsc": gsc,
            "gsc_trend": gsc_trend,
            "authority": authority,
            "attribution": attribution,
            "critical_issues": count_open_critical(conn, cid_filter),
            "content_by_status": _aggregate_content(conn, cid_filter),
            "aeo": _aeo_coverage(conn, cid_filter) if cid_filter else {"coverage_pct": 0},
            "sync_runs_recent": list_sync_runs(conn, cid_filter, limit=5),
        }

    if dashboard_type == "seo":
        trend = gsc_daily_trend(conn, days=28, customer_id=cid_filter) if cid_filter else []
        attribution = {}
        if cid_filter:
            try:
                from ptt_seo.attribution import (
                    organic_attribution_summary,
                    top_organic_landing_pages,
                )

                attribution = {
                    "summary": organic_attribution_summary(conn, cid_filter, days=28),
                    "top_pages": top_organic_landing_pages(conn, cid_filter, days=28, limit=10),
                }
            except Exception:
                attribution = {}
        return {
            **base,
            "days": 28,
            "gsc": gsc_summary(conn, cid_filter) if cid_filter else _aggregate_gsc(conn),
            "gsc_trend": trend,
            "attribution": attribution,
        }

    if dashboard_type == "content":
        by_status = count_by_status(conn, cid_filter) if cid_filter else _aggregate_content(conn, None)
        return {
            **base,
            "content_by_status": by_status,
            "content_chart": [{"label": k, "value": v} for k, v in by_status.items()],
        }

    if dashboard_type == "technical":
        if not cid_filter:
            return {**base, "severity": {"critical": count_open_critical(conn)}, "issues": []}
        rows = conn.execute(
            """
            SELECT id, url, issue_type, severity, status FROM seo_technical_issues
            WHERE customer_id = ? AND status NOT IN ('closed','verified')
            ORDER BY id DESC LIMIT 20
            """,
            (cid_filter,),
        ).fetchall()
        sev = severity_matrix(conn, cid_filter)
        return {
            **base,
            "severity": sev,
            "severity_chart": [
                {"label": k, "value": int(sev.get(k, 0))}
                for k in ("critical", "high", "medium", "low")
            ],
            "issues": [dict(r) for r in rows],
        }

    if dashboard_type == "aeo":
        cov = _aeo_coverage(conn, cid_filter) if cid_filter else {"coverage_pct": 0}
        mentions: list[dict[str, Any]] = []
        if cid_filter:
            try:
                from ptt_seo.aeo import list_mention_trends

                mentions = list_mention_trends(cid_filter, days=30)[:10]
            except Exception:
                mentions = []
        return {**base, "aeo": cov, "mentions_recent": mentions}

    if dashboard_type == "ops":
        return {
            **base,
            "content_by_status": count_by_status(conn, cid_filter) if cid_filter else _aggregate_content(conn, None),
            "sync_runs": list_sync_runs(conn, cid_filter, limit=10),
            "open_alerts": conn.execute(
                "SELECT COUNT(*) AS c FROM seo_alerts WHERE status = 'open'"
            ).fetchone()["c"],
        }

    return base


def _aggregate_gsc(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(clicks),0) AS clicks, COALESCE(SUM(impressions),0) AS impressions
        FROM seo_gsc_daily_stats
        WHERE stat_date >= date('now', '-28 days')
        """
    ).fetchone()
    clicks = int(row["clicks"] or 0) if row else 0
    impressions = int(row["impressions"] or 0) if row else 0
    return {
        "clicks": clicks,
        "impressions": impressions,
        "avg_ctr": round(clicks / impressions, 4) if impressions else 0.0,
    }


def _aggregate_content(conn: sqlite3.Connection, customer_id: int | None) -> dict[str, int]:
    if customer_id:
        return count_by_status(conn, customer_id)
    rows = conn.execute(
        """
        SELECT workflow_status, COUNT(*) AS c FROM seo_content
        WHERE workflow_status != 'archived' GROUP BY workflow_status
        """
    ).fetchall()
    return {str(r["workflow_status"]): int(r["c"]) for r in rows}
