"""R6 — Add-on ngành trên Lead; gỡ trường BĐS legacy (re_project_id…)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

MIGRATION_KEY = "lead_industry_addon_r6_v1"

INDUSTRY_ADDON_PACKS: dict[str, dict[str, Any]] = {
    "bds": {
        "addon_key": "bds",
        "addon_label": "Add-on BĐS",
        "fields": [
            {"key": "du_an", "label": "Tên dự án", "type": "text"},
            {
                "key": "loai_sp",
                "label": "Loại sản phẩm",
                "type": "select",
                "options": [
                    {"value": "can_ho", "label": "Căn hộ"},
                    {"value": "dat_nen", "label": "Đất nền"},
                    {"value": "biet_thu", "label": "Biệt thự"},
                    {"value": "shophouse", "label": "Shophouse"},
                ],
            },
            {"key": "khu_vuc", "label": "Khu vực / phân khu", "type": "text"},
            {"key": "ngan_sach", "label": "Ngân sách dự kiến", "type": "text"},
        ],
    },
    "spa": {
        "addon_key": "spa",
        "addon_label": "Add-on Spa & Beauty",
        "fields": [
            {"key": "loai_hinh", "label": "Loại hình spa", "type": "text"},
            {"key": "vi_tri", "label": "Vị trí", "type": "text"},
            {"key": "dich_vu_chinh", "label": "Dịch vụ chủ lực", "type": "text"},
        ],
    },
    "fnb": {
        "addon_key": "fnb",
        "addon_label": "Add-on F&B",
        "fields": [
            {
                "key": "loai_quan",
                "label": "Loại quán",
                "type": "select",
                "options": [
                    {"value": "cafe", "label": "Cafe"},
                    {"value": "nha_hang", "label": "Nhà hàng"},
                    {"value": "fast_food", "label": "Fast food"},
                ],
            },
            {"key": "vi_tri", "label": "Khu vực", "type": "text"},
            {"key": "quy_mo", "label": "Quy mô (m² / chi nhánh)", "type": "text"},
        ],
    },
    "giao-duc": {
        "addon_key": "giao-duc",
        "addon_label": "Add-on Giáo dục",
        "fields": [
            {"key": "cap_hoc", "label": "Cấp học", "type": "text"},
            {"key": "mon_manh", "label": "Môn / chương trình mạnh", "type": "text"},
            {"key": "khu_vuc", "label": "Khu vực", "type": "text"},
        ],
    },
}

RE_LEGACY_FIELDS: tuple[str, ...] = (
    "re_project_id",
    "product_line",
    "zone",
    "re_product_id",
)


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def ensure_industry_addon_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_lead_industry_addon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL UNIQUE REFERENCES crm_leads(id) ON DELETE CASCADE,
            industry_slug TEXT NOT NULL DEFAULT '',
            data_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_ind_addon_slug "
        "ON crm_lead_industry_addon(industry_slug)"
    )


def bootstrap_industry_traits(conn: sqlite3.Connection) -> None:
    """Gắn pack add-on vào traits_json ngành trong catalog (merge, không ghi đè field khác)."""
    from crm_lead_catalog import ensure_lead_catalog_schema

    ensure_lead_catalog_schema(conn)
    ts = _ts()
    for slug, pack in INDUSTRY_ADDON_PACKS.items():
        row = conn.execute(
            "SELECT id, traits_json FROM crm_catalog_industries WHERE slug = ? LIMIT 1",
            (slug,),
        ).fetchone()
        if row is None:
            continue
        try:
            traits = json.loads(str(row["traits_json"] or "{}"))
        except (TypeError, json.JSONDecodeError):
            traits = {}
        if not isinstance(traits, dict):
            traits = {}
        changed = False
        for key in ("addon_key", "addon_label", "fields"):
            if traits.get(key) != pack.get(key):
                traits[key] = pack[key]
                changed = True
        if changed:
            conn.execute(
                """
                UPDATE crm_catalog_industries
                SET traits_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(traits, ensure_ascii=False), ts, int(row["id"])),
            )


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
    save_lead_config(conn, config=cfg, updated_by="system", ts=_ts())


