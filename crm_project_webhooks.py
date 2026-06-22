"""Lead webhook theo dự án BĐS — Phase 3: slug URL, map form Facebook → dự án."""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime
from typing import Any

from crm_lead_webhooks import facebook_verify_token, facebook_webhook_callback_url, zalo_webhook_callback_url
from crm_project_leads import validate_re_project_id


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_project_webhook_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_lead_config (
            project_id INTEGER PRIMARY KEY REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            enabled INTEGER NOT NULL DEFAULT 1,
            webhook_slug TEXT UNIQUE,
            webhook_verify_token TEXT NOT NULL DEFAULT '',
            facebook_page_id TEXT NOT NULL DEFAULT '',
            auto_assign INTEGER NOT NULL DEFAULT 1,
            webhook_enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_facebook_forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            page_id TEXT NOT NULL DEFAULT '',
            form_id TEXT NOT NULL,
            form_name TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(form_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_re_project_fb_forms_project "
        "ON crm_re_project_facebook_forms(project_id, active)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_re_project_lead_config_slug "
        "ON crm_re_project_lead_config(webhook_slug) WHERE webhook_slug IS NOT NULL AND webhook_slug != ''"
    )
    lc_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_lead_config)").fetchall()}
    if "zalo_oa_id" not in lc_cols:
        conn.execute(
            "ALTER TABLE crm_re_project_lead_config ADD COLUMN zalo_oa_id TEXT NOT NULL DEFAULT ''"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_zalo_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            oa_id TEXT NOT NULL DEFAULT '',
            campaign_id TEXT NOT NULL,
            campaign_name TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(campaign_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_re_project_zalo_campaigns_project "
        "ON crm_re_project_zalo_campaigns(project_id, active)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_website_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            route_key TEXT NOT NULL,
            route_name TEXT NOT NULL DEFAULT '',
            route_type TEXT NOT NULL DEFAULT 'utm',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(route_key)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_re_project_website_routes_project "
        "ON crm_re_project_website_routes(project_id, active)"
    )


def _default_slug(project_id: int) -> str:
    suffix = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].lower()
    return f"p{int(project_id)}-{suffix}"


def project_webhook_url(slug: str) -> str:
    base = facebook_webhook_callback_url().rstrip("/")
    s = str(slug or "").strip().strip("/")
    if not s:
        return base
    return f"{base}/{s}"


def project_zalo_webhook_url(slug: str) -> str:
    base = zalo_webhook_callback_url().rstrip("/")
    s = str(slug or "").strip().strip("/")
    if not s:
        return base
    return f"{base}/{s}"


def _config_row_to_dict(conn: sqlite3.Connection, row: sqlite3.Row | None, project_id: int) -> dict[str, Any]:
    if row is None:
        slug = _default_slug(project_id)
        return {
            "project_id": int(project_id),
            "enabled": True,
            "webhook_slug": slug,
            "webhook_verify_token": "",
            "webhook_url": project_webhook_url(slug),
            "zalo_webhook_url": project_zalo_webhook_url(slug),
            "facebook_page_id": "",
            "zalo_oa_id": "",
            "auto_assign": True,
            "webhook_enabled": True,
            "forms": [],
            "zalo_campaigns": [],
            "website_routes": [],
            "updated_at": "",
            "updated_by": "",
        }
    d = dict(row)
    slug = str(d.get("webhook_slug") or "").strip() or _default_slug(project_id)
    return {
        "project_id": int(d["project_id"]),
        "enabled": bool(int(d.get("enabled") or 0)),
        "webhook_slug": slug,
        "webhook_verify_token": str(d.get("webhook_verify_token") or ""),
        "webhook_url": project_webhook_url(slug),
        "zalo_webhook_url": project_zalo_webhook_url(slug),
        "facebook_page_id": str(d.get("facebook_page_id") or ""),
        "zalo_oa_id": str(d.get("zalo_oa_id") or ""),
        "auto_assign": bool(int(d.get("auto_assign") if d.get("auto_assign") is not None else 1)),
        "webhook_enabled": bool(int(d.get("webhook_enabled") if d.get("webhook_enabled") is not None else 1)),
        "forms": list_project_facebook_forms(conn, int(project_id)),
        "zalo_campaigns": list_project_zalo_campaigns(conn, int(project_id)),
        "website_routes": list_project_website_routes(conn, int(project_id)),
        "updated_at": str(d.get("updated_at") or ""),
        "updated_by": str(d.get("updated_by") or ""),
    }


