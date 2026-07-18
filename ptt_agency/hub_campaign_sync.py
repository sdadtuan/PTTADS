"""Hub SQLite campaigns → PostgreSQL hub_campaign_map (Phase 2 P0)."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.db import json_dumps, pg_connection

logger = logging.getLogger(__name__)

_META_ID_RE = re.compile(r"^[0-9]{5,20}$")


def pg_hub_map_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_v3_ready

        return pg_v3_ready()
    except Exception as exc:
        logger.debug("pg_hub_map_ready: %s", exc)
        return False


def normalize_meta_campaign_id(raw: str | None) -> str:
    return re.sub(r"\D", "", str(raw or "").strip())


def pg_channel_for_campaign(*, channel: str, external_ref: str) -> str | None:
    ch = str(channel or "").strip().lower()
    ref = normalize_meta_campaign_id(external_ref)
    if ch in {"meta", "facebook"}:
        return "meta" if ref else None
    if ch == "ads" and ref and _META_ID_RE.match(ref):
        return "meta"
    if ch == "zalo":
        return "zalo"
    if ch == "google":
        return "google"
    if ref and _META_ID_RE.match(ref):
        return "meta"
    return None


def _utc_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_target_cpl(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        num = float(value)
        return num if num > 0 else None
    except (TypeError, ValueError):
        return None


def _resolve_external_account_id(client_id: str) -> str | None:
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT external_account_id
                    FROM client_channel_accounts
                    WHERE client_id = %s::uuid
                      AND channel = 'meta'
                      AND status = 'active'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (client_id,),
                )
                row = cur.fetchone()
                return str(row[0]).strip() if row and row[0] else None
    except Exception as exc:
        logger.debug("resolve external_account_id: %s", exc)
        return None


def _client_exists(client_id: str) -> bool:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM clients WHERE id = %s::uuid", (client_id,))
            return cur.fetchone() is not None


def campaign_sync_payload(row: dict[str, Any]) -> dict[str, Any] | None:
    """Build upsert payload from SQLite crm_campaigns row."""
    client_id = str(row.get("agency_client_id") or "").strip()
    external_ref = normalize_meta_campaign_id(str(row.get("external_ref") or ""))
    channel = pg_channel_for_campaign(
        channel=str(row.get("channel") or ""),
        external_ref=external_ref,
    )
    if not client_id or not external_ref or not channel:
        return None
    if channel == "meta" and not _META_ID_RE.match(external_ref):
        return None
    if not _client_exists(client_id):
        return None

    hub_id = int(row.get("id") or 0)
    if hub_id <= 0:
        return None

    target = _parse_target_cpl(row.get("target_cpl_vnd"))
    active = bool(int(row.get("active") or 0))
    return {
        "client_id": client_id,
        "hub_campaign_id": hub_id,
        "channel": channel,
        "external_campaign_id": external_ref,
        "external_campaign_name": str(row.get("name") or "")[:255] or None,
        "external_account_id": _resolve_external_account_id(client_id),
        "target_cpl_vnd": target,
        "active": active,
        "meta": {
            "hub_code": str(row.get("code") or ""),
            "utm_campaign": str(row.get("utm_campaign") or ""),
            "sqlite_channel": str(row.get("channel") or ""),
        },
    }


def upsert_hub_campaign_map(payload: dict[str, Any]) -> dict[str, Any]:
    """Upsert one row into hub_campaign_map."""
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM hub_campaign_map
                WHERE client_id = %s::uuid
                  AND hub_campaign_id = %s
                  AND channel = %s
                LIMIT 1
                """,
                (payload["client_id"], payload["hub_campaign_id"], payload["channel"]),
            )
            existing = cur.fetchone()
            meta_json = json_dumps(payload.get("meta") or {})

            if existing:
                map_id = str(existing[0])
                cur.execute(
                    """
                    UPDATE hub_campaign_map
                    SET external_campaign_id = %s,
                        external_campaign_name = COALESCE(%s, external_campaign_name),
                        external_account_id = COALESCE(%s, external_account_id),
                        target_cpl_vnd = %s,
                        active = %s,
                        meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    RETURNING id
                    """,
                    (
                        payload["external_campaign_id"],
                        payload.get("external_campaign_name"),
                        payload.get("external_account_id"),
                        payload.get("target_cpl_vnd"),
                        payload.get("active", True),
                        meta_json,
                        map_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO hub_campaign_map (
                        client_id, hub_campaign_id, channel,
                        external_campaign_id, external_campaign_name,
                        external_account_id, target_cpl_vnd, active, meta
                    ) VALUES (
                        %s::uuid, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT (client_id, channel, external_campaign_id)
                    DO UPDATE SET
                        hub_campaign_id = EXCLUDED.hub_campaign_id,
                        external_campaign_name = EXCLUDED.external_campaign_name,
                        external_account_id = COALESCE(EXCLUDED.external_account_id, hub_campaign_map.external_account_id),
                        target_cpl_vnd = EXCLUDED.target_cpl_vnd,
                        active = EXCLUDED.active,
                        meta = hub_campaign_map.meta || EXCLUDED.meta,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (
                        payload["client_id"],
                        payload["hub_campaign_id"],
                        payload["channel"],
                        payload["external_campaign_id"],
                        payload.get("external_campaign_name"),
                        payload.get("external_account_id"),
                        payload.get("target_cpl_vnd"),
                        payload.get("active", True),
                        meta_json,
                    ),
                )
                row = cur.fetchone()
                map_id = str(row[0]) if row else None

            conn.commit()
            return {
                "ok": True,
                "map_id": map_id,
                "client_id": payload["client_id"],
                "hub_campaign_id": payload["hub_campaign_id"],
                "external_campaign_id": payload["external_campaign_id"],
            }


def sync_campaign_row(
    row: dict[str, Any],
    *,
    sqlite_conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Sync one SQLite campaign dict to PG; optionally stamp sync columns on SQLite."""
    campaign_id = int(row.get("id") or 0)
    if not pg_hub_map_ready():
        out = {"ok": False, "skipped": True, "reason": "pg_hub_map_not_ready", "campaign_id": campaign_id}
        _stamp_sqlite_sync(sqlite_conn, campaign_id, ok=False, error=out["reason"])
        return out

    payload = campaign_sync_payload(row)
    if not payload:
        reason = "missing_client_or_meta_campaign_id"
        _stamp_sqlite_sync(sqlite_conn, campaign_id, ok=False, error=reason)
        return {"ok": True, "skipped": True, "reason": reason, "campaign_id": campaign_id}

    try:
        result = upsert_hub_campaign_map(payload)
        _stamp_sqlite_sync(sqlite_conn, campaign_id, ok=True, error="")
        return {**result, "campaign_id": campaign_id}
    except Exception as exc:
        logger.warning("hub_campaign_map sync failed campaign_id=%s: %s", campaign_id, exc)
        _stamp_sqlite_sync(sqlite_conn, campaign_id, ok=False, error=str(exc))
        return {"ok": False, "error": str(exc), "campaign_id": campaign_id}


def sync_campaign_by_id(
    campaign_id: int,
    *,
    sqlite_path: str,
) -> dict[str, Any]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM crm_campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "campaign_not_found", "campaign_id": campaign_id}
        return sync_campaign_row(dict(row), sqlite_conn=conn)
    finally:
        conn.close()


def sync_all_from_sqlite(
    *,
    sqlite_path: str,
    include_inactive: bool = False,
) -> dict[str, Any]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        if include_inactive:
            rows = conn.execute("SELECT * FROM crm_campaigns ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM crm_campaigns WHERE active = 1 ORDER BY id"
            ).fetchall()

        synced = 0
        skipped = 0
        failed = 0
        results: list[dict[str, Any]] = []
        for row in rows:
            out = sync_campaign_row(dict(row), sqlite_conn=conn)
            results.append(out)
            if out.get("ok") and out.get("map_id"):
                synced += 1
            elif out.get("skipped"):
                skipped += 1
            elif not out.get("ok"):
                failed += 1
        conn.commit()
        return {
            "ok": failed == 0,
            "total": len(rows),
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }
    finally:
        conn.close()


def _stamp_sqlite_sync(
    conn: sqlite3.Connection | None,
    campaign_id: int,
    *,
    ok: bool,
    error: str,
) -> None:
    if conn is None or campaign_id <= 0:
        return
    ts = _utc_ts()
    try:
        conn.execute(
            """
            UPDATE crm_campaigns
            SET hub_map_synced_at = ?, hub_map_last_error = ?
            WHERE id = ?
            """,
            (ts if ok else "", error[:500] if error else "", campaign_id),
        )
    except sqlite3.OperationalError:
        pass


def enrich_campaigns_with_client_codes(campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach agency_client_code for Hub UI (best-effort)."""
    ids = {str(c.get("agency_client_id") or "").strip() for c in campaigns}
    ids.discard("")
    if not ids or not pg_hub_map_ready():
        return campaigns

    codes: dict[str, str] = {}
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, code FROM clients
                    WHERE id = ANY(%s::uuid[])
                    """,
                    (list(ids),),
                )
                for cid, code in cur.fetchall():
                    codes[str(cid)] = str(code)
    except Exception as exc:
        logger.debug("enrich client codes: %s", exc)
        return campaigns

    out: list[dict[str, Any]] = []
    for c in campaigns:
        item = dict(c)
        cid = str(item.get("agency_client_id") or "").strip()
        item["agency_client_code"] = codes.get(cid) if cid else None
        item["hub_map_ready"] = bool(
            cid
            and normalize_meta_campaign_id(str(item.get("external_ref") or ""))
            and pg_channel_for_campaign(
                channel=str(item.get("channel") or ""),
                external_ref=normalize_meta_campaign_id(str(item.get("external_ref") or "")),
            )
        )
        item["hub_map_synced"] = bool(str(item.get("hub_map_synced_at") or "").strip())
        out.append(item)
    return out
