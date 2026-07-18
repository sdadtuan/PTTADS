"""P3 — Gỡ luồng RE khỏi funnel Lead (ingest / assign / DB cleanup)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

MIGRATION_KEY = "product_model_p3_re_detach_v1"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _migration_done(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "crm_lead_settings"):
        return False
    row = conn.execute(
        "SELECT config_json FROM crm_lead_settings WHERE config_key = 'global' LIMIT 1"
    ).fetchone()
    if row is None:
        return False
    try:
        cfg = json.loads(str(row["config_json"] or "{}"))
    except (TypeError, json.JSONDecodeError):
        return False
    migrations = cfg.get("migrations") or {}
    return bool(migrations.get(MIGRATION_KEY))


def _mark_migration_done(conn: sqlite3.Connection) -> None:
    from crm_lead_rules import fetch_lead_config, save_lead_config

    cfg = fetch_lead_config(conn)
    migrations = dict(cfg.get("migrations") or {})
    migrations[MIGRATION_KEY] = _ts()
    cfg["migrations"] = migrations
    cfg["product_model_v1"] = True
    cfg["re_lead_funnel_disabled"] = True
    save_lead_config(conn, config=cfg, updated_by="system", ts=_ts())


def clear_re_columns_on_leads(conn: sqlite3.Connection) -> int:
    """Xóa dữ liệu RE legacy còn trên lead (sau R6 migrate add-on)."""
    if not _table_exists(conn, "crm_leads"):
        return 0
    cur = conn.execute(
        """
        UPDATE crm_leads
        SET re_project_id = NULL,
            product_line = '',
            zone = '',
            re_product_id = NULL,
            updated_at = ?
        WHERE (re_project_id IS NOT NULL AND re_project_id != 0)
           OR trim(COALESCE(product_line, '')) != ''
           OR trim(COALESCE(zone, '')) != ''
           OR (re_product_id IS NOT NULL AND re_product_id != 0)
        """,
        (_ts(),),
    )
    return int(cur.rowcount or 0)


def ensure_p3_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    """Chạy migration P3 một lần: R6 add-on + dọn cột RE trên lead."""
    from crm_lead_industry_addon import ensure_r6_schema

    ensure_r6_schema(conn)
    if _migration_done(conn):
        return {"cleared": 0, "skipped": True}
    cleared = clear_re_columns_on_leads(conn)
    _mark_migration_done(conn)
    return {"cleared": cleared, "skipped": False}


def product_model_v1_enabled(conn: sqlite3.Connection | None = None) -> bool:
    """Product Model v1 — funnel không dùng RE project trên lead."""
    if conn is None:
        return True
    try:
        from crm_lead_rules import fetch_lead_config

        cfg = fetch_lead_config(conn)
        if cfg.get("re_lead_funnel_disabled"):
            return True
        migrations = cfg.get("migrations") or {}
        return bool(migrations.get(MIGRATION_KEY))
    except Exception:
        return True


def resolve_facebook_industry_slug(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    *,
    webhook_slug: str | None = None,
) -> str:
    """Ngành mặc định cho lead Facebook — không map qua re_project."""
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    raw = (
        str(item.get("industry_slug") or meta.get("industry_slug") or "").strip()
        or str(item.get("industry") or meta.get("industry") or "").strip()
    )
    if raw:
        from crm_lead_catalog import normalize_industry_slug

        try:
            return normalize_industry_slug(conn, raw)
        except ValueError:
            pass
    if webhook_slug:
        from crm_lead_catalog import normalize_catalog_slug

        guess = normalize_catalog_slug(webhook_slug)
        if guess:
            try:
                from crm_lead_catalog import validate_industry_slug

                return validate_industry_slug(conn, guess)
            except ValueError:
                pass
    return "khac"
