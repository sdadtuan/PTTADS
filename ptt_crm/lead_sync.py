"""SQLite → PostgreSQL crm_leads read replica sync (Phase 1b Bước 6)."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_crm.config import lead_replica_sync_enabled
from ptt_crm.leads_read import get_lead_v1, lead_row_to_v1
from ptt_crm.pg_schema import pg_leads_replica_ready, pg_row_to_v1
from ptt_jobs.config import sqlite_db_path
from ptt_jobs.db import json_dumps, pg_connection

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_ts(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text[:19] if "T" not in fmt and len(text) >= 19 else text, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _normalize_uuid(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or not _UUID_RE.match(text):
        return None
    return text.lower()


def sqlite_row_to_pg_record(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Build PG upsert payload from SQLite crm_leads row."""
    d = dict(row)
    meta = _parse_meta(d.get("meta_json"))
    v1 = lead_row_to_v1({**d, "meta_json": json.dumps(meta) if meta else "{}"})
    return {
        "sqlite_lead_id": int(v1["id"]),
        "full_name": v1["full_name"],
        "phone": v1["phone"],
        "email": v1["email"],
        "status": v1["status"],
        "source": v1["source"],
        "owner_id": v1["owner_id"],
        "is_duplicate": bool(v1["is_duplicate"]),
        "meta_json": json_dumps(meta),
        "agency_client_id": _normalize_uuid(v1.get("client_id")),
        "channel": v1["channel"],
        "external_lead_id": v1.get("external_lead_id") or None,
        "campaign_id": v1.get("campaign_id") or None,
        "received_at": _parse_ts(v1.get("received_at")),
        "created_at": _parse_ts(v1.get("created_at")),
    }


def upsert_pg_lead(record: dict[str, Any], *, write_source: str = "sync") -> None:
    ws = (write_source or "sync")[:32]
    payload = {**record, "write_source": ws}
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO crm_leads (
                    sqlite_lead_id, full_name, phone, email, status, source,
                    owner_id, is_duplicate, meta_json, agency_client_id,
                    channel, external_lead_id, campaign_id, received_at, created_at,
                    synced_at, sync_version, write_source
                )
                VALUES (
                    %(sqlite_lead_id)s, %(full_name)s, %(phone)s, %(email)s,
                    %(status)s, %(source)s, %(owner_id)s, %(is_duplicate)s,
                    %(meta_json)s::jsonb,
                    %(agency_client_id)s::uuid,
                    %(channel)s, %(external_lead_id)s, %(campaign_id)s,
                    %(received_at)s, %(created_at)s, NOW(), 1, %(write_source)s
                )
                ON CONFLICT (sqlite_lead_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    status = EXCLUDED.status,
                    source = EXCLUDED.source,
                    owner_id = EXCLUDED.owner_id,
                    is_duplicate = EXCLUDED.is_duplicate,
                    meta_json = EXCLUDED.meta_json,
                    agency_client_id = EXCLUDED.agency_client_id,
                    channel = EXCLUDED.channel,
                    external_lead_id = EXCLUDED.external_lead_id,
                    campaign_id = EXCLUDED.campaign_id,
                    received_at = EXCLUDED.received_at,
                    created_at = EXCLUDED.created_at,
                    synced_at = NOW(),
                    sync_version = crm_leads.sync_version + 1,
                    write_source = CASE
                        WHEN EXCLUDED.write_source <> 'sync' THEN EXCLUDED.write_source
                        ELSE crm_leads.write_source
                    END
                """,
                payload,
            )
        conn.commit()


def _fetch_sqlite_rows(*, after_id: int = 0, lead_ids: list[int] | None = None, limit: int = 200) -> list[sqlite3.Row]:
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        if lead_ids:
            placeholders = ",".join("?" * len(lead_ids))
            return conn.execute(
                f"""
                SELECT id, full_name, phone, email, status, source,
                       owner_id, created_at, is_duplicate, meta_json
                FROM crm_leads
                WHERE id IN ({placeholders})
                ORDER BY id ASC
                """,
                lead_ids,
            ).fetchall()
        lim = max(1, min(int(limit), 1000))
        return conn.execute(
            """
            SELECT id, full_name, phone, email, status, source,
                   owner_id, created_at, is_duplicate, meta_json
            FROM crm_leads
            WHERE id > ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (after_id, lim),
        ).fetchall()
    finally:
        conn.close()


