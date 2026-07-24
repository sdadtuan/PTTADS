"""B14 — Meta/Google daily_performance → ClickHouse warehouse facts."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CHANNELS = ("meta", "google")


def warehouse_export_enabled() -> bool:
    return os.environ.get("PTT_META_WAREHOUSE_EXPORT", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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


def ensure_meta_facts_schema(*, ddl_path: str | None = None) -> dict[str, Any]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = Path(ddl_path) if ddl_path else root / "deploy/clickhouse/init-meta-daily-facts.sql"
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
        logger.warning("ensure_meta_facts_schema: %s", exc)
        return {"ok": False, "error": str(exc)}


def _insight_level_filter_sql() -> tuple[str, list[Any]]:
    try:
        from ptt_crm.pg_schema import pg_daily_performance_insight_level_ready

        if pg_daily_performance_insight_level_ready():
            return "AND COALESCE(dp.insight_level, 'campaign') = 'campaign'", []
    except Exception:
        pass
    return "", []


def collect_meta_daily_facts(
    *,
    fact_date: str | None = None,
    client_id: str | None = None,
    channels: tuple[str, ...] = DEFAULT_CHANNELS,
) -> list[dict[str, Any]]:
    from ptt_jobs.db import pg_connection

    d = fact_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    level_clause, level_params = _insight_level_filter_sql()
    facts: list[dict[str, Any]] = []

    with pg_connection() as conn:
        with conn.cursor() as cur:
            params: list[Any] = [d, list(channels)]
            clauses = ["dp.performance_date = %s::date", "dp.channel = ANY(%s)"]
            if client_id:
                clauses.append("dp.client_id = %s::uuid")
                params.append(client_id)
            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       dp.channel,
                       COALESCE(dp.external_campaign_id, '') AS external_campaign_id,
                       dp.performance_date::text,
                       COALESCE(dp.spend, 0),
                       COALESCE(dp.impressions, 0),
                       COALESCE(dp.clicks, 0),
                       COALESCE(dp.leads_platform, 0),
                       COALESCE(dp.leads_crm, 0),
                       CASE WHEN dp.hub_campaign_map_id IS NOT NULL THEN 1 ELSE 0 END
                FROM daily_performance dp
                WHERE {' AND '.join(clauses)}
                  {level_clause}
                ORDER BY dp.client_id, dp.channel, dp.external_campaign_id
                """,
                tuple(params) + tuple(level_params),
            )
            for row in cur.fetchall():
                facts.append(
                    {
                        "client_id": str(row[0]),
                        "channel": str(row[1]),
                        "external_campaign_id": str(row[2] or ""),
                        "performance_date": str(row[3]),
                        "spend": float(row[4] or 0),
                        "impressions": int(row[5] or 0),
                        "clicks": int(row[6] or 0),
                        "leads_platform": int(row[7] or 0),
                        "leads_crm": int(row[8] or 0),
                        "hub_mapped": int(row[9] or 0),
                    }
                )
    return facts


def count_pg_meta_facts(*, date_from: str, date_to: str) -> int:
    try:
        from ptt_jobs.db import pg_connection

        level_clause, level_params = _insight_level_filter_sql()
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int
                    FROM daily_performance dp
                    WHERE dp.channel IN ('meta', 'google')
                      AND dp.performance_date BETWEEN %s::date AND %s::date
                      {level_clause}
                    """,
                    (date_from, date_to, *level_params),
                )
                return int(cur.fetchone()[0] or 0)
    except Exception as exc:
        logger.warning("count_pg_meta_facts: %s", exc)
        return -1


def count_ch_meta_facts(*, date_from: str, date_to: str) -> int:
    try:
        raw = _ch_request(
            "SELECT count() FROM ptt.meta_daily_facts "
            f"WHERE performance_date >= toDate('{date_from}') "
            f"AND performance_date <= toDate('{date_to}') FORMAT TabSeparated",
        )
        return int(raw.strip() or 0)
    except Exception as exc:
        logger.warning("count_ch_meta_facts: %s", exc)
        return -1


def compare_export_parity(*, days: int = 7) -> dict[str, Any]:
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=max(days - 1, 0))
    pg_count = count_pg_meta_facts(date_from=start.isoformat(), date_to=end.isoformat())
    ch_count = count_ch_meta_facts(date_from=start.isoformat(), date_to=end.isoformat())
    if pg_count < 0:
        return {
            "ok": True,
            "reason": "pg_unavailable",
            "pg_count": pg_count,
            "ch_count": ch_count,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        }
    if ch_count < 0:
        return {
            "ok": False,
            "reason": "clickhouse_unavailable",
            "pg_count": pg_count,
            "ch_count": ch_count,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        }
    tolerance = max(int(pg_count * 0.05), 5) if pg_count else 5
    delta = abs(pg_count - ch_count)
    return {
        "ok": delta <= tolerance or (pg_count == 0 and ch_count == 0),
        "pg_count": pg_count,
        "ch_count": ch_count,
        "delta": delta,
        "tolerance": tolerance,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
    }


def export_meta_facts_to_clickhouse(
    *,
    fact_date: str | None = None,
    client_id: str | None = None,
    skip_if_no_ch: bool = True,
    stub: bool = False,
) -> dict[str, Any]:
    if not stub and not warehouse_export_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_META_WAREHOUSE_EXPORT=0"}
    if not stub and skip_if_no_ch and not (os.environ.get("CLICKHOUSE_URL") or os.environ.get("CLICKHOUSE_HOST")):
        return {"ok": True, "skipped": True, "reason": "clickhouse_not_configured"}

    d = fact_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    try:
        facts = collect_meta_daily_facts(fact_date=d, client_id=client_id)
    except Exception as exc:
        if stub:
            logger.warning("collect_meta_daily_facts stub fallback: %s", exc)
            facts = []
        else:
            return {"ok": False, "error": str(exc)}
    if stub:
        return {
            "ok": True,
            "stub": True,
            "rows": len(facts),
            "fact_date": d,
        }

    schema_out = ensure_meta_facts_schema()
    if not schema_out.get("ok"):
        return schema_out

    if not facts:
        return {"ok": True, "exported": 0, "fact_date": d}

    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    for f in facts:
        lines.append(
            json.dumps(
                {**f, "exported_at": exported_at},
                ensure_ascii=False,
            )
        )
    body = ("\n".join(lines) + "\n").encode("utf-8")
    _ch_request("INSERT INTO ptt.meta_daily_facts FORMAT JSONEachRow", data=body)
    return {"ok": True, "exported": len(facts), "fact_date": d}


def export_meta_facts_range(
    *,
    days: int = 7,
    client_id: str | None = None,
    skip_if_no_ch: bool = True,
) -> dict[str, Any]:
    if not warehouse_export_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_META_WAREHOUSE_EXPORT=0"}

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    total = 0
    results: list[dict[str, Any]] = []
    for offset in range(max(days, 1)):
        d = (end - timedelta(days=offset)).isoformat()
        out = export_meta_facts_to_clickhouse(
            fact_date=d,
            client_id=client_id,
            skip_if_no_ch=skip_if_no_ch,
        )
        results.append(out)
        if out.get("exported"):
            total += int(out["exported"])
        if not out.get("ok") and not out.get("skipped"):
            return {**out, "partial_results": results}
    return {"ok": True, "exported": total, "days": days, "results": results}
