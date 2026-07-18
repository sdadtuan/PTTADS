"""PostgreSQL → SQLite crm_leads shadow sync (Phase 2 W2)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_crm.config import lead_shadow_sync_enabled
from ptt_crm.leads_read import get_lead_v1
from ptt_crm.pg_schema import pg_row_to_v1, pg_shadow_ready
from ptt_jobs.config import sqlite_db_path
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

_PG_SELECT = """
SELECT sqlite_lead_id, full_name, phone, email, status, source,
       owner_id, is_duplicate, meta_json, agency_client_id, channel,
       external_lead_id, campaign_id, received_at, created_at,
       synced_at, sync_version, updated_at, updated_by, write_source
FROM crm_leads
WHERE sync_version > %s
  AND COALESCE(write_source, 'sync') <> 'sync'
ORDER BY sync_version ASC
LIMIT %s
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        return json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _fmt_sqlite_ts(value: Any) -> str:
    if value is None:
        return _utc_now().strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    text = str(value).strip().replace("T", " ")[:19]
    return text or _utc_now().strftime("%Y-%m-%d %H:%M:%S")


def _phone_norm(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits[:20]


def _email_norm(email: str) -> str:
    return str(email or "").strip().lower()[:240]


def pg_row_to_sqlite_record(row: dict[str, Any]) -> dict[str, Any]:
    """Build SQLite upsert payload from PG crm_leads row."""
    meta = _parse_meta(row.get("meta_json"))
    channel = str(row.get("channel") or meta.get("channel") or "")
    client_id = row.get("agency_client_id")
    if client_id:
        meta["agency_client_id"] = str(client_id)
    if channel:
        meta["channel"] = channel
    ext_id = row.get("external_lead_id")
    if ext_id:
        meta.setdefault("external_lead_id", str(ext_id))
        if channel == "meta" or meta.get("facebook_leadgen_id"):
            meta.setdefault("facebook_leadgen_id", str(ext_id))
        elif channel == "zalo" or meta.get("zalo_lead_id"):
            meta.setdefault("zalo_lead_id", str(ext_id))
    campaign_id = row.get("campaign_id")
    if campaign_id:
        meta.setdefault("campaign_id", str(campaign_id))
    received = row.get("received_at")
    if received:
        meta.setdefault("ingested_at", _fmt_sqlite_ts(received))
    meta["shadow_from_pg"] = True
    meta["pg_sync_version"] = int(row.get("sync_version") or 0)

    phone = str(row.get("phone") or "")
    email = str(row.get("email") or "")
    updated_by = str(row.get("updated_by") or row.get("write_source") or "shadow_sync")[:120]
    created = _fmt_sqlite_ts(row.get("created_at"))
    updated = _fmt_sqlite_ts(row.get("updated_at") or row.get("synced_at") or created)

    return {
        "id": int(row["sqlite_lead_id"]),
        "full_name": str(row.get("full_name") or "")[:240],
        "phone": phone[:80],
        "phone_norm": _phone_norm(phone),
        "email": email[:240],
        "email_norm": _email_norm(email),
        "source": str(row.get("source") or "other")[:64],
        "status": str(row.get("status") or "new")[:64],
        "owner_id": int(row["owner_id"]) if row.get("owner_id") is not None else None,
        "is_duplicate": 1 if row.get("is_duplicate") else 0,
        "meta_json": json.dumps(meta, ensure_ascii=False),
        "created_at": created,
        "updated_at": updated,
        "created_by": updated_by,
        "updated_by": updated_by,
        "sync_version": int(row.get("sync_version") or 0),
    }


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_leads)").fetchall()}
    if cols:
        return
    from crm_lead_store import ensure_lead_schema

    ensure_lead_schema(conn)


