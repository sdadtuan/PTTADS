"""Lead ingest rules — PG snapshot (Phase 2 cutover, no SQLite OLTP reads on ingest path)."""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.config import sqlite_db_path
from ptt_jobs.db import pg_available, pg_connection

logger = logging.getLogger(__name__)

_EMPTY_SNAPSHOT: dict[str, Any] = {
    "lead_config": {},
    "staff_rows": [],
    "assignment_state": [],
    "staff_assign_scope": [],
    "catalog_services": [],
    "catalog_industries": [],
    "staff_workload": {},
}


def ingest_rules_source() -> str:
    from ptt_crm.config import ingest_rules_source as _src

    return _src()


def ingest_rules_from_pg() -> bool:
    return ingest_rules_source() == "pg"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pg_ingest_rules_ready() -> bool:
    try:
        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'crm_ingest_rules_snapshot'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.debug("pg_ingest_rules_ready: %s", exc)
        return False


def fetch_pg_ingest_rules_snapshot() -> dict[str, Any] | None:
    if not pg_ingest_rules_ready():
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT lead_config, staff_rows, assignment_state, staff_assign_scope,
                       catalog_services, catalog_industries, staff_workload, synced_at
                FROM crm_ingest_rules_snapshot
                WHERE id = 1
                """
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def snapshot_has_rules(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    cfg = data.get("lead_config")
    if isinstance(cfg, dict) and cfg:
        return True
    staff = data.get("staff_rows")
    return isinstance(staff, list) and len(staff) > 0


def _collect_sqlite_rules_snapshot(*, sqlite_path: str | None = None) -> dict[str, Any]:
    path = sqlite_path or sqlite_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        from crm_lead_assign_scope import ensure_staff_assign_scope_schema
        from crm_lead_catalog import ensure_lead_catalog_schema
        from crm_lead_rules import ensure_lead_settings_schema, fetch_lead_config

        ensure_lead_settings_schema(conn)
        ensure_lead_catalog_schema(conn)
        ensure_staff_assign_scope_schema(conn)

        lead_config = fetch_lead_config(conn)
        staff_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, name, notes, COALESCE(active, 1) AS active,
                       COALESCE(sales_level, 'b') AS sales_level,
                       COALESCE(internal_code, '') AS internal_code
                FROM crm_staff
                ORDER BY id
                """
            ).fetchall()
        ]
        assignment_state = [
            dict(r)
            for r in conn.execute(
                "SELECT pool_key, last_staff_id FROM crm_assignment_state ORDER BY pool_key"
            ).fetchall()
        ]
        staff_assign_scope = [
            dict(r)
            for r in conn.execute(
                """
                SELECT staff_id, industry_slug, service_slug, active
                FROM crm_staff_assign_scope
                ORDER BY staff_id, industry_slug, service_slug
                """
            ).fetchall()
        ]
        catalog_services = [
            dict(r)
            for r in conn.execute(
                """
                SELECT slug, name, description, sort_order, active, created_at, updated_at
                FROM crm_catalog_services
                ORDER BY sort_order, slug
                """
            ).fetchall()
        ]
        catalog_industries = [
            dict(r)
            for r in conn.execute(
                """
                SELECT slug, name, description, traits_json, sort_order, active, created_at, updated_at
                FROM crm_catalog_industries
                ORDER BY sort_order, slug
                """
            ).fetchall()
        ]
        return {
            "lead_config": lead_config,
            "staff_rows": staff_rows,
            "assignment_state": assignment_state,
            "staff_assign_scope": staff_assign_scope,
            "catalog_services": catalog_services,
            "catalog_industries": catalog_industries,
            "staff_workload": _collect_staff_workload_from_pg(),
            "synced_from": path,
        }
    finally:
        conn.close()