def get_project_lead_config(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    validate_re_project_id(conn, project_id)
    ensure_project_webhook_schema(conn)
    row = conn.execute(
        "SELECT * FROM crm_re_project_lead_config WHERE project_id = ?",
        (int(project_id),),
    ).fetchone()
    return _config_row_to_dict(conn, row, int(project_id))


def list_project_facebook_forms(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    ensure_project_webhook_schema(conn)
    rows = conn.execute(
        """
        SELECT id, project_id, page_id, form_id, form_name, active, created_at, updated_at
        FROM crm_re_project_facebook_forms
        WHERE project_id = ?
        ORDER BY form_name, form_id
        """,
        (int(project_id),),
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "project_id": int(r["project_id"]),
            "page_id": str(r["page_id"] or ""),
            "form_id": str(r["form_id"] or ""),
            "form_name": str(r["form_name"] or ""),
            "active": bool(int(r["active"] or 0)),
            "created_at": str(r["created_at"] or ""),
            "updated_at": str(r["updated_at"] or ""),
        }
        for r in rows
    ]


def list_project_zalo_campaigns(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    ensure_project_webhook_schema(conn)
    rows = conn.execute(
        """
        SELECT id, project_id, oa_id, campaign_id, campaign_name, active, created_at, updated_at
        FROM crm_re_project_zalo_campaigns
        WHERE project_id = ?
        ORDER BY campaign_name, campaign_id
        """,
        (int(project_id),),
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "project_id": int(r["project_id"]),
            "oa_id": str(r["oa_id"] or ""),
            "campaign_id": str(r["campaign_id"] or ""),
            "campaign_name": str(r["campaign_name"] or ""),
            "active": bool(int(r["active"] or 0)),
            "created_at": str(r["created_at"] or ""),
            "updated_at": str(r["updated_at"] or ""),
        }
        for r in rows
    ]


def list_project_website_routes(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    ensure_project_webhook_schema(conn)
    rows = conn.execute(
        """
        SELECT id, project_id, route_key, route_name, route_type, active, created_at, updated_at
        FROM crm_re_project_website_routes
        WHERE project_id = ?
        ORDER BY route_name, route_key
        """,
        (int(project_id),),
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "project_id": int(r["project_id"]),
            "route_key": str(r["route_key"] or ""),
            "route_name": str(r["route_name"] or ""),
            "route_type": str(r["route_type"] or "utm"),
            "active": bool(int(r["active"] or 0)),
            "created_at": str(r["created_at"] or ""),
            "updated_at": str(r["updated_at"] or ""),
        }
        for r in rows
    ]


def save_project_lead_config(
    conn: sqlite3.Connection,
    project_id: int,
    payload: dict[str, Any],
    *,
    updated_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    validate_re_project_id(conn, project_id)
    ensure_project_webhook_schema(conn)
    ts = ts or _now_ts()
    existing = conn.execute(
        "SELECT * FROM crm_re_project_lead_config WHERE project_id = ?",
        (int(project_id),),
    ).fetchone()
    slug = str((existing and dict(existing).get("webhook_slug")) or "").strip()
    if not slug:
        slug = _default_slug(project_id)
    verify = str((existing and dict(existing).get("webhook_verify_token")) or "").strip()
    if not verify:
        verify = secrets.token_urlsafe(16)

    enabled = bool(payload.get("enabled", True))
    webhook_enabled = bool(payload.get("webhook_enabled", True))
    auto_assign = bool(payload.get("auto_assign", True))
    page_id = str(payload.get("facebook_page_id") or "").strip()
    zalo_oa_id = str(payload.get("zalo_oa_id") or "").strip()
    if "webhook_slug" in payload:
        raw_slug = str(payload.get("webhook_slug") or "").strip().lower()
        if raw_slug:
            other = conn.execute(
                "SELECT project_id FROM crm_re_project_lead_config WHERE webhook_slug = ? AND project_id != ?",
                (raw_slug, int(project_id)),
            ).fetchone()
            if other:
                raise ValueError(f"Webhook slug «{raw_slug}» đã dùng cho dự án khác.")
            slug = raw_slug
    if payload.get("regenerate_verify_token"):
        verify = secrets.token_urlsafe(16)

    conn.execute(
        """
        INSERT INTO crm_re_project_lead_config (
            project_id, enabled, webhook_slug, webhook_verify_token, facebook_page_id,
            zalo_oa_id, auto_assign, webhook_enabled, updated_at, updated_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET
            enabled = excluded.enabled,
            webhook_slug = excluded.webhook_slug,
            webhook_verify_token = excluded.webhook_verify_token,
            facebook_page_id = excluded.facebook_page_id,
            zalo_oa_id = excluded.zalo_oa_id,
            auto_assign = excluded.auto_assign,
            webhook_enabled = excluded.webhook_enabled,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (
            int(project_id),
            1 if enabled else 0,
            slug,
            verify,
            page_id,
            zalo_oa_id,
            1 if auto_assign else 0,
            1 if webhook_enabled else 0,
            ts,
            str(updated_by or "")[:120],
        ),
    )

    if "forms" in payload and isinstance(payload["forms"], list):
        sync_project_facebook_forms(
            conn,
            project_id,
            payload["forms"],
            default_page_id=page_id,
            ts=ts,
        )

    if "zalo_campaigns" in payload and isinstance(payload["zalo_campaigns"], list):
        sync_project_zalo_campaigns(
            conn,
            project_id,
            payload["zalo_campaigns"],
            default_oa_id=zalo_oa_id,
            ts=ts,
        )

    if "website_routes" in payload and isinstance(payload["website_routes"], list):
        sync_project_website_routes(conn, project_id, payload["website_routes"], ts=ts)

    return get_project_lead_config(conn, project_id)


def sync_project_facebook_forms(
    conn: sqlite3.Connection,
    project_id: int,
    forms: list[Any],
    *,
    default_page_id: str = "",
    ts: str = "",
) -> list[dict[str, Any]]:
    ensure_project_webhook_schema(conn)
    ts = ts or _now_ts()
    seen: set[str] = set()
    for raw in forms:
        if not isinstance(raw, dict):
            continue
        form_id = str(raw.get("form_id") or "").strip()
        if not form_id or form_id in seen:
            continue
        seen.add(form_id)
        other = conn.execute(
            """
            SELECT project_id FROM crm_re_project_facebook_forms
            WHERE form_id = ? AND project_id != ?
            """,
            (form_id, int(project_id)),
        ).fetchone()
        if other:
            raise ValueError(f"Form ID {form_id} đã map sang dự án #{other['project_id']}.")
        page_id = str(raw.get("page_id") or default_page_id or "").strip()
        form_name = str(raw.get("form_name") or "").strip()
        active = bool(raw.get("active", True))
        conn.execute(
            """
            INSERT INTO crm_re_project_facebook_forms (
                project_id, page_id, form_id, form_name, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(form_id) DO UPDATE SET
                project_id = excluded.project_id,
                page_id = excluded.page_id,
                form_name = excluded.form_name,
                active = excluded.active,
                updated_at = excluded.updated_at
            """,
            (int(project_id), page_id, form_id, form_name, 1 if active else 0, ts, ts),
        )

    if forms:
        keep = tuple(seen)
        if keep:
            placeholders = ",".join("?" * len(keep))
            conn.execute(
                f"""
                DELETE FROM crm_re_project_facebook_forms
                WHERE project_id = ? AND form_id NOT IN ({placeholders})
                """,
                (int(project_id), *keep),
            )
    return list_project_facebook_forms(conn, project_id)


def sync_project_zalo_campaigns(
    conn: sqlite3.Connection,
    project_id: int,
    campaigns: list[Any],
    *,
    default_oa_id: str = "",
    ts: str = "",
) -> list[dict[str, Any]]:
    ensure_project_webhook_schema(conn)
    ts = ts or _now_ts()
    seen: set[str] = set()
    for raw in campaigns:
        if not isinstance(raw, dict):
            continue
        campaign_id = str(raw.get("campaign_id") or "").strip()
        if not campaign_id or campaign_id in seen:
            continue
        seen.add(campaign_id)
        other = conn.execute(
            """
            SELECT project_id FROM crm_re_project_zalo_campaigns
            WHERE campaign_id = ? AND project_id != ?
            """,
            (campaign_id, int(project_id)),
        ).fetchone()
        if other:
            raise ValueError(f"Campaign ID {campaign_id} đã map sang dự án #{other['project_id']}.")
        oa_id = str(raw.get("oa_id") or default_oa_id or "").strip()
        campaign_name = str(raw.get("campaign_name") or "").strip()
        active = bool(raw.get("active", True))
        conn.execute(
            """
            INSERT INTO crm_re_project_zalo_campaigns (
                project_id, oa_id, campaign_id, campaign_name, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(campaign_id) DO UPDATE SET
                project_id = excluded.project_id,
                oa_id = excluded.oa_id,
                campaign_name = excluded.campaign_name,
                active = excluded.active,
                updated_at = excluded.updated_at
            """,
            (int(project_id), oa_id, campaign_id, campaign_name, 1 if active else 0, ts, ts),
        )

    if campaigns:
        keep = tuple(seen)
        if keep:
            placeholders = ",".join("?" * len(keep))
            conn.execute(
                f"""
                DELETE FROM crm_re_project_zalo_campaigns
                WHERE project_id = ? AND campaign_id NOT IN ({placeholders})
                """,
                (int(project_id), *keep),
            )
    return list_project_zalo_campaigns(conn, project_id)


def sync_project_website_routes(
    conn: sqlite3.Connection,
    project_id: int,
    routes: list[Any],
    *,
    ts: str = "",
) -> list[dict[str, Any]]:
    ensure_project_webhook_schema(conn)
    ts = ts or _now_ts()
    seen: set[str] = set()
    for raw in routes:
        if not isinstance(raw, dict):
            continue
        route_key = str(raw.get("route_key") or raw.get("utm_campaign") or raw.get("campaign_code") or "").strip()
        if not route_key or route_key in seen:
            continue
        seen.add(route_key)
        other = conn.execute(
            """
            SELECT project_id FROM crm_re_project_website_routes
            WHERE route_key = ? AND project_id != ?
            """,
            (route_key, int(project_id)),
        ).fetchone()
        if other:
            raise ValueError(f"Route key {route_key} đã map sang dự án #{other['project_id']}.")
        route_name = str(raw.get("route_name") or raw.get("route_label") or "").strip()
        route_type = str(raw.get("route_type") or "utm").strip().lower() or "utm"
        active = bool(raw.get("active", True))
        conn.execute(
            """
            INSERT INTO crm_re_project_website_routes (
                project_id, route_key, route_name, route_type, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(route_key) DO UPDATE SET
                project_id = excluded.project_id,
                route_name = excluded.route_name,
                route_type = excluded.route_type,
                active = excluded.active,
                updated_at = excluded.updated_at
            """,
            (int(project_id), route_key, route_name, route_type, 1 if active else 0, ts, ts),
        )

    if routes:
        keep = tuple(seen)
        if keep:
            placeholders = ",".join("?" * len(keep))
            conn.execute(
                f"""
                DELETE FROM crm_re_project_website_routes
                WHERE project_id = ? AND route_key NOT IN ({placeholders})
                """,
                (int(project_id), *keep),
            )
    return list_project_website_routes(conn, project_id)


def resolve_project_from_webhook(
    conn: sqlite3.Connection,
    *,
    webhook_slug: str | None = None,
    page_id: str | None = None,
    form_id: str | None = None,
) -> int | None:
    """Ưu tiên: slug route → form_id → page_id (duy nhất)."""
    ensure_project_webhook_schema(conn)
    slug = str(webhook_slug or "").strip().lower()
    if slug:
        row = conn.execute(
            """
            SELECT project_id FROM crm_re_project_lead_config
            WHERE webhook_slug = ? AND enabled = 1 AND webhook_enabled = 1
            """,
            (slug,),
        ).fetchone()
        return int(row["project_id"]) if row else None

    fid = str(form_id or "").strip()
    if fid:
        row = conn.execute(
            """
            SELECT f.project_id
            FROM crm_re_project_facebook_forms f
            JOIN crm_re_project_lead_config c ON c.project_id = f.project_id
            WHERE f.form_id = ? AND f.active = 1 AND c.enabled = 1 AND c.webhook_enabled = 1
            """,
            (fid,),
        ).fetchone()
        if row:
            return int(row["project_id"])

    pid = str(page_id or "").strip()
    if pid:
        rows = conn.execute(
            """
            SELECT project_id FROM crm_re_project_lead_config
            WHERE facebook_page_id = ? AND enabled = 1 AND webhook_enabled = 1
            """,
            (pid,),
        ).fetchall()
        if len(rows) == 1:
            return int(rows[0]["project_id"])
    return None


def resolve_project_from_zalo_webhook(
    conn: sqlite3.Connection,
    *,
    webhook_slug: str | None = None,
    campaign_id: str | None = None,
    oa_id: str | None = None,
) -> int | None:
    """Ưu tiên: slug route → campaign_id → oa_id (duy nhất)."""
    ensure_project_webhook_schema(conn)
    slug = str(webhook_slug or "").strip().lower()
    if slug:
        row = conn.execute(
            """
            SELECT project_id FROM crm_re_project_lead_config
            WHERE webhook_slug = ? AND enabled = 1 AND webhook_enabled = 1
            """,
            (slug,),
        ).fetchone()
        return int(row["project_id"]) if row else None

    cid = str(campaign_id or "").strip()
    if cid:
        row = conn.execute(
            """
            SELECT z.project_id
            FROM crm_re_project_zalo_campaigns z
            JOIN crm_re_project_lead_config c ON c.project_id = z.project_id
            WHERE z.campaign_id = ? AND z.active = 1 AND c.enabled = 1 AND c.webhook_enabled = 1
            """,
            (cid,),
        ).fetchone()
        if row:
            return int(row["project_id"])

    oid = str(oa_id or "").strip()
    if oid:
        rows = conn.execute(
            """
            SELECT project_id FROM crm_re_project_lead_config
            WHERE zalo_oa_id = ? AND enabled = 1 AND webhook_enabled = 1
            """,
            (oid,),
        ).fetchall()
        if len(rows) == 1:
            return int(rows[0]["project_id"])
    return None


def resolve_project_id_by_code(conn: sqlite3.Connection, code: str | None) -> int | None:
    c = str(code or "").strip()
    if not c:
        return None
    row = conn.execute(
        """
        SELECT id FROM crm_re_projects
        WHERE lower(trim(code)) = lower(?)
        """,
        (c,),
    ).fetchone()
    return int(row["id"]) if row else None


def resolve_project_from_website_route(
    conn: sqlite3.Connection,
    *,
    utm_campaign: str | None = None,
    ingest_site: str | None = None,
) -> int | None:
    """Map UTM campaign hoặc site slug (website / form SEO) → dự án."""
    ensure_project_webhook_schema(conn)
    for raw in (utm_campaign, ingest_site):
        key = str(raw or "").strip()
        if not key:
            continue
        row = conn.execute(
            """
            SELECT w.project_id
            FROM crm_re_project_website_routes w
            JOIN crm_re_project_lead_config c ON c.project_id = w.project_id
            WHERE w.route_key = ? AND w.active = 1 AND c.enabled = 1 AND c.webhook_enabled = 1
            """,
            (key,),
        ).fetchone()
        if row:
            return int(row["project_id"])
    return None


def resolve_project_for_lead_ingest(
    conn: sqlite3.Connection,
    *,
    re_project_id: int | None = None,
    re_project_code: str | None = None,
    webhook_slug: str | None = None,
    facebook_form_id: str | None = None,
    facebook_page_id: str | None = None,
    zalo_campaign_id: str | None = None,
    zalo_oa_id: str | None = None,
    utm_campaign: str | None = None,
    ingest_site: str | None = None,
) -> int | None:
    """Resolver thống nhất — mọi nguồn lead (FB, Zalo, website/form)."""
    if re_project_id is not None:
        try:
            validate_re_project_id(conn, int(re_project_id))
            return int(re_project_id)
        except ValueError:
            pass
    pid = resolve_project_id_by_code(conn, re_project_code)
    if pid is not None:
        return pid
    slug = str(webhook_slug or "").strip().lower()
    if slug:
        row = conn.execute(
            """
            SELECT project_id FROM crm_re_project_lead_config
            WHERE webhook_slug = ? AND enabled = 1 AND webhook_enabled = 1
            """,
            (slug,),
        ).fetchone()
        if row:
            return int(row["project_id"])
    pid = resolve_project_from_webhook(
        conn,
        form_id=facebook_form_id,
        page_id=facebook_page_id,
    )
    if pid is not None:
        return pid
    pid = resolve_project_from_zalo_webhook(
        conn,
        campaign_id=zalo_campaign_id or utm_campaign,
        oa_id=zalo_oa_id,
    )
    if pid is not None:
        return pid
    return resolve_project_from_website_route(
        conn,
        utm_campaign=utm_campaign,
        ingest_site=ingest_site,
    )


def verify_project_webhook_token(conn: sqlite3.Connection, webhook_slug: str, token: str) -> int | None:
    """Trả project_id nếu token khớp (project hoặc global fallback)."""
    ensure_project_webhook_schema(conn)
    slug = str(webhook_slug or "").strip().lower()
    if not slug:
        return None
    row = conn.execute(
        "SELECT project_id, webhook_verify_token FROM crm_re_project_lead_config WHERE webhook_slug = ?",
        (slug,),
    ).fetchone()
    if not row:
        return None
    proj_token = str(row["webhook_verify_token"] or "").strip()
    global_token = facebook_verify_token()
    if proj_token and token and proj_token == token:
        return int(row["project_id"])
    if global_token and token and global_token == token:
        return int(row["project_id"])
    return None


def project_webhook_ingest_allowed(conn: sqlite3.Connection, project_id: int) -> tuple[bool, str]:
    cfg = get_project_lead_config(conn, project_id)
    if not cfg.get("enabled"):
        return False, "Dự án tắt nhận lead webhook."
    if not cfg.get("webhook_enabled"):
        return False, "Webhook dự án đã tắt."
    return True, ""


def list_unmapped_facebook_forms(conn: sqlite3.Connection, *, limit: int = 20) -> list[dict[str, Any]]:
    """Form ID xuất hiện ở pending/lead nhưng chưa map dự án — gợi ý AI."""
    ensure_project_webhook_schema(conn)
    lim = max(1, min(int(limit), 50))
    try:
        from crm_facebook_pending import ensure_facebook_pending_schema

        ensure_facebook_pending_schema(conn)
    except Exception:
        pass
    rows = conn.execute(
        """
        SELECT form_id, COUNT(*) AS cnt, MAX(updated_at) AS last_seen
        FROM crm_facebook_pending
        WHERE form_id != ''
        GROUP BY form_id
        ORDER BY cnt DESC, last_seen DESC
        LIMIT ?
        """,
        (lim,),
    ).fetchall()
    mapped = {
        str(r["form_id"])
        for r in conn.execute("SELECT form_id FROM crm_re_project_facebook_forms WHERE active = 1").fetchall()
    }
    out: list[dict[str, Any]] = []
    for r in rows:
        fid = str(r["form_id"] or "").strip()
        if not fid or fid in mapped:
            continue
        out.append(
            {
                "form_id": fid,
                "pending_count": int(r["cnt"] or 0),
                "last_seen": str(r["last_seen"] or ""),
            }
        )
    return out[:lim]


def suggest_facebook_form_project(conn: sqlite3.Connection, form_id: str) -> dict[str, Any] | None:
    """Gợi ý dự án cho form chưa map — dựa trên page_id trùng config."""
    fid = str(form_id or "").strip()
    if not fid:
        return None
    ensure_project_webhook_schema(conn)
    mapped = conn.execute(
        "SELECT project_id FROM crm_re_project_facebook_forms WHERE form_id = ? AND active = 1",
        (fid,),
    ).fetchone()
    if mapped:
        return None
    pending = conn.execute(
        "SELECT page_id FROM crm_facebook_pending WHERE form_id = ? ORDER BY updated_at DESC LIMIT 1",
        (fid,),
    ).fetchone()
    page_id = str(pending["page_id"] if pending else "").strip()
    if not page_id:
        return None
    rows = conn.execute(
        """
        SELECT c.project_id, p.name, p.code
        FROM crm_re_project_lead_config c
        JOIN crm_re_projects p ON p.id = c.project_id
        WHERE c.facebook_page_id = ? AND c.enabled = 1
        """,
        (page_id,),
    ).fetchall()
    if len(rows) != 1:
        return None
    r = rows[0]
    return {
        "form_id": fid,
        "suggested_project_id": int(r["project_id"]),
        "suggested_project_name": str(r["name"] or ""),
        "suggested_project_code": str(r["code"] or ""),
        "reason": f"Page ID {page_id} khớp cấu hình dự án.",
    }