def upsert_sqlite_lead(record: dict[str, Any]) -> str:
    """Upsert one lead into SQLite. Returns 'insert' or 'update'."""
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        _ensure_sqlite_schema(conn)
        existing = conn.execute(
            "SELECT id FROM crm_leads WHERE id = ?",
            (record["id"],),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE crm_leads SET
                    full_name = ?, phone = ?, phone_norm = ?, email = ?, email_norm = ?,
                    status = ?, source = ?, owner_id = ?, is_duplicate = ?, meta_json = ?,
                    updated_at = ?, updated_by = ?
                WHERE id = ?
                """,
                (
                    record["full_name"],
                    record["phone"],
                    record["phone_norm"],
                    record["email"],
                    record["email_norm"],
                    record["status"],
                    record["source"],
                    record["owner_id"],
                    record["is_duplicate"],
                    record["meta_json"],
                    record["updated_at"],
                    record["updated_by"],
                    record["id"],
                ),
            )
            conn.commit()
            return "update"
        conn.execute(
            """
            INSERT INTO crm_leads (
                id, full_name, phone, phone_norm, email, email_norm, source, status,
                owner_id, is_duplicate, meta_json, created_at, updated_at,
                created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["full_name"],
                record["phone"],
                record["phone_norm"],
                record["email"],
                record["email_norm"],
                record["source"],
                record["status"],
                record["owner_id"],
                record["is_duplicate"],
                record["meta_json"],
                record["created_at"],
                record["updated_at"],
                record["created_by"],
                record["updated_by"],
            ),
        )
        conn.commit()
        return "insert"
    finally:
        conn.close()


def _get_shadow_watermark() -> int:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_pg_version FROM crm_leads_shadow_state WHERE id = 1")
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0


