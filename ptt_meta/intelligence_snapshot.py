"""Meta intelligence weekly snapshot export (B11) — gzip JSON artifact + PG metadata."""
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


def meta_intel_snapshot_enabled() -> bool:
    return _truthy("PTT_META_INTEL_SNAPSHOT_ENABLED", "0")


def pg_meta_intelligence_snapshots_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_meta_intelligence_snapshots_ready as _ready

        return _ready()
    except Exception:
        return False


def _artifacts_dir() -> Path:
    raw = os.environ.get("PTT_ARTIFACTS_DIR", ".local-dev")
    p = Path(raw)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[1] / p
    out = p / "meta-intel-snapshots"
    out.mkdir(parents=True, exist_ok=True)
    return out


def create_intelligence_snapshot(
    *,
    client_id: str | None = None,
    period_days: int = 7,
) -> dict[str, Any]:
    if not meta_intel_snapshot_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_META_INTEL_SNAPSHOT_ENABLED=0"}
    if not pg_meta_intelligence_snapshots_ready():
        return {
            "ok": False,
            "error": "meta_intelligence_snapshots_not_ready",
            "hint": "./scripts/apply_pg_ddl_v7_meta_advanced.sh",
        }

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=max(1, period_days) - 1)

    clauses = ["dp.channel = 'meta'", "dp.performance_date BETWEEN %s AND %s"]
    values: list[Any] = [start, end]
    if client_id:
        clauses.append("dp.client_id = %s::uuid")
        values.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text, dp.performance_date::date,
                       SUM(dp.spend) AS spend,
                       SUM(dp.leads_crm) AS leads_crm,
                       SUM(dp.conversion_value) AS conversion_value
                FROM daily_performance dp
                WHERE {' AND '.join(clauses)}
                GROUP BY dp.client_id, dp.performance_date
                ORDER BY dp.client_id, dp.performance_date
                """,
                values,
            )
            perf_rows = cur.fetchall()

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "client_id": client_id,
        "performance": [
            {
                "client_id": r[0],
                "performance_date": r[1].isoformat(),
                "spend": float(r[2] or 0),
                "leads_crm": int(r[3] or 0),
                "conversion_value": float(r[4] or 0),
            }
            for r in perf_rows
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client_part = client_id or "all"
    filename = f"meta-intel-{client_part}-{stamp}.json.gz"
    path = _artifacts_dir() / filename
    with gzip.open(path, "wb") as fh:
        fh.write(raw)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meta_intelligence_snapshots (
                    client_id, period_start, period_end, artifact_path, byte_size, gzip
                ) VALUES (%s::uuid, %s::date, %s::date, %s, %s, TRUE)
                RETURNING id::text, created_at
                """,
                (client_id, start, end, str(path), len(raw)),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "ok": True,
        "snapshot": {
            "id": row[0],
            "client_id": client_id,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "artifact_path": str(path),
            "byte_size": len(raw),
            "gzip": True,
            "created_at": row[1].isoformat() if row[1] else None,
        },
    }


def fetch_latest_snapshot_digest(*, client_id: str | None = None) -> dict[str, Any] | None:
    """Summary for owner-weekly digest hook."""
    if not meta_intel_snapshot_enabled() or not pg_meta_intelligence_snapshots_ready():
        return None

    clauses = ["1=1"]
    values: list[Any] = []
    if client_id:
        clauses.append("client_id = %s::uuid")
        values.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text, period_start, period_end, byte_size, created_at
                FROM meta_intelligence_snapshots
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT 1
                """,
                values,
            )
            row = cur.fetchone()

    if not row:
        return None

    return {
        "snapshot_id": row[0],
        "client_id": row[1],
        "period_start": row[2].isoformat() if isinstance(row[2], date) else str(row[2]),
        "period_end": row[3].isoformat() if isinstance(row[3], date) else str(row[3]),
        "byte_size": int(row[4] or 0),
        "created_at": row[5].isoformat() if row[5] else None,
    }