def _collect_staff_workload_from_pg() -> dict[str, Any]:
    """Owner workload counts from PG crm_leads (for auto-assign cap simulation)."""
    if not pg_available():
        return {}
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT owner_id,
                           COUNT(*) FILTER (
                               WHERE created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
                           ) AS leads_today,
                           COUNT(*) FILTER (
                               WHERE status NOT IN ('won', 'lost')
                           ) AS open_load
                    FROM crm_leads
                    WHERE owner_id IS NOT NULL
                      AND COALESCE(is_duplicate, FALSE) IS NOT TRUE
                    GROUP BY owner_id
                    """
                )
                rows = cur.fetchall()
        out: dict[str, Any] = {}
        for owner_id, leads_today, open_load in rows:
            out[str(int(owner_id))] = {
                "leads_today": int(leads_today or 0),
                "open_load": int(open_load or 0),
            }
        return out
    except Exception as exc:
        logger.debug("staff workload from pg skipped: %s", exc)
        return {}


def sync_ingest_rules_from_sqlite(*, sqlite_path: str | None = None) -> dict[str, Any]:
    """Copy SQLite lead rules → PG snapshot (run before Phase 2 cutover / on cron)."""
    if not pg_ingest_rules_ready():
        from ptt_crm.pg_schema import apply_ddl_v3_leads_ingest_config

        apply_ddl_v3_leads_ingest_config()

    payload = _collect_sqlite_rules_snapshot(sqlite_path=sqlite_path)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE crm_ingest_rules_snapshot SET
                    lead_config = %s::jsonb,
                    staff_rows = %s::jsonb,
                    assignment_state = %s::jsonb,
                    staff_assign_scope = %s::jsonb,
                    catalog_services = %s::jsonb,
                    catalog_industries = %s::jsonb,
                    staff_workload = %s::jsonb,
                    synced_at = NOW(),
                    synced_from = %s
                WHERE id = 1
                """,
                (
                    json.dumps(payload["lead_config"], ensure_ascii=False),
                    json.dumps(payload["staff_rows"], ensure_ascii=False),
                    json.dumps(payload["assignment_state"], ensure_ascii=False),
                    json.dumps(payload["staff_assign_scope"], ensure_ascii=False),
                    json.dumps(payload["catalog_services"], ensure_ascii=False),
                    json.dumps(payload["catalog_industries"], ensure_ascii=False),
                    json.dumps(payload["staff_workload"], ensure_ascii=False),
                    str(payload.get("synced_from") or "sqlite")[:240],
                ),
            )
        conn.commit()
    return {
        "ok": True,
        "staff_count": len(payload["staff_rows"]),
        "synced_at": _utc_now(),
    }


