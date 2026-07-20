"""Email daily facts → ClickHouse (Wave 2)."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def _ch_request(sql: str, *, data: bytes | None = None) -> str:
    from ptt_analytics.clickhouse_export import _auth_header, _clickhouse_endpoint
    import urllib.request

    base, _, _ = _clickhouse_endpoint()
    url = f"{base}/?query={sql}"
    headers = {"Content-Type": "text/plain; charset=utf-8"}
    headers.update(_auth_header())
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def ensure_email_facts_schema(*, ddl_path: str | None = None) -> dict[str, Any]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = Path(ddl_path) if ddl_path else root / "deploy/clickhouse/init-email-facts.sql"
    if not path.is_file():
        return {"ok": False, "error": "ddl_missing"}
    ddl = path.read_text(encoding="utf-8")
    try:
        for stmt in ddl.split(";"):
            chunk = stmt.strip()
            if not chunk or chunk.startswith("--"):
                continue
            lines = [ln for ln in chunk.splitlines() if ln.strip() and not ln.strip().startswith("--")]
            if not lines:
                continue
            _ch_request("\n".join(lines))
        return {"ok": True}
    except Exception as exc:
        logger.warning("ensure_email_facts_schema: %s", exc)
        return {"ok": False, "error": str(exc)}


def collect_daily_facts(*, fact_date: str | None = None, client_id: str | None = None) -> list[dict[str, Any]]:
    from ptt_jobs.db import pg_connection
    from ptt_email.attribution import email_revenue_attributed

    d = fact_date or date.today().isoformat()
    facts: list[dict[str, Any]] = []
    with pg_connection() as conn:
        with conn.cursor() as cur:
            if client_id:
                cur.execute(f"SELECT client_id::text FROM {SCHEMA}.workspaces WHERE client_id = %s::uuid", (client_id,))
            else:
                cur.execute(f"SELECT client_id::text FROM {SCHEMA}.workspaces")
            client_ids = [str(r[0]) for r in cur.fetchall()]

            for cid in client_ids:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {SCHEMA}.send_queue sq
                    WHERE sq.client_id = %s::uuid
                      AND sq.status IN ('sent', 'delivered')
                      AND COALESCE(sq.sent_at, sq.scheduled_at)::date = %s::date
                    """,
                    (cid, d),
                )
                sent = float(cur.fetchone()[0] or 0)
                facts.append(
                    {
                        "client_id": cid,
                        "fact_date": d,
                        "metric_name": "emails_sent",
                        "metric_value": sent,
                        "dimensions": "{}",
                    }
                )
                for event_type, metric in (("open", "opens"), ("click", "clicks"), ("complaint", "complaints")):
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {SCHEMA}.engagement_events ee
                        WHERE ee.client_id = %s::uuid AND ee.event_type = %s
                          AND ee.occurred_at::date = %s::date
                        """,
                        (cid, event_type, d),
                    )
                    val = float(cur.fetchone()[0] or 0)
                    facts.append(
                        {
                            "client_id": cid,
                            "fact_date": d,
                            "metric_name": metric,
                            "metric_value": val,
                            "dimensions": json.dumps({"event_type": event_type}, ensure_ascii=False),
                        }
                    )
                rev = email_revenue_attributed(cid, days=28)
                if rev > 0:
                    facts.append(
                        {
                            "client_id": cid,
                            "fact_date": d,
                            "metric_name": "revenue_attrib",
                            "metric_value": rev,
                            "dimensions": "{}",
                        }
                    )
    return facts


def collect_deliverability_daily(*, metric_date: str | None = None) -> list[dict[str, Any]]:
    from ptt_jobs.db import pg_connection

    d = metric_date or date.today().isoformat()
    rows_out: list[dict[str, Any]] = []
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT d.client_id::text, d.domain,
                       COUNT(*) FILTER (WHERE sq.status IN ('sent','delivered')) AS sent,
                       COUNT(*) FILTER (WHERE ee.event_type = 'delivered') AS delivered,
                       COUNT(*) FILTER (WHERE ee.event_type = 'bounce_hard') AS bounce_hard,
                       COUNT(*) FILTER (WHERE ee.event_type = 'bounce_soft') AS bounce_soft,
                       COUNT(*) FILTER (WHERE ee.event_type = 'complaint') AS complaint,
                       COUNT(*) FILTER (WHERE ee.event_type = 'unsubscribe') AS unsub
                FROM {SCHEMA}.domains d
                LEFT JOIN {SCHEMA}.send_queue sq ON sq.client_id = d.client_id
                  AND COALESCE(sq.sent_at, sq.scheduled_at)::date = %s::date
                LEFT JOIN {SCHEMA}.engagement_events ee ON ee.client_id = d.client_id
                  AND ee.occurred_at::date = %s::date
                GROUP BY d.client_id, d.domain
                """,
                (d, d),
            )
            for row in cur.fetchall():
                rows_out.append(
                    {
                        "client_id": str(row[0]),
                        "domain": str(row[1]),
                        "metric_date": d,
                        "sent_count": int(row[2] or 0),
                        "delivered_count": int(row[3] or 0),
                        "bounce_hard": int(row[4] or 0),
                        "bounce_soft": int(row[5] or 0),
                        "complaint_count": int(row[6] or 0),
                        "unsubscribe_count": int(row[7] or 0),
                    }
                )
    return rows_out


def export_email_facts_to_clickhouse(
    *,
    fact_date: str | None = None,
    skip_if_no_ch: bool = True,
) -> dict[str, Any]:
    from ptt_email.config import email_clickhouse_export_enabled

    if not email_clickhouse_export_enabled():
        return {"ok": False, "skipped": True, "reason": "export_disabled"}
    if skip_if_no_ch and not (os.environ.get("CLICKHOUSE_URL") or os.environ.get("CLICKHOUSE_HOST")):
        return {"ok": False, "skipped": True, "reason": "clickhouse_not_configured"}

    schema_out = ensure_email_facts_schema()
    if not schema_out.get("ok"):
        return schema_out

    facts = collect_daily_facts(fact_date=fact_date)
    deliv = collect_deliverability_daily(metric_date=fact_date)
    if not facts and not deliv:
        return {"ok": True, "exported": 0, "deliverability_rows": 0}

    exported_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if facts:
        lines = []
        for f in facts:
            lines.append(
                json.dumps(
                    {
                        "client_id": f["client_id"],
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
        _ch_request("INSERT INTO ptt.email_daily_facts FORMAT JSONEachRow", data=body)

    if deliv:
        lines = [json.dumps(row, ensure_ascii=False) for row in deliv]
        body = ("\n".join(lines) + "\n").encode("utf-8")
        _ch_request("INSERT INTO ptt.email_deliverability_daily FORMAT JSONEachRow", data=body)

    return {
        "ok": True,
        "exported": len(facts),
        "deliverability_rows": len(deliv),
        "fact_date": fact_date or date.today().isoformat(),
    }