def migrate_re_legacy_to_industry_addon(conn: sqlite3.Connection) -> dict[str, int]:
    """Chuyển re_project_id / product_line / zone cũ → add-on ngành BĐS; xóa cột legacy."""
    ensure_industry_addon_schema(conn)
    if not _table_exists(conn, "crm_leads"):
        return {"migrated": 0, "skipped": 0}
    if _migration_done(conn):
        return {"migrated": 0, "skipped": 1}

    has_re_projects = _table_exists(conn, "crm_re_projects")
    if has_re_projects:
        rows = conn.execute(
            """
            SELECT l.id, l.re_project_id, l.product_line, l.zone, l.industry_slug,
                   p.code AS project_code, p.name AS project_name
            FROM crm_leads l
            LEFT JOIN crm_re_projects p ON p.id = l.re_project_id
            WHERE (l.re_project_id IS NOT NULL AND l.re_project_id != 0)
               OR trim(COALESCE(l.product_line, '')) != ''
               OR trim(COALESCE(l.zone, '')) != ''
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, re_project_id, product_line, zone, industry_slug,
                   '' AS project_code, '' AS project_name
            FROM crm_leads
            WHERE (re_project_id IS NOT NULL AND re_project_id != 0)
               OR trim(COALESCE(product_line, '')) != ''
               OR trim(COALESCE(zone, '')) != ''
            """
        ).fetchall()

    migrated = 0
    ts = _ts()
    for row in rows:
        lid = int(row["id"])
        slug = str(row["industry_slug"] or "").strip() or "bds"
        data: dict[str, str] = {}
        code = str(row["project_code"] or "").strip()
        name = str(row["project_name"] or "").strip()
        if code or name:
            data["du_an"] = f"{code} — {name}".strip(" —")
        line = str(row["product_line"] or "").strip()
        if line:
            data["loai_sp"] = line
        zone = str(row["zone"] or "").strip()
        if zone:
            data["khu_vuc"] = zone
        conn.execute(
            """
            INSERT INTO crm_lead_industry_addon
                (lead_id, industry_slug, data_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(lead_id) DO UPDATE SET
                industry_slug = excluded.industry_slug,
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (lid, slug, json.dumps(data, ensure_ascii=False), ts, ts),
        )
        conn.execute(
            """
            UPDATE crm_leads
            SET re_project_id = NULL, product_line = '', zone = '', re_product_id = NULL,
                industry_slug = CASE
                    WHEN trim(COALESCE(industry_slug, '')) = '' THEN 'bds'
                    ELSE industry_slug
                END,
                updated_at = ?
            WHERE id = ?
            """,
            (ts, lid),
        )
        migrated += 1

    _mark_migration_done(conn)
    conn.commit()
    return {"migrated": migrated, "skipped": 0}


def ensure_r6_schema(conn: sqlite3.Connection) -> None:
    ensure_industry_addon_schema(conn)
    bootstrap_industry_traits(conn)
    migrate_re_legacy_to_industry_addon(conn)


def reject_re_legacy_lead_input(
    *,
    re_project_id: Any = None,
    product_line: Any = None,
    zone: Any = None,
    re_product_id: Any = None,
) -> None:
    """Product Model v1: không nhận trường BĐS legacy trên lead."""
    if re_project_id not in (None, "", 0, "0"):
        raise ValueError(
            "Trường dự án BĐS legacy (re_project_id) đã gỡ — chọn Ngành và điền Add-on ngành."
        )
    if str(product_line or "").strip():
        raise ValueError(
            "Trường product_line legacy đã gỡ — dùng Add-on ngành (catalog Ngành)."
        )
    if str(zone or "").strip():
        raise ValueError(
            "Trường zone legacy đã gỡ — dùng Add-on ngành (catalog Ngành)."
        )
    if re_product_id not in (None, "", 0, "0"):
        raise ValueError(
            "Trường re_product_id / giữ căn legacy đã gỡ — dùng Add-on ngành."
        )


def resolve_addon_pack(
    conn: sqlite3.Connection, industry_slug: str
) -> dict[str, Any] | None:
    slug = str(industry_slug or "").strip()
    if not slug:
        return None
    from crm_lead_catalog import ensure_lead_catalog_schema

    ensure_lead_catalog_schema(conn)
    row = conn.execute(
        "SELECT traits_json FROM crm_catalog_industries WHERE slug = ? AND active = 1 LIMIT 1",
        (slug,),
    ).fetchone()
    traits: dict[str, Any] = {}
    if row is not None:
        try:
            parsed = json.loads(str(row["traits_json"] or "{}"))
            if isinstance(parsed, dict):
                traits = parsed
        except (TypeError, json.JSONDecodeError):
            traits = {}
    if traits.get("fields"):
        return {
            "addon_key": str(traits.get("addon_key") or slug),
            "addon_label": str(traits.get("addon_label") or slug),
            "fields": traits.get("fields") or [],
        }
    fallback = INDUSTRY_ADDON_PACKS.get(slug)
    return dict(fallback) if fallback else None


def _default_data(pack: dict[str, Any] | None) -> dict[str, str]:
    if not pack:
        return {}
    out: dict[str, str] = {}
    for field in pack.get("fields") or []:
        if isinstance(field, dict) and field.get("key"):
            out[str(field["key"])] = ""
    return out


def _parse_data(raw: Any, pack: dict[str, Any] | None) -> dict[str, str]:
    base = _default_data(pack)
    obj: dict[str, Any] = {}
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                obj = parsed
        except (TypeError, json.JSONDecodeError):
            pass
    elif isinstance(raw, dict):
        obj = raw
    for k in base:
        v = obj.get(k)
        if isinstance(v, str):
            base[k] = v.strip()[:2000]
        elif v is not None:
            base[k] = str(v).strip()[:2000]
    return base


def get_lead_addon_row(conn: sqlite3.Connection, lead_id: int) -> dict[str, Any] | None:
    ensure_industry_addon_schema(conn)
    row = conn.execute(
        "SELECT * FROM crm_lead_industry_addon WHERE lead_id = ?",
        (int(lead_id),),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def lead_industry_addon_payload(
    conn: sqlite3.Connection, lead_id: int, *, industry_slug: str = ""
) -> dict[str, Any]:
    slug = str(industry_slug or "").strip()
    if not slug:
        lead = conn.execute(
            "SELECT industry_slug FROM crm_leads WHERE id = ?", (int(lead_id),)
        ).fetchone()
        slug = str(lead["industry_slug"] or "").strip() if lead else ""
    pack = resolve_addon_pack(conn, slug) if slug else None
    row = get_lead_addon_row(conn, int(lead_id))
    data = _parse_data(row.get("data_json") if row else "{}", pack)
    return {
        "industry_slug": slug,
        "pack": pack,
        "data": data,
        "has_pack": pack is not None,
        "legacy_re_removed": True,
    }


def update_lead_industry_addon(
    conn: sqlite3.Connection,
    lead_id: int,
    patch: dict[str, Any],
    *,
    industry_slug: str | None = None,
) -> dict[str, Any]:
    ensure_industry_addon_schema(conn)
    lead = conn.execute(
        "SELECT industry_slug FROM crm_leads WHERE id = ?", (int(lead_id),)
    ).fetchone()
    if lead is None:
        raise ValueError("Không tìm thấy lead")
    slug = str(
        industry_slug if industry_slug is not None else lead["industry_slug"] or ""
    ).strip()
    if not slug:
        raise ValueError("Lead chưa có ngành — chọn ngành trước khi điền add-on.")
    from crm_lead_catalog import validate_industry_slug

    validate_industry_slug(conn, slug)
    pack = resolve_addon_pack(conn, slug)
    if pack is None:
        raise ValueError(f"Ngành {slug} chưa có add-on.")

    row = get_lead_addon_row(conn, int(lead_id))
    current = _parse_data(row.get("data_json") if row else "{}", pack)
    incoming = patch.get("data") if isinstance(patch.get("data"), dict) else patch
    if isinstance(incoming, dict):
        allowed = {str(f["key"]) for f in pack.get("fields") or [] if f.get("key")}
        for k, v in incoming.items():
            if k in allowed:
                current[k] = str(v or "").strip()[:2000]

    ts = _ts()
    conn.execute(
        """
        INSERT INTO crm_lead_industry_addon
            (lead_id, industry_slug, data_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lead_id) DO UPDATE SET
            industry_slug = excluded.industry_slug,
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
        """,
        (int(lead_id), slug, json.dumps(current, ensure_ascii=False), ts, ts),
    )
    if str(lead["industry_slug"] or "").strip() != slug:
        conn.execute(
            "UPDATE crm_leads SET industry_slug = ?, updated_at = ? WHERE id = ?",
            (slug, ts, int(lead_id)),
        )
    conn.commit()
    return lead_industry_addon_payload(conn, int(lead_id), industry_slug=slug)


def sync_addon_on_industry_change(
    conn: sqlite3.Connection, lead_id: int, new_slug: str
) -> None:
    """Khi đổi ngành lead: reset data add-on theo pack mới."""
    pack = resolve_addon_pack(conn, new_slug)
    if pack is None:
        conn.execute("DELETE FROM crm_lead_industry_addon WHERE lead_id = ?", (int(lead_id),))
        conn.commit()
        return
    ts = _ts()
    conn.execute(
        """
        INSERT INTO crm_lead_industry_addon
            (lead_id, industry_slug, data_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lead_id) DO UPDATE SET
            industry_slug = excluded.industry_slug,
            data_json = excluded.data_json,
            updated_at = excluded.updated_at
        """,
        (
            int(lead_id),
            new_slug,
            json.dumps(_default_data(pack), ensure_ascii=False),
            ts,
            ts,
        ),
    )
    conn.commit()