def _get_watermark() -> int:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_sqlite_id FROM crm_leads_sync_state WHERE id = 1")
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0


def _update_sync_state(*, last_sqlite_id: int, full: bool = False) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE crm_leads_sync_state
                SET last_sqlite_id = GREATEST(last_sqlite_id, %s),
                    last_sync_at = NOW(),
                    last_full_at = CASE WHEN %s THEN NOW() ELSE last_full_at END,
                    rows_total = (SELECT COUNT(*) FROM crm_leads),
                    updated_at = NOW()
                WHERE id = 1
                """,
                (last_sqlite_id, full),
            )
        conn.commit()


def sync_lead_ids(lead_ids: list[int]) -> dict[str, Any]:
    """Upsert specific SQLite lead ids to PG."""
    if not lead_ids:
        return {"ok": True, "synced": 0, "skipped": True, "reason": "no_ids"}
    if not lead_replica_sync_enabled():
        return {"ok": True, "synced": 0, "skipped": True, "reason": "disabled"}
    if not pg_leads_replica_ready():
        return {"ok": False, "synced": 0, "error": "pg_replica_not_ready"}

    rows = _fetch_sqlite_rows(lead_ids=[int(i) for i in lead_ids])
    synced = 0
    max_id = _get_watermark()
    for row in rows:
        upsert_pg_lead(sqlite_row_to_pg_record(row), write_source="sync")
        synced += 1
        max_id = max(max_id, int(row["id"]))
    if synced:
        _update_sync_state(last_sqlite_id=max_id)
    return {"ok": True, "synced": synced, "last_sqlite_id": max_id}


def sync_lead_ids_worker(lead_ids: list[int]) -> dict[str, Any]:
    """Upsert ingest leads to PG with write_source=worker (Sprint 0 PG-primary path)."""
    if not lead_ids:
        return {"ok": True, "synced": 0, "skipped": True, "reason": "no_ids"}
    if not pg_leads_replica_ready():
        return {"ok": False, "synced": 0, "error": "pg_replica_not_ready"}

    rows = _fetch_sqlite_rows(lead_ids=[int(i) for i in lead_ids])
    if len(rows) != len(lead_ids):
        missing = set(int(i) for i in lead_ids) - {int(r["id"]) for r in rows}
        return {"ok": False, "synced": 0, "error": "sqlite_rows_missing", "missing": sorted(missing)}

    synced = 0
    max_id = _get_watermark()
    for row in rows:
        upsert_pg_lead(sqlite_row_to_pg_record(row), write_source="worker")
        synced += 1
        max_id = max(max_id, int(row["id"]))
    if synced:
        _update_sync_state(last_sqlite_id=max_id)
    return {"ok": True, "synced": synced, "write_source": "worker", "last_sqlite_id": max_id}


def sync_incremental(*, batch_size: int = 200) -> dict[str, Any]:
    """Sync rows with id > watermark."""
    if not lead_replica_sync_enabled():
        return {"ok": True, "synced": 0, "skipped": True, "reason": "disabled"}
    if not pg_leads_replica_ready():
        return {"ok": False, "synced": 0, "error": "pg_replica_not_ready"}

    watermark = _get_watermark()
    rows = _fetch_sqlite_rows(after_id=watermark, limit=batch_size)
    synced = 0
    max_id = watermark
    for row in rows:
        upsert_pg_lead(sqlite_row_to_pg_record(row), write_source="sync")
        synced += 1
        max_id = max(max_id, int(row["id"]))
    if synced:
        _update_sync_state(last_sqlite_id=max_id)
    return {
        "ok": True,
        "synced": synced,
        "watermark_before": watermark,
        "last_sqlite_id": max_id,
    }


def sync_full_backfill(*, batch_size: int = 500, max_batches: int = 100) -> dict[str, Any]:
    """Backfill all SQLite leads into PG (idempotent upsert)."""
    if not lead_replica_sync_enabled():
        return {"ok": True, "synced": 0, "skipped": True, "reason": "disabled"}
    if not pg_leads_replica_ready():
        return {"ok": False, "synced": 0, "error": "pg_replica_not_ready"}

    total = 0
    watermark = 0
    batches = 0
    while batches < max_batches:
        rows = _fetch_sqlite_rows(after_id=watermark, limit=batch_size)
        if not rows:
            break
        for row in rows:
            upsert_pg_lead(sqlite_row_to_pg_record(row), write_source="sync")
            watermark = max(watermark, int(row["id"]))
            total += 1
        _update_sync_state(last_sqlite_id=watermark)
        batches += 1
        if len(rows) < batch_size:
            break
    _update_sync_state(last_sqlite_id=watermark, full=True)
    return {"ok": True, "synced": total, "batches": batches, "last_sqlite_id": watermark}


def _pg_lead_v1(lead_id: int) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sqlite_lead_id, full_name, phone, email, status, source,
                       owner_id, is_duplicate, agency_client_id, channel,
                       external_lead_id, campaign_id, received_at, created_at
                FROM crm_leads WHERE sqlite_lead_id = %s
                """,
                (lead_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return pg_row_to_v1(dict(zip(cols, row)))


def reconcile_leads(*, sample_size: int = 50) -> dict[str, Any]:
    """Compare SQLite vs PG counts + sample LeadV1 fingerprints."""
    if not pg_leads_replica_ready():
        return {"ok": False, "error": "pg_replica_not_ready"}

    conn = sqlite3.connect(sqlite_db_path())
    try:
        sqlite_total = int(
            conn.execute("SELECT COUNT(*) FROM crm_leads WHERE COALESCE(is_duplicate, 0) = 0").fetchone()[0]
        )
        ids = [
            int(r[0])
            for r in conn.execute(
                """
                SELECT id FROM crm_leads
                WHERE COALESCE(is_duplicate, 0) = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(sample_size, 500)),),
            ).fetchall()
        ]
    finally:
        conn.close()

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM crm_leads WHERE is_duplicate IS NOT TRUE")
            pg_total = int(cur.fetchone()[0] or 0)

    mismatches: list[dict[str, Any]] = []
    for lead_id in ids:
        flask_lead = get_lead_v1(lead_id)
        pg_lead = _pg_lead_v1(lead_id)
        if flask_lead is None and pg_lead is None:
            continue
        if flask_lead is None or pg_lead is None:
            mismatches.append({"id": lead_id, "error": "missing_side", "flask": bool(flask_lead), "pg": bool(pg_lead)})
            continue
        from ptt_crm.dual_run import diff_lead_v1

        diffs = diff_lead_v1(flask_lead, pg_lead)
        if diffs:
            mismatches.append({"id": lead_id, "diffs": [d.__dict__ for d in diffs]})

    return {
        "ok": len(mismatches) == 0 and sqlite_total == pg_total,
        "sqlite_total": sqlite_total,
        "pg_total": pg_total,
        "sample_size": len(ids),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
    }


def sync_after_ingest(created_ids: list[int]) -> None:
    """Fast path after ingest_lead — sync new leads immediately."""
    if not created_ids:
        return
    try:
        from ptt_crm.config import leads_write_source_pg

        if leads_write_source_pg():
            return
        if not lead_replica_sync_enabled():
            return
        result = sync_lead_ids(created_ids)
        if not result.get("ok"):
            logger.warning("lead replica sync after ingest failed: %s", result)
        else:
            logger.info("lead replica synced after ingest count=%s", result.get("synced"))
    except Exception as exc:
        logger.exception("lead replica sync after ingest error: %s", exc)
