"""Lead read API — SQLite CRM with v1 response shape."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from ptt_jobs.config import sqlite_db_path


def _parse_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def lead_row_to_v1(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Normalize lead row for /api/v1/leads (target NestJS parity)."""
    d = dict(row)
    meta = _parse_meta(d.pop("meta_json", "{}"))
    channel = str(
        meta.get("channel")
        or meta.get("ingest_channel")
        or meta.get("utm_source")
        or d.get("source")
        or ""
    )
    return {
        "id": int(d["id"]),
        "full_name": d.get("full_name") or "",
        "phone": d.get("phone") or "",
        "email": d.get("email") or "",
        "status": d.get("status") or "",
        "source": d.get("source") or "",
        "channel": channel,
        "client_id": meta.get("agency_client_id") or None,
        "campaign_id": str(
            meta.get("campaign_id")
            or meta.get("facebook_campaign_id")
            or meta.get("zalo_campaign_id")
            or ""
        )
        or None,
        "external_lead_id": str(
            meta.get("facebook_leadgen_id")
            or meta.get("zalo_lead_id")
            or meta.get("external_lead_id")
            or ""
        )
        or None,
        "owner_id": int(d["owner_id"]) if d.get("owner_id") else None,
        "created_at": d.get("created_at") or "",
        "received_at": str(meta.get("ingested_at") or meta.get("facebook_created_time") or d.get("created_at") or ""),
        "is_duplicate": bool(d.get("is_duplicate")),
    }


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def list_leads_v1(
    *,
    client_id: str | None = None,
    status: str | None = None,
    source: str | None = None,
    channel: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[str] = ["COALESCE(l.is_duplicate, 0) = 0"]
    params: list[Any] = []

    if client_id:
        clauses.append("json_extract(l.meta_json, '$.agency_client_id') = ?")
        params.append(client_id.strip())
    if status:
        clauses.append("l.status = ?")
        params.append(status.strip())
    if source:
        clauses.append("l.source = ?")
        params.append(source.strip())
    if channel:
        ch = channel.strip().lower()
        clauses.append(
            """(
                lower(COALESCE(json_extract(l.meta_json, '$.channel'), '')) = ?
                OR lower(COALESCE(json_extract(l.meta_json, '$.ingest_channel'), '')) = ?
                OR lower(COALESCE(l.source, '')) = ?
            )"""
        )
        params.extend([ch, ch, ch])
    if q:
        like = f"%{q.strip()}%"
        clauses.append("(l.full_name LIKE ? OR l.phone LIKE ? OR l.email LIKE ?)")
        params.extend([like, like, like])

    where = " WHERE " + " AND ".join(clauses)
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))

    conn = _connect()
    try:
        total_row = conn.execute(f"SELECT COUNT(*) AS c FROM crm_leads l{where}", params).fetchone()
        total = int(total_row["c"] or 0) if total_row else 0
        rows = conn.execute(
            f"""
            SELECT l.id, l.full_name, l.phone, l.email, l.status, l.source,
                   l.owner_id, l.created_at, l.is_duplicate, l.meta_json
            FROM crm_leads l
            {where}
            ORDER BY l.id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, lim, off],
        ).fetchall()
        return [lead_row_to_v1(r) for r in rows], total
    finally:
        conn.close()


def get_lead_v1(lead_id: int) -> dict[str, Any] | None:
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT l.id, l.full_name, l.phone, l.email, l.status, l.source,
                   l.owner_id, l.created_at, l.is_duplicate, l.meta_json
            FROM crm_leads l
            WHERE l.id = ?
            """,
            (lead_id,),
        ).fetchone()
        return lead_row_to_v1(row) if row else None
    finally:
        conn.close()
