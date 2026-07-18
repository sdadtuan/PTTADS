"""Danh mục Dịch vụ + Ngành — quản trị CRM Lead (R3)."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

DEFAULT_INDUSTRIES: tuple[dict[str, str], ...] = (
    {"slug": "spa", "name": "Spa & Beauty", "description": "Spa, thẩm mỹ, wellness"},
    {"slug": "bds", "name": "Bất động sản", "description": "BĐS, dự án, môi giới"},
    {"slug": "giao-duc", "name": "Giáo dục", "description": "Trường, trung tâm, EdTech"},
    {"slug": "fnb", "name": "F&B", "description": "Nhà hàng, cafe, F&B chain"},
    {"slug": "khac", "name": "Khác", "description": "Ngành khác / chưa phân loại"},
)


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def normalize_catalog_slug(raw: str) -> str:
    s = str(raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:80]


def validate_catalog_slug(slug: str) -> str:
    key = normalize_catalog_slug(slug)
    if not key or not _SLUG_RE.match(key):
        raise ValueError("Slug không hợp lệ (chữ thường, số, dấu gạch ngang).")
    return key


def ensure_lead_catalog_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_catalog_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_catalog_industries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            traits_json TEXT NOT NULL DEFAULT '{}',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_catalog_services_active ON crm_catalog_services(active, sort_order)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_catalog_industries_active ON crm_catalog_industries(active, sort_order)"
    )
    _bootstrap_catalog_if_empty(conn)


def _bootstrap_catalog_if_empty(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS c FROM crm_catalog_services").fetchone()
    if int(row["c"] if row else 0) == 0:
        from crm_svc_tasks import SERVICE_LABELS

        ts = _ts()
        order = 0
        for slug, name in sorted(SERVICE_LABELS.items()):
            if slug.startswith("_"):
                continue
            order += 10
            conn.execute(
                """
                INSERT OR IGNORE INTO crm_catalog_services
                    (slug, name, description, sort_order, active, created_at, updated_at)
                VALUES (?, ?, '', ?, 1, ?, ?)
                """,
                (slug, name, order, ts, ts),
            )
    row2 = conn.execute("SELECT COUNT(*) AS c FROM crm_catalog_industries").fetchone()
    if int(row2["c"] if row2 else 0) == 0:
        ts = _ts()
        for i, item in enumerate(DEFAULT_INDUSTRIES):
            conn.execute(
                """
                INSERT OR IGNORE INTO crm_catalog_industries
                    (slug, name, description, traits_json, sort_order, active, created_at, updated_at)
                VALUES (?, ?, ?, '{}', ?, 1, ?, ?)
                """,
                (
                    item["slug"],
                    item["name"],
                    item.get("description") or "",
                    (i + 1) * 10,
                    ts,
                    ts,
                ),
            )


def _service_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    return {
        "id": int(d["id"]),
        "slug": str(d.get("slug") or ""),
        "name": str(d.get("name") or ""),
        "description": str(d.get("description") or ""),
        "sort_order": int(d.get("sort_order") or 0),
        "active": bool(int(d.get("active") or 0)),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
    }


def _industry_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    traits_raw = d.get("traits_json") or "{}"
    try:
        traits = json.loads(traits_raw) if isinstance(traits_raw, str) else traits_raw
    except (TypeError, json.JSONDecodeError):
        traits = {}
    return {
        "id": int(d["id"]),
        "slug": str(d.get("slug") or ""),
        "name": str(d.get("name") or ""),
        "description": str(d.get("description") or ""),
        "traits": traits if isinstance(traits, dict) else {},
        "sort_order": int(d.get("sort_order") or 0),
        "active": bool(int(d.get("active") or 0)),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
    }


def list_catalog_services(
    conn: sqlite3.Connection, *, active_only: bool = False
) -> list[dict[str, Any]]:
    ensure_lead_catalog_schema(conn)
    if active_only:
        rows = conn.execute(
            """
            SELECT * FROM crm_catalog_services
            WHERE active = 1
            ORDER BY sort_order ASC, name ASC, id ASC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM crm_catalog_services ORDER BY sort_order ASC, name ASC, id ASC"
        ).fetchall()
    return [_service_row_to_dict(r) for r in rows]