def _open_sqlite_readonly() -> sqlite3.Connection:
    path = sqlite_db_path()
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _hydrate_rules_conn_from_snapshot(data: dict[str, Any]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from crm_lead_assign_scope import ensure_staff_assign_scope_schema
    from crm_lead_catalog import ensure_lead_catalog_schema
    from crm_lead_rules import ensure_lead_settings_schema

    ensure_lead_settings_schema(conn)
    ensure_lead_catalog_schema(conn)
    ensure_staff_assign_scope_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            sales_level TEXT NOT NULL DEFAULT 'b',
            internal_code TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_assignment_state (
            pool_key TEXT PRIMARY KEY,
            last_staff_id INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            created_at TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'intake',
            is_duplicate INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    lead_config = data.get("lead_config") if isinstance(data.get("lead_config"), dict) else {}
    conn.execute(
        """
        INSERT INTO crm_lead_settings (config_key, config_json, updated_at, updated_by)
        VALUES ('global', ?, ?, 'ingest_snapshot')
        """,
        (json.dumps(lead_config, ensure_ascii=False), _utc_now()),
    )

    for row in data.get("staff_rows") or []:
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO crm_staff (id, name, notes, active, sales_level, internal_code)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["id"]),
                str(row.get("name") or "")[:240],
                str(row.get("notes") or "")[:2000],
                int(row.get("active", 1)),
                str(row.get("sales_level") or "b")[:8],
                str(row.get("internal_code") or "")[:64],
            ),
        )

    for row in data.get("assignment_state") or []:
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO crm_assignment_state (pool_key, last_staff_id)
            VALUES (?, ?)
            ON CONFLICT(pool_key) DO UPDATE SET last_staff_id = excluded.last_staff_id
            """,
            (str(row.get("pool_key") or ""), int(row.get("last_staff_id") or 0)),
        )

    for row in data.get("staff_assign_scope") or []:
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO crm_staff_assign_scope (staff_id, industry_slug, service_slug, active)
            VALUES (?, ?, ?, ?)
            """,
            (
                int(row["staff_id"]),
                str(row.get("industry_slug") or "*")[:80],
                str(row.get("service_slug") or "*")[:80],
                int(row.get("active", 1)),
            ),
        )

    conn.execute("DELETE FROM crm_catalog_services")
    for row in data.get("catalog_services") or []:
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO crm_catalog_services
                (slug, name, description, sort_order, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row.get("slug") or ""),
                str(row.get("name") or ""),
                str(row.get("description") or ""),
                int(row.get("sort_order") or 0),
                int(row.get("active", 1)),
                str(row.get("created_at") or ""),
                str(row.get("updated_at") or ""),
            ),
        )

    conn.execute("DELETE FROM crm_catalog_industries")
    for row in data.get("catalog_industries") or []:
        if not isinstance(row, dict):
            continue
        conn.execute(
            """
            INSERT INTO crm_catalog_industries
                (slug, name, description, traits_json, sort_order, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row.get("slug") or ""),
                str(row.get("name") or ""),
                str(row.get("description") or ""),
                str(row.get("traits_json") or "{}"),
                int(row.get("sort_order") or 0),
                int(row.get("active", 1)),
                str(row.get("created_at") or ""),
                str(row.get("updated_at") or ""),
            ),
        )

    workload = data.get("staff_workload") if isinstance(data.get("staff_workload"), dict) else {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stub_id = 1
    for owner_key, stats in workload.items():
        if not isinstance(stats, dict):
            continue
        owner_id = int(owner_key)
        for _ in range(int(stats.get("leads_today") or 0)):
            conn.execute(
                """
                INSERT INTO crm_leads (id, owner_id, created_at, status, is_duplicate)
                VALUES (?, ?, ?, 'intake', 0)
                """,
                (stub_id, owner_id, f"{today} 12:00:00"),
            )
            stub_id += 1
        for _ in range(int(stats.get("open_load") or 0)):
            conn.execute(
                """
                INSERT INTO crm_leads (id, owner_id, created_at, status, is_duplicate)
                VALUES (?, ?, ?, 'intake', 0)
                """,
                (stub_id, owner_id, "2020-01-01 00:00:00"),
            )
            stub_id += 1

    conn.commit()
    return conn


def open_ingest_rules_conn(*, prefer_pg: bool | None = None) -> sqlite3.Connection:
    """
    Connection for scoring / assign / facebook config on ingest path.
    PG snapshot when enabled; falls back to SQLite read-only.
    """
    use_pg = ingest_rules_from_pg() if prefer_pg is None else bool(prefer_pg)
    if use_pg and pg_ingest_rules_ready():
        snap = fetch_pg_ingest_rules_snapshot()
        if snapshot_has_rules(snap):
            return _hydrate_rules_conn_from_snapshot(snap or _EMPTY_SNAPSHOT)
        logger.warning("PG ingest rules snapshot empty — falling back to SQLite read-only")
    return _open_sqlite_readonly()


def fetch_facebook_config_for_ingest(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    from crm_facebook_config import fetch_facebook_config, merge_facebook_config

    rules_conn = conn or open_ingest_rules_conn()
    owns = conn is None
    try:
        if owns and ingest_rules_from_pg() and pg_ingest_rules_ready():
            snap = fetch_pg_ingest_rules_snapshot()
            if snapshot_has_rules(snap):
                cfg = (snap or {}).get("lead_config") or {}
                fb_raw = cfg.get("facebook_config") if isinstance(cfg, dict) else {}
                return merge_facebook_config(fb_raw if isinstance(fb_raw, dict) else {})
        return fetch_facebook_config(rules_conn)
    finally:
        if owns:
            rules_conn.close()


def fetch_lead_config_for_ingest(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    from crm_lead_rules import fetch_lead_config

    rules_conn = conn or open_ingest_rules_conn()
    owns = conn is None
    try:
        if owns and ingest_rules_from_pg() and pg_ingest_rules_ready():
            snap = fetch_pg_ingest_rules_snapshot()
            cfg = (snap or {}).get("lead_config")
            if isinstance(cfg, dict) and cfg:
                return dict(cfg)
        return fetch_lead_config(rules_conn)
    finally:
        if owns:
            rules_conn.close()