def _update_shadow_state(*, last_pg_version: int, last_sqlite_id: int, rows: int) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE crm_leads_shadow_state
                SET last_pg_version = GREATEST(last_pg_version, %s),
                    last_sqlite_id = GREATEST(last_sqlite_id, %s),
                    last_shadow_at = NOW(),
                    rows_shadowed = rows_shadowed + %s,
                    updated_at = NOW()
                WHERE id = 1
                """,
                (last_pg_version, last_sqlite_id, rows),
            )
            cur.execute(
                """
                UPDATE crm_leads_sync_state
                SET last_shadow_at = NOW(), updated_at = NOW()
                WHERE id = 1
                """
            )
        conn.commit()


def _fetch_pg_rows(*, after_version: int, lead_ids: list[int] | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            if lead_ids:
                cur.execute(
                    """
                    SELECT sqlite_lead_id, full_name, phone, email, status, source,
                           owner_id, is_duplicate, meta_json, agency_client_id, channel,
                           external_lead_id, campaign_id, received_at, created_at,
                           synced_at, sync_version, updated_at, updated_by, write_source
                    FROM crm_leads
                    WHERE sqlite_lead_id = ANY(%s)
                      AND COALESCE(write_source, 'sync') <> 'sync'
                    ORDER BY sync_version ASC
                    """,
                    (lead_ids,),
                )
            else:
                cur.execute(_PG_SELECT, (after_version, max(1, min(int(limit), 1000))))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _apply_rows(rows: list[dict[str, Any]], *, watermark: int) -> dict[str, Any]:
    synced = 0
    inserted = 0
    updated = 0
    max_version = watermark
    max_id = 0
    for row in rows:
        rec = pg_row_to_sqlite_record(row)
        action = upsert_sqlite_lead(rec)
        synced += 1
        if action == "insert":
            inserted += 1
        else:
            updated += 1
        max_version = max(max_version, int(row.get("sync_version") or 0))
        max_id = max(max_id, int(row["sqlite_lead_id"]))
    if synced:
        _update_shadow_state(last_pg_version=max_version, last_sqlite_id=max_id, rows=synced)
    return {
        "synced": synced,
        "inserted": inserted,
        "updated": updated,
        "last_pg_version": max_version,
        "last_sqlite_id": max_id,
    }


def sync_shadow_lead_ids(lead_ids: list[int]) -> dict[str, Any]:
    if not lead_ids:
        return {"ok": True, "synced": 0, "skipped": True, "reason": "no_ids"}
    if not lead_shadow_sync_enabled():
        return {"ok": True, "synced": 0, "skipped": True, "reason": "disabled"}
    if not pg_shadow_ready():
        return {"ok": False, "synced": 0, "error": "pg_shadow_not_ready"}

    watermark = _get_shadow_watermark()
    rows = _fetch_pg_rows(after_version=0, lead_ids=[int(i) for i in lead_ids])
    stats = _apply_rows(rows, watermark=watermark)
    return {"ok": True, **stats}


WRITE_COMPARE_FIELDS = ("owner_id", "status")


def _sqlite_write_fields(lead_id: int) -> dict[str, Any] | None:
    import sqlite3

    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, owner_id, status FROM crm_leads WHERE id = ?",
            (int(lead_id),),
        ).fetchone()
        if not row:
            return None
        return {"id": int(row["id"]), "owner_id": row["owner_id"], "status": row["status"] or ""}
    finally:
        conn.close()


def _pg_write_fields(lead_id: int) -> dict[str, Any] | None:
    lead = get_pg_lead_v1(lead_id)
    if not lead:
        return None
    return {"id": lead["id"], "owner_id": lead.get("owner_id"), "status": lead.get("status") or ""}


def sync_shadow_repair_gaps(*, limit: int = 500) -> dict[str, Any]:
    """
    Sync PG nest/staging rows missing from SQLite or with write-field drift.
    Used by Phase 2 gate pack before dual-run checks.
    """
    import sqlite3

    if not pg_shadow_ready():
        return {"ok": False, "error": "pg_shadow_not_ready", "repaired": 0}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sqlite_lead_id FROM crm_leads
                WHERE COALESCE(write_source, 'sync') <> 'sync'
                  AND is_duplicate IS NOT TRUE
                ORDER BY sqlite_lead_id DESC
                LIMIT %s
                """,
                (max(1, min(int(limit), 2000)),),
            )
            pg_ids = [int(r[0]) for r in cur.fetchall()]

    conn_sql = sqlite3.connect(sqlite_db_path())
    try:
        sqlite_ids = {
            int(r[0])
            for r in conn_sql.execute(
                "SELECT id FROM crm_leads WHERE COALESCE(is_duplicate, 0) = 0"
            ).fetchall()
        }
    finally:
        conn_sql.close()

    missing = [lead_id for lead_id in pg_ids if lead_id not in sqlite_ids]
    drift: list[int] = []
    for lead_id in pg_ids:
        if lead_id in missing:
            continue
        pg = _pg_write_fields(lead_id)
        sql = _sqlite_write_fields(lead_id)
        if not pg or not sql:
            continue
        for field in WRITE_COMPARE_FIELDS:
            if pg.get(field) != sql.get(field):
                drift.append(lead_id)
                break

    repair_ids = list(dict.fromkeys(missing + drift))
    if not repair_ids:
        return {"ok": True, "repaired": 0, "missing_ids": [], "drift_ids": []}

    watermark = _get_shadow_watermark()
    rows = _fetch_pg_rows(after_version=0, lead_ids=repair_ids)
    stats = _apply_rows(rows, watermark=watermark)
    return {
        "ok": True,
        "repaired": int(stats.get("synced") or 0),
        "missing_ids": missing[:20],
        "drift_ids": drift[:20],
        **stats,
    }


def sync_shadow_incremental(*, batch_size: int = 200) -> dict[str, Any]:
    if not lead_shadow_sync_enabled():
        return {"ok": True, "synced": 0, "skipped": True, "reason": "disabled"}
    if not pg_shadow_ready():
        return {"ok": False, "synced": 0, "error": "pg_shadow_not_ready"}

    watermark = _get_shadow_watermark()
    rows = _fetch_pg_rows(after_version=watermark, limit=batch_size)
    stats = _apply_rows(rows, watermark=watermark)
    return {
        "ok": True,
        "watermark_before": watermark,
        **stats,
    }