def list_catalog_industries(
    conn: sqlite3.Connection, *, active_only: bool = False
) -> list[dict[str, Any]]:
    ensure_lead_catalog_schema(conn)
    if active_only:
        rows = conn.execute(
            """
            SELECT * FROM crm_catalog_industries
            WHERE active = 1
            ORDER BY sort_order ASC, name ASC, id ASC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM crm_catalog_industries ORDER BY sort_order ASC, name ASC, id ASC"
        ).fetchall()
    return [_industry_row_to_dict(r) for r in rows]


def get_active_service_slugs(conn: sqlite3.Connection) -> frozenset[str]:
    ensure_lead_catalog_schema(conn)
    rows = conn.execute(
        "SELECT slug FROM crm_catalog_services WHERE active = 1"
    ).fetchall()
    if not rows:
        from crm_service_lifecycle import VALID_SLUGS

        return VALID_SLUGS
    return frozenset(str(r["slug"]) for r in rows)


def get_service_label(conn: sqlite3.Connection, slug: str) -> str:
    key = normalize_catalog_slug(slug)
    if not key:
        return ""
    row = conn.execute(
        "SELECT name FROM crm_catalog_services WHERE slug = ? LIMIT 1", (key,)
    ).fetchone()
    if row:
        return str(row["name"])
    from crm_svc_tasks import SERVICE_LABELS

    return SERVICE_LABELS.get(key, key)


def get_industry_label(conn: sqlite3.Connection, slug: str) -> str:
    key = normalize_catalog_slug(slug)
    if not key:
        return ""
    row = conn.execute(
        "SELECT name FROM crm_catalog_industries WHERE slug = ? LIMIT 1", (key,)
    ).fetchone()
    if row:
        return str(row["name"])
    for item in DEFAULT_INDUSTRIES:
        if item["slug"] == key:
            return item["name"]
    return key


def validate_service_slug(conn: sqlite3.Connection, slug: str) -> str:
    key = validate_catalog_slug(slug)
    if key not in get_active_service_slugs(conn):
        raise ValueError(f"Dịch vụ không hợp lệ hoặc đã vô hiệu: {key}")
    return key


def validate_industry_slug(conn: sqlite3.Connection, slug: str) -> str:
    key = validate_catalog_slug(slug)
    row = conn.execute(
        "SELECT 1 FROM crm_catalog_industries WHERE slug = ? AND active = 1 LIMIT 1",
        (key,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Ngành không hợp lệ hoặc đã vô hiệu: {key}")
    return key


def normalize_product_interest(conn: sqlite3.Connection, raw: str) -> str:
    """Chuẩn hóa dịch vụ quan tâm; cho phép text legacy nếu chưa có trong catalog."""
    value = str(raw or "").strip()
    if not value:
        return ""
    ensure_lead_catalog_schema(conn)
    key = normalize_catalog_slug(value)
    row = conn.execute(
        "SELECT active FROM crm_catalog_services WHERE slug = ? LIMIT 1", (key,)
    ).fetchone()
    if row is None:
        return value[:300]
    if not int(row["active"]):
        raise ValueError(f"Dịch vụ không hợp lệ hoặc đã vô hiệu: {key}")
    return key


def normalize_industry_slug(conn: sqlite3.Connection, raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    return validate_industry_slug(conn, value)


def normalize_industry_traits(raw: Any) -> dict[str, Any]:
    """Chuẩn hóa traits_json add-on pack trên ngành."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("traits_json không hợp lệ — kiểm tra cú pháp JSON.") from exc
    if not isinstance(raw, dict):
        raise ValueError("traits phải là object JSON.")
    out: dict[str, Any] = {}
    if "addon_key" in raw:
        key = str(raw.get("addon_key") or "").strip()[:80]
        if key and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", key):
            raise ValueError("addon_key không hợp lệ.")
        out["addon_key"] = key
    if "addon_label" in raw:
        out["addon_label"] = str(raw.get("addon_label") or "").strip()[:200]
    if "fields" in raw:
        fields = raw.get("fields")
        if fields is None:
            out["fields"] = []
        elif not isinstance(fields, list):
            raise ValueError("fields phải là mảng.")
        else:
            norm_fields: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in fields:
                if not isinstance(item, dict):
                    raise ValueError("Mỗi field add-on phải là object.")
                fkey = str(item.get("key") or "").strip()
                if not fkey or not re.match(r"^[a-z0-9_]+(?:-[a-z0-9_]+)*$", fkey):
                    raise ValueError(f"Field key không hợp lệ: {fkey or '(trống)'}")
                if fkey in seen:
                    raise ValueError(f"Field key trùng: {fkey}")
                seen.add(fkey)
                ftype = str(item.get("type") or "text").strip().lower()
                if ftype not in ("text", "select"):
                    raise ValueError(f"Field type không hỗ trợ: {ftype}")
                field: dict[str, Any] = {
                    "key": fkey,
                    "label": str(item.get("label") or fkey).strip()[:200],
                    "type": ftype,
                }
                if ftype == "select":
                    opts = item.get("options")
                    if not isinstance(opts, list) or not opts:
                        raise ValueError(f"Field {fkey} (select) cần options.")
                    field["options"] = [
                        {
                            "value": str(o.get("value") or "").strip()[:80],
                            "label": str(o.get("label") or o.get("value") or "").strip()[:200],
                        }
                        for o in opts
                        if isinstance(o, dict) and str(o.get("value") or "").strip()
                    ]
                    if not field["options"]:
                        raise ValueError(f"Field {fkey} (select) cần ít nhất một option.")
                norm_fields.append(field)
            out["fields"] = norm_fields
    return out


def industry_traits_field_count(traits: dict[str, Any] | None) -> int:
    if not traits or not isinstance(traits, dict):
        return 0
    fields = traits.get("fields")
    return len(fields) if isinstance(fields, list) else 0


def create_catalog_service(
    conn: sqlite3.Connection,
    *,
    slug: str,
    name: str,
    description: str = "",
    sort_order: int = 0,
    active: bool = True,
    updated_by: str = "",
) -> dict[str, Any]:
    ensure_lead_catalog_schema(conn)
    key = validate_catalog_slug(slug)
    nm = str(name or "").strip()
    if not nm:
        raise ValueError("Tên dịch vụ bắt buộc.")
    dup = conn.execute(
        "SELECT id FROM crm_catalog_services WHERE slug = ?", (key,)
    ).fetchone()
    if dup is not None:
        raise ValueError(f"Slug dịch vụ đã tồn tại: {key}")
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_catalog_services
            (slug, name, description, sort_order, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key,
            nm[:200],
            str(description or "").strip()[:500],
            int(sort_order or 0),
            1 if active else 0,
            ts,
            ts,
        ),
    )
    row = conn.execute(
        "SELECT * FROM crm_catalog_services WHERE id = ?", (int(cur.lastrowid),)
    ).fetchone()
    assert row is not None
    return _service_row_to_dict(row)


