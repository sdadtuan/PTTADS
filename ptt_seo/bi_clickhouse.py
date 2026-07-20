"""SEO daily facts → ClickHouse (Phase 5D / enterprise BI)."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def _ch_request(sql: str, *, data: bytes | None = None) -> str:
    from ptt_analytics.clickhouse_export import _auth_header, _clickhouse_endpoint

    base, _, _ = _clickhouse_endpoint()
    url = f"{base}/?query={sql}"
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    headers.update(_auth_header())
    import urllib.request

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def ensure_seo_facts_schema(*, ddl_path: str | None = None) -> dict[str, Any]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = Path(ddl_path) if ddl_path else root / "deploy/clickhouse/init-seo-daily-facts.sql"
    if not path.is_file():
        return {"ok": False, "error": "ddl_missing"}
    ddl = path.read_text(encoding="utf-8")
    try:
        _ch_request(ddl)
        return {"ok": True}
    except Exception as exc:
        logger.warning("ensure_seo_facts_schema: %s", exc)
        return {"ok": False, "error": str(exc)}


def collect_daily_facts(conn: sqlite3.Connection, *, fact_date: str | None = None) -> list[dict[str, Any]]:
    d = fact_date or date.today().isoformat()
    facts: list[dict[str, Any]] = []
    customer_rows = conn.execute(
        """
        SELECT DISTINCT customer_id FROM (
            SELECT customer_id FROM seo_content WHERE workflow_status != 'archived'
            UNION SELECT customer_id FROM seo_keywords WHERE status = 'active'
            UNION SELECT customer_id FROM seo_questions WHERE status = 'active'
            UNION SELECT customer_id FROM seo_client_settings
        )
        """
    ).fetchall()
    for row in customer_rows:
        cid = int(row["customer_id"] if isinstance(row, dict) else row[0])
        published = conn.execute(
            """
            SELECT COUNT(*) AS c FROM seo_content
            WHERE customer_id = ? AND workflow_status IN ('published', 'monitoring')
            """,
            (cid,),
        ).fetchone()
        pub_count = int(published["c"] or 0) if published else 0
        facts.append(
            {
                "customer_id": cid,
                "fact_date": d,
                "metric_name": "content_published",
                "metric_value": float(pub_count),
                "dimensions": json.dumps({"source": "seo_content"}, ensure_ascii=False),
            }
        )
        gsc = conn.execute(
            """
            SELECT COALESCE(SUM(clicks),0) AS clicks, COALESCE(SUM(impressions),0) AS impressions
            FROM seo_gsc_daily_stats
            WHERE customer_id = ? AND stat_date = ?
            """,
            (cid, d),
        ).fetchone()
        if gsc:
            facts.append(
                {
                    "customer_id": cid,
                    "fact_date": d,
                    "metric_name": "gsc_clicks",
                    "metric_value": float(gsc["clicks"] or 0),
                    "dimensions": json.dumps({"stat_date": d}, ensure_ascii=False),
                }
            )
            facts.append(
                {
                    "customer_id": cid,
                    "fact_date": d,
                    "metric_name": "gsc_impressions",
                    "metric_value": float(gsc["impressions"] or 0),
                    "dimensions": json.dumps({"stat_date": d}, ensure_ascii=False),
                }
            )
        crit = conn.execute(
            """
            SELECT COUNT(*) AS c FROM seo_technical_issues
            WHERE customer_id = ? AND severity = 'critical'
              AND status NOT IN ('closed', 'verified')
            """,
            (cid,),
        ).fetchone()
        facts.append(
            {
                "customer_id": cid,
                "fact_date": d,
                "metric_name": "critical_issues_open",
                "metric_value": float(crit["c"] or 0) if crit else 0.0,
                "dimensions": "{}",
            }
        )
        aeo = conn.execute(
            """
            SELECT COUNT(*) AS t,
                   SUM(CASE WHEN COALESCE(m.brand_visible, 0) = 1 THEN 1 ELSE 0 END) AS v
            FROM seo_questions q
            LEFT JOIN seo_ai_mentions m ON m.id = (
                SELECT id FROM seo_ai_mentions WHERE question_id = q.id ORDER BY id DESC LIMIT 1
            )
            WHERE q.customer_id = ? AND q.status = 'active'
            """,
            (cid,),
        ).fetchone()
        if aeo and int(aeo["t"] or 0) > 0:
            total = int(aeo["t"])
            visible = int(aeo["v"] or 0)
            facts.append(
                {
                    "customer_id": cid,
                    "fact_date": d,
                    "metric_name": "aeo_coverage_pct",
                    "metric_value": round(100.0 * visible / total, 2),
                    "dimensions": json.dumps({"visible": visible, "total": total}, ensure_ascii=False),
                }
            )
        try:
            from ptt_seo.attribution import organic_revenue_total

            rev = organic_revenue_total(conn, cid, days=28)
            if rev > 0:
                facts.append(
                    {
                        "customer_id": cid,
                        "fact_date": d,
                        "metric_name": "organic_revenue",
                        "metric_value": rev,
                        "dimensions": "{}",
                    }
                )
        except Exception:
            pass
    return facts


def export_seo_facts_to_clickhouse(
    conn: sqlite3.Connection,
    *,
    fact_date: str | None = None,
    skip_if_no_ch: bool = True,
) -> dict[str, Any]:
    if skip_if_no_ch and not (os.environ.get("CLICKHOUSE_URL") or os.environ.get("CLICKHOUSE_HOST")):
        return {"ok": False, "skipped": True, "reason": "clickhouse_not_configured"}
    ensure_seo_facts_schema()
    facts = collect_daily_facts(conn, fact_date=fact_date)
    if not facts:
        return {"ok": True, "exported": 0}
    exported_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []
    for f in facts:
        lines.append(
            json.dumps(
                {
                    "customer_id": f["customer_id"],
                    "fact_date": f["fact_date"],
                    "metric_name": f["metric_name"],
                    "metric_value": f["metric_value"],
                    "dimensions": f["dimensions"],
                    "exported_at": exported_at,
                },
                ensure_ascii=False,
            )
        )
    body = ("\n".join(lines) + "\n").encode("utf-8")
    sql = "INSERT INTO ptt.seo_daily_facts FORMAT JSONEachRow"
    try:
        _ch_request(sql, data=body)
        return {"ok": True, "exported": len(facts), "fact_date": fact_date or date.today().isoformat()}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "exported": 0}


def bi_dashboard(conn: sqlite3.Connection, *, customer_id: int | None = None, days: int = 28) -> dict[str, Any]:
    """PG-side BI summary (works without ClickHouse)."""
    since = (date.today() - timedelta(days=days)).isoformat()
    cid_filter = customer_id
    gsc_sql = """
        SELECT stat_date, SUM(clicks) AS clicks, SUM(impressions) AS impressions
        FROM seo_gsc_daily_stats WHERE stat_date >= ?
    """
    params: list[Any] = [since]
    if cid_filter:
        gsc_sql += " AND customer_id = ?"
        params.append(cid_filter)
    gsc_sql += " GROUP BY stat_date ORDER BY stat_date ASC"
    series = [dict(r) for r in conn.execute(gsc_sql, params).fetchall()]
    totals = {
        "clicks": sum(int(r.get("clicks") or 0) for r in series),
        "impressions": sum(int(r.get("impressions") or 0) for r in series),
    }
    return {
        "type": "bi",
        "customer_id": customer_id,
        "days": days,
        "gsc_series": series,
        "totals": totals,
        "clickhouse_configured": bool(os.environ.get("CLICKHOUSE_URL") or os.environ.get("CLICKHOUSE_HOST")),
    }