def sync_shadow_full(*, batch_size: int = 500, max_batches: int = 100) -> dict[str, Any]:
    """Backfill PG-authoritative rows into SQLite shadow."""
    if not lead_shadow_sync_enabled():
        return {"ok": True, "synced": 0, "skipped": True, "reason": "disabled"}
    if not pg_shadow_ready():
        return {"ok": False, "synced": 0, "error": "pg_shadow_not_ready"}

    total = 0
    inserted = 0
    updated = 0
    watermark = _get_shadow_watermark()
    batches = 0
    while batches < max_batches:
        rows = _fetch_pg_rows(after_version=watermark, limit=batch_size)
        if not rows:
            break
        stats = _apply_rows(rows, watermark=watermark)
        total += int(stats["synced"])
        inserted += int(stats["inserted"])
        updated += int(stats["updated"])
        watermark = int(stats["last_pg_version"])
        batches += 1
        if len(rows) < batch_size:
            break
    return {
        "ok": True,
        "synced": total,
        "inserted": inserted,
        "updated": updated,
        "batches": batches,
        "last_pg_version": watermark,
    }


def get_pg_lead_v1(lead_id: int) -> dict[str, Any] | None:
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


def reconcile_leads_pg_primary(*, sample_size: int = 50) -> dict[str, Any]:
    """Compare PG (authoritative) vs SQLite shadow — Phase 2 W2."""
    if not pg_shadow_ready():
        return {"ok": False, "error": "pg_shadow_not_ready"}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM crm_leads WHERE is_duplicate IS NOT TRUE")
            pg_total = int(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT sqlite_lead_id FROM crm_leads
                WHERE is_duplicate IS NOT TRUE
                ORDER BY sqlite_lead_id DESC
                LIMIT %s
                """,
                (max(1, min(sample_size, 500)),),
            )
            ids = [int(r[0]) for r in cur.fetchall()]

    conn_sql = sqlite3.connect(sqlite_db_path())
    try:
        sqlite_total = int(
            conn_sql.execute("SELECT COUNT(*) FROM crm_leads WHERE COALESCE(is_duplicate, 0) = 0").fetchone()[0]
        )
    finally:
        conn_sql.close()

    mismatches: list[dict[str, Any]] = []
    for lead_id in ids:
        pg_lead = get_pg_lead_v1(lead_id)
        sqlite_lead = get_lead_v1(lead_id)
        if pg_lead is None and sqlite_lead is None:
            continue
        if pg_lead is None or sqlite_lead is None:
            mismatches.append(
                {"id": lead_id, "error": "missing_side", "pg": bool(pg_lead), "sqlite": bool(sqlite_lead)}
            )
            continue
        from ptt_crm.dual_run import diff_lead_v1

        diffs = diff_lead_v1(pg_lead, sqlite_lead)
        if diffs:
            mismatches.append({"id": lead_id, "diffs": [d.__dict__ for d in diffs]})

    shadow = {}
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_pg_version, last_shadow_at, rows_shadowed FROM crm_leads_shadow_state WHERE id = 1"
                )
                row = cur.fetchone()
                if row:
                    shadow = {
                        "last_pg_version": int(row[0] or 0),
                        "last_shadow_at": row[1].isoformat() if row[1] else None,
                        "rows_shadowed": int(row[2] or 0),
                    }
    except Exception as exc:
        shadow = {"error": str(exc)}

    return {
        "ok": len(mismatches) == 0,
        "mode": "pg_primary",
        "pg_total": pg_total,
        "sqlite_total": sqlite_total,
        "sample_size": len(ids),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "shadow_state": shadow,
    }