def update_catalog_service(
    conn: sqlite3.Connection,
    service_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    active: bool | None = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM crm_catalog_services WHERE id = ?", (int(service_id),)
    ).fetchone()
    if row is None:
        raise ValueError("Không tìm thấy dịch vụ.")
    d = dict(row)
    nm = str(name if name is not None else d["name"]).strip()
    if not nm:
        raise ValueError("Tên dịch vụ bắt buộc.")
    desc = str(description if description is not None else d["description"]).strip()
    order = int(sort_order if sort_order is not None else d["sort_order"])
    act = int(d["active"]) if active is None else (1 if active else 0)
    ts = _ts()
    conn.execute(
        """
        UPDATE crm_catalog_services
        SET name = ?, description = ?, sort_order = ?, active = ?, updated_at = ?
        WHERE id = ?
        """,
        (nm[:200], desc[:500], order, act, ts, int(service_id)),
    )
    out = conn.execute(
        "SELECT * FROM crm_catalog_services WHERE id = ?", (int(service_id),)
    ).fetchone()
    assert out is not None
    return _service_row_to_dict(out)


def create_catalog_industry(
    conn: sqlite3.Connection,
    *,
    slug: str,
    name: str,
    description: str = "",
    sort_order: int = 0,
    active: bool = True,
) -> dict[str, Any]:
    ensure_lead_catalog_schema(conn)
    key = validate_catalog_slug(slug)
    nm = str(name or "").strip()
    if not nm:
        raise ValueError("Tên ngành bắt buộc.")
    dup = conn.execute(
        "SELECT id FROM crm_catalog_industries WHERE slug = ?", (key,)
    ).fetchone()
    if dup is not None:
        raise ValueError(f"Slug ngành đã tồn tại: {key}")
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_catalog_industries
            (slug, name, description, traits_json, sort_order, active, created_at, updated_at)
        VALUES (?, ?, ?, '{}', ?, ?, ?, ?)
        """,
        (
            key,
            nm[:200],
            str(description or "").strip()[:500],
            int(sort_order or 0),
            1 if active else 0,
            ts,
            ts,
        ),
    )
    row = conn.execute(
        "SELECT * FROM crm_catalog_industries WHERE id = ?", (int(cur.lastrowid),)
    ).fetchone()
    assert row is not None
    return _industry_row_to_dict(row)


def update_catalog_industry(
    conn: sqlite3.Connection,
    industry_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    active: bool | None = None,
    traits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM crm_catalog_industries WHERE id = ?", (int(industry_id),)
    ).fetchone()
    if row is None:
        raise ValueError("Không tìm thấy ngành.")
    d = dict(row)
    nm = str(name if name is not None else d["name"]).strip()
    if not nm:
        raise ValueError("Tên ngành bắt buộc.")
    desc = str(description if description is not None else d["description"]).strip()
    order = int(sort_order if sort_order is not None else d["sort_order"])
    act = int(d["active"]) if active is None else (1 if active else 0)
    ts = _ts()
    sets = ["name = ?", "description = ?", "sort_order = ?", "active = ?", "updated_at = ?"]
    params: list[Any] = [nm[:200], desc[:500], order, act, ts]
    if traits is not None:
        norm_traits = normalize_industry_traits(traits)
        sets.append("traits_json = ?")
        params.append(json.dumps(norm_traits, ensure_ascii=False))
    params.append(int(industry_id))
    conn.execute(
        f"UPDATE crm_catalog_industries SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    out = conn.execute(
        "SELECT * FROM crm_catalog_industries WHERE id = ?", (int(industry_id),)
    ).fetchone()
    assert out is not None
    return _industry_row_to_dict(out)


def catalog_public_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    services = list_catalog_services(conn, active_only=True)
    industries = list_catalog_industries(conn, active_only=True)
    return {
        "services": services,
        "industries": industries,
        "service_slugs": [s["slug"] for s in services],
        "service_labels": {s["slug"]: s["name"] for s in services},
        "industry_slugs": [i["slug"] for i in industries],
        "industry_labels": {i["slug"]: i["name"] for i in industries},
    }
