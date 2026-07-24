"""B9 insights archive — purge aged daily_performance rows (dry-run default)."""
from __future__ import annotations

import gzip
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def insights_archive_enabled() -> bool:
    return _truthy("PTT_META_INSIGHTS_ARCHIVE_ENABLED", "1")


def retention_days() -> int:
    raw = os.environ.get("PTT_META_INSIGHTS_RETENTION_DAYS", "400").strip()
    try:
        return max(30, min(int(raw), 2000))
    except ValueError:
        return 400


def archive_artifact_dir() -> Path:
    raw = os.environ.get("PTT_META_INSIGHTS_ARCHIVE_DIR", ".local-dev/archive/meta-insights").strip()
    return Path(raw)


def count_archive_candidates(*, cutoff_date: date | None = None) -> int:
    cutoff = cutoff_date or (datetime.now(timezone.utc).date() - timedelta(days=retention_days()))
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM daily_performance
                WHERE performance_date < %s::date
                """,
                [cutoff.isoformat()],
            )
            return int(cur.fetchone()[0] or 0)


def archive_daily_performance(
    *,
    dry_run: bool = True,
    client_id: str | None = None,
    limit: int = 5000,
) -> dict[str, Any]:
    """Delete or export daily_performance rows older than retention window."""
    if not insights_archive_enabled():
        return {"ok": True, "skipped": True, "reason": "archive_disabled"}

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=retention_days())
    max_rows = max(1, min(int(limit), 50000))
    client_clause = ""
    select_params: list[Any] = [cutoff.isoformat()]
    if client_id:
        client_clause = "AND client_id = %s::uuid"
        select_params.append(client_id)
    select_params.append(max_rows)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT client_id::text, channel, external_campaign_id, performance_date,
                       spend, leads_crm, leads_platform, impressions, clicks
                FROM daily_performance
                WHERE performance_date < %s::date
                {client_clause}
                ORDER BY performance_date ASC
                LIMIT %s
                """,
                select_params,
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    export_path: str | None = None
    if rows and not dry_run:
        out_dir = archive_artifact_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"daily_performance_archive_{stamp}.json.gz"
        payload = {
            "cutoff_date": cutoff.isoformat(),
            "row_count": len(rows),
            "rows": rows,
        }
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, default=str)
        export_path = str(path)

    deleted = 0
    if rows and not dry_run:
        del_params: list[Any] = [cutoff.isoformat()]
        if client_id:
            del_params.append(client_id)
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    DELETE FROM daily_performance
                    WHERE performance_date < %s::date
                    {client_clause}
                    """,
                    del_params,
                )
                deleted = cur.rowcount or 0
            conn.commit()

    return {
        "ok": True,
        "dry_run": dry_run,
        "cutoff_date": cutoff.isoformat(),
        "retention_days": retention_days(),
        "candidate_count": len(rows),
        "deleted": deleted if not dry_run else 0,
        "export_path": export_path,
        "client_id": client_id,
    }
