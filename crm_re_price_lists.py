"""Bảng giá theo version — crm_re_price_lists + bulk apply lên sản phẩm."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime
from typing import Any

PRICE_LIST_STATUSES = ("draft", "active", "archived")

PRICE_LIST_STATUS_LABELS = {
    "draft": "Nháp",
    "active": "Đang áp dụng",
    "archived": "Lưu trữ",
}


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_price_lists_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_price_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            version_code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL DEFAULT '',
            effective_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            notes TEXT NOT NULL DEFAULT '',
            applied_at TEXT NOT NULL DEFAULT '',
            applied_by TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_re_price_lists_version
        ON crm_re_price_lists(project_id, lower(trim(version_code)))
        WHERE trim(version_code) != ''
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_price_lists_status "
        "ON crm_re_price_lists(project_id, status, effective_date)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_price_list_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            price_list_id INTEGER NOT NULL REFERENCES crm_re_price_lists(id) ON DELETE CASCADE,
            unit_code TEXT NOT NULL DEFAULT '',
            zone TEXT NOT NULL DEFAULT '',
            list_price_vnd INTEGER NOT NULL DEFAULT 0,
            net_price_vnd INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_re_price_list_items_unit
        ON crm_re_price_list_items(price_list_id, lower(trim(unit_code)))
        WHERE trim(unit_code) != ''
        """
    )


def _price_list_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    st = str(d.get("status") or "draft")
    if st not in PRICE_LIST_STATUSES:
        st = "draft"
    item_count = int(d.get("item_count") or 0)
    return {
        "id": int(d["id"]),
        "project_id": int(d["project_id"]),
        "version_code": str(d.get("version_code") or ""),
        "name": str(d.get("name") or ""),
        "effective_date": str(d.get("effective_date") or ""),
        "status": st,
        "status_label": PRICE_LIST_STATUS_LABELS.get(st, st),
        "notes": str(d.get("notes") or ""),
        "applied_at": str(d.get("applied_at") or ""),
        "applied_by": str(d.get("applied_by") or ""),
        "created_by": str(d.get("created_by") or ""),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
        "item_count": item_count,
    }


def _item_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    return {
        "id": int(d["id"]),
        "price_list_id": int(d["price_list_id"]),
        "unit_code": str(d.get("unit_code") or ""),
        "zone": str(d.get("zone") or ""),
        "list_price_vnd": int(d.get("list_price_vnd") or 0),
        "net_price_vnd": int(d.get("net_price_vnd") or 0),
        "notes": str(d.get("notes") or ""),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
    }


def _validate_version_code(raw: str) -> str:
    code = str(raw or "").strip()[:80]
    if not code:
        raise ValueError("Thiếu mã version (version_code).")
    return code


def _validate_status(raw: str) -> str:
    st = str(raw or "draft").strip().lower()
    if st not in PRICE_LIST_STATUSES:
        raise ValueError(f"Trạng thái không hợp lệ: {raw}")
    return st


def list_price_lists(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT pl.*,
               (SELECT COUNT(*) FROM crm_re_price_list_items i WHERE i.price_list_id = pl.id) AS item_count
        FROM crm_re_price_lists pl
        WHERE pl.project_id = ?
        ORDER BY pl.effective_date DESC, pl.updated_at DESC, pl.id DESC
        """,
        (int(project_id),),
    ).fetchall()
    return [_price_list_row_to_dict(r) for r in rows]


def fetch_price_list(conn: sqlite3.Connection, project_id: int, list_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT pl.*,
               (SELECT COUNT(*) FROM crm_re_price_list_items i WHERE i.price_list_id = pl.id) AS item_count
        FROM crm_re_price_lists pl
        WHERE pl.id = ? AND pl.project_id = ?
        """,
        (int(list_id), int(project_id)),
    ).fetchone()
    if row is None:
        return None
    return _price_list_row_to_dict(row)


def fetch_price_list_by_version(
    conn: sqlite3.Connection,
    project_id: int,
    version_code: str,
) -> dict[str, Any] | None:
    code = str(version_code or "").strip()
    if not code:
        return None
    row = conn.execute(
        """
        SELECT pl.*,
               (SELECT COUNT(*) FROM crm_re_price_list_items i WHERE i.price_list_id = pl.id) AS item_count
        FROM crm_re_price_lists pl
        WHERE pl.project_id = ? AND lower(trim(pl.version_code)) = lower(?)
        """,
        (int(project_id), code),
    ).fetchone()
    if row is None:
        return None
    return _price_list_row_to_dict(row)


def save_price_list(
    conn: sqlite3.Connection,
    project_id: int,
    payload: dict[str, Any],
    *,
    list_id: int | None = None,
    created_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    from crm_project_leads import validate_re_project_id

    validate_re_project_id(conn, int(project_id))
    ts_val = ts or _now_ts()
    version_code = _validate_version_code(payload.get("version_code") or payload.get("code"))
    name = str(payload.get("name") or version_code).strip()[:200]
    effective_date = str(payload.get("effective_date") or "").strip()[:10]
    notes = str(payload.get("notes") or "")[:2000]
    if list_id:
        existing = fetch_price_list(conn, int(project_id), int(list_id))
        if existing is None:
            raise ValueError("Không tìm thấy bảng giá.")
        if existing["status"] == "active" and payload.get("version_code"):
            dup = conn.execute(
                """
                SELECT id FROM crm_re_price_lists
                WHERE project_id = ? AND lower(trim(version_code)) = lower(?)
                  AND id != ?
                """,
                (int(project_id), version_code, int(list_id)),
            ).fetchone()
            if dup:
                raise ValueError(f"Mã version «{version_code}» đã tồn tại.")
        status = existing["status"]
        if payload.get("status") is not None:
            new_st = _validate_status(str(payload.get("status")))
            if new_st == "active" and existing["status"] != "active":
                raise ValueError("Dùng «Áp dụng bảng giá» để kích hoạt — không đổi status trực tiếp.")
            if existing["status"] != "active":
                status = new_st
        conn.execute(
            """
            UPDATE crm_re_price_lists SET
                version_code = ?, name = ?, effective_date = ?, status = ?, notes = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (version_code, name, effective_date, status, notes, ts_val, int(list_id), int(project_id)),
        )
        rid = int(list_id)
    else:
        dup = conn.execute(
            """
            SELECT id FROM crm_re_price_lists
            WHERE project_id = ? AND lower(trim(version_code)) = lower(?)
            """,
            (int(project_id), version_code),
        ).fetchone()
        if dup:
            raise ValueError(f"Mã version «{version_code}» đã tồn tại.")
        cur = conn.execute(
            """
            INSERT INTO crm_re_price_lists (
                project_id, version_code, name, effective_date, status, notes,
                applied_at, applied_by, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'draft', ?, '', '', ?, ?, ?)
            """,
            (
                int(project_id),
                version_code,
                name,
                effective_date,
                notes,
                str(created_by or "")[:120],
                ts_val,
                ts_val,
            ),
        )
        rid = int(cur.lastrowid)
    out = fetch_price_list(conn, int(project_id), rid)
    assert out is not None
    return out


def delete_price_list(conn: sqlite3.Connection, project_id: int, list_id: int) -> None:
    row = fetch_price_list(conn, int(project_id), int(list_id))
    if row is None:
        raise ValueError("Không tìm thấy bảng giá.")
    if row["status"] == "active":
        raise ValueError("Không xóa bảng giá đang áp dụng — lưu trữ hoặc áp bảng khác trước.")
    conn.execute(
        "DELETE FROM crm_re_price_lists WHERE id = ? AND project_id = ?",
        (int(list_id), int(project_id)),
    )


def list_price_list_items(
    conn: sqlite3.Connection,
    price_list_id: int,
    *,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    lim = max(1, min(int(limit), 2000))
    off = max(0, int(offset))
    total = int(
        conn.execute(
            "SELECT COUNT(*) AS c FROM crm_re_price_list_items WHERE price_list_id = ?",
            (int(price_list_id),),
        ).fetchone()["c"]
    )
    rows = conn.execute(
        """
        SELECT * FROM crm_re_price_list_items
        WHERE price_list_id = ?
        ORDER BY unit_code COLLATE NOCASE
        LIMIT ? OFFSET ?
        """,
        (int(price_list_id), lim, off),
    ).fetchall()
    return [_item_row_to_dict(r) for r in rows], total


def _parse_price_int(raw: Any) -> int:
    if raw in (None, ""):
        return 0
    s = str(raw).strip().replace(",", "").replace(".", "")
    try:
        return max(0, int(float(s)))
    except (TypeError, ValueError):
        return 0


def import_price_list_items_csv(
    conn: sqlite3.Connection,
    price_list_id: int,
    csv_text: str,
    *,
    ts: str | None = None,
) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    pl = conn.execute(
        "SELECT id, project_id, status FROM crm_re_price_lists WHERE id = ?",
        (int(price_list_id),),
    ).fetchone()
    if pl is None:
        raise ValueError("Không tìm thấy bảng giá.")
    if str(pl["status"]) == "archived":
        raise ValueError("Bảng giá đã lưu trữ — không import thêm.")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ValueError("File CSV trống hoặc thiếu header.")
    created = 0
    updated = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        unit = str(row.get("unit_code") or row.get("ma_can") or "").strip()
        if not unit:
            errors.append(f"Dòng {i}: thiếu unit_code")
            continue
        list_price = _parse_price_int(row.get("list_price_vnd") or row.get("gia") or row.get("gia_niem_yet"))
        net_price = _parse_price_int(row.get("net_price_vnd") or row.get("gia_net") or row.get("gia_net_vnd"))
        if net_price <= 0 and list_price > 0:
            net_price = list_price
        zone = str(row.get("zone") or row.get("phan_khu") or "").strip()[:60]
        notes = str(row.get("notes") or "").strip()[:500]
        existing = conn.execute(
            """
            SELECT id FROM crm_re_price_list_items
            WHERE price_list_id = ? AND lower(trim(unit_code)) = lower(?)
            """,
            (int(price_list_id), unit),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE crm_re_price_list_items SET
                    zone = ?, list_price_vnd = ?, net_price_vnd = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (zone, list_price, net_price, notes, ts_val, int(existing["id"])),
            )
            updated += 1
        else:
            conn.execute(
                """
                INSERT INTO crm_re_price_list_items (
                    price_list_id, unit_code, zone, list_price_vnd, net_price_vnd, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(price_list_id), unit[:40], zone, list_price, net_price, notes, ts_val, ts_val),
            )
            created += 1
    conn.execute(
        "UPDATE crm_re_price_lists SET updated_at = ? WHERE id = ?",
        (ts_val, int(price_list_id)),
    )
    return {"created": created, "updated": updated, "errors": errors[:20]}


def apply_price_list(
    conn: sqlite3.Connection,
    project_id: int,
    list_id: int,
    *,
    updated_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    """Bulk apply: cập nhật list_price_vnd, net_price_vnd, price_batch trên sản phẩm."""
    ts_val = ts or _now_ts()
    pl = fetch_price_list(conn, int(project_id), int(list_id))
    if pl is None:
        raise ValueError("Không tìm thấy bảng giá.")
    items, _ = list_price_list_items(conn, int(list_id), limit=50000)
    if not items:
        raise ValueError("Bảng giá chưa có dòng giá — import CSV trước khi áp dụng.")
    version_code = pl["version_code"]
    matched = 0
    skipped = 0
    unmatched: list[str] = []
    for it in items:
        unit = str(it.get("unit_code") or "").strip()
        if not unit:
            continue
        prod = conn.execute(
            """
            SELECT id, status FROM crm_re_project_products
            WHERE project_id = ? AND lower(trim(unit_code)) = lower(?)
            """,
            (int(project_id), unit),
        ).fetchone()
        if prod is None:
            unmatched.append(unit)
            continue
        st = str(prod["status"] or "available")
        if st == "sold":
            skipped += 1
            continue
        conn.execute(
            """
            UPDATE crm_re_project_products SET
                list_price_vnd = ?, net_price_vnd = ?, price_batch = ?, updated_at = ?
            WHERE id = ? AND project_id = ?
            """,
            (
                int(it.get("list_price_vnd") or 0),
                int(it.get("net_price_vnd") or 0),
                version_code[:80],
                ts_val,
                int(prod["id"]),
                int(project_id),
            ),
        )
        matched += 1
    conn.execute(
        """
        UPDATE crm_re_price_lists SET status = 'archived', updated_at = ?
        WHERE project_id = ? AND status = 'active' AND id != ?
        """,
        (ts_val, int(project_id), int(list_id)),
    )
    conn.execute(
        """
        UPDATE crm_re_price_lists SET
            status = 'active', applied_at = ?, applied_by = ?, updated_at = ?
        WHERE id = ? AND project_id = ?
        """,
        (ts_val, str(updated_by or "")[:120], ts_val, int(list_id), int(project_id)),
    )
    return {
        "price_list_id": int(list_id),
        "version_code": version_code,
        "matched": matched,
        "skipped_sold": skipped,
        "unmatched": unmatched[:30],
        "unmatched_count": len(unmatched),
    }


def products_on_price_version(
    conn: sqlite3.Connection,
    project_id: int,
    version_code: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    from crm_re_projects import _enrich_product_row, _staff_lookup, list_products

    code = str(version_code or "").strip()
    if not code:
        return []
    products = list_products(conn, int(project_id))
    lim = max(1, min(int(limit), 500))
    out: list[dict[str, Any]] = []
    staff_ids = {int(p["sales_staff_id"]) for p in products if p.get("sales_staff_id")}
    staff_map = _staff_lookup(conn, staff_ids)
    for p in products:
        batch = str(p.get("price_batch") or "").strip()
        if batch.lower() != code.lower():
            continue
        d = dict(p)
        _enrich_product_row(d, staff_map)
        out.append(d)
        if len(out) >= lim:
            break
    return out


def _items_map(conn: sqlite3.Connection, price_list_id: int) -> dict[str, dict[str, Any]]:
    items, _ = list_price_list_items(conn, int(price_list_id), limit=50000)
    return {str(it["unit_code"]).strip().lower(): it for it in items if str(it.get("unit_code") or "").strip()}


def compare_price_lists(
    conn: sqlite3.Connection,
    project_id: int,
    version_a: str,
    version_b: str,
) -> dict[str, Any]:
    """So sánh hai version — theo bảng giá hoặc price_batch trên SP."""
    va = str(version_a or "").strip()
    vb = str(version_b or "").strip()
    if not va or not vb:
        raise ValueError("Cần hai mã version để so sánh.")
    if va.lower() == vb.lower():
        raise ValueError("Hai version trùng nhau — chọn mã khác nhau.")

    pla = fetch_price_list_by_version(conn, int(project_id), va)
    plb = fetch_price_list_by_version(conn, int(project_id), vb)

    map_a: dict[str, dict[str, Any]] = _items_map(conn, int(pla["id"])) if pla else {}
    map_b: dict[str, dict[str, Any]] = _items_map(conn, int(plb["id"])) if plb else {}

    if not map_a:
        for p in products_on_price_version(conn, int(project_id), va, limit=5000):
            k = str(p.get("unit_code") or "").strip().lower()
            if k:
                map_a[k] = {
                    "unit_code": p.get("unit_code"),
                    "list_price_vnd": int(p.get("list_price_vnd") or 0),
                    "net_price_vnd": int(p.get("net_price_vnd") or 0),
                    "zone": p.get("zone") or "",
                }
    if not map_b:
        for p in products_on_price_version(conn, int(project_id), vb, limit=5000):
            k = str(p.get("unit_code") or "").strip().lower()
            if k:
                map_b[k] = {
                    "unit_code": p.get("unit_code"),
                    "list_price_vnd": int(p.get("list_price_vnd") or 0),
                    "net_price_vnd": int(p.get("net_price_vnd") or 0),
                    "zone": p.get("zone") or "",
                }

    all_units = sorted(set(map_a.keys()) | set(map_b.keys()))
    rows: list[dict[str, Any]] = []
    increased = 0
    decreased = 0
    unchanged = 0
    only_a = 0
    only_b = 0
    for uk in all_units:
        a = map_a.get(uk)
        b = map_b.get(uk)
        unit_display = (a or b or {}).get("unit_code") or uk
        if a and not b:
            only_a += 1
            rows.append(
                {
                    "unit_code": unit_display,
                    "zone": a.get("zone") or "",
                    "list_a": int(a.get("list_price_vnd") or 0),
                    "list_b": None,
                    "net_a": int(a.get("net_price_vnd") or 0),
                    "net_b": None,
                    "list_delta": None,
                    "net_delta": None,
                    "change": "only_a",
                }
            )
            continue
        if b and not a:
            only_b += 1
            rows.append(
                {
                    "unit_code": unit_display,
                    "zone": b.get("zone") or "",
                    "list_a": None,
                    "list_b": int(b.get("list_price_vnd") or 0),
                    "net_a": None,
                    "net_b": int(b.get("net_price_vnd") or 0),
                    "list_delta": None,
                    "net_delta": None,
                    "change": "only_b",
                }
            )
            continue
        assert a and b
        la = int(a.get("list_price_vnd") or 0)
        lb = int(b.get("list_price_vnd") or 0)
        na = int(a.get("net_price_vnd") or 0)
        nb = int(b.get("net_price_vnd") or 0)
        ld = lb - la
        nd = nb - na
        if ld > 0 or nd > 0:
            increased += 1
            ch = "up"
        elif ld < 0 or nd < 0:
            decreased += 1
            ch = "down"
        else:
            unchanged += 1
            ch = "same"
        rows.append(
            {
                "unit_code": unit_display,
                "zone": a.get("zone") or b.get("zone") or "",
                "list_a": la,
                "list_b": lb,
                "net_a": na,
                "net_b": nb,
                "list_delta": ld,
                "net_delta": nd,
                "change": ch,
            }
        )

    return {
        "version_a": va,
        "version_b": vb,
        "price_list_a": pla,
        "price_list_b": plb,
        "summary": {
            "total_units": len(all_units),
            "both": len(all_units) - only_a - only_b,
            "only_a": only_a,
            "only_b": only_b,
            "increased": increased,
            "decreased": decreased,
            "unchanged": unchanged,
        },
        "rows": rows[:200],
        "truncated": len(rows) > 200,
    }


def list_all_version_codes(conn: sqlite3.Connection, project_id: int) -> list[str]:
    """Mã version từ bảng giá + price_batch trên SP."""
    from crm_project_deep import list_price_batches

    codes: set[str] = set()
    for pl in list_price_lists(conn, int(project_id)):
        c = str(pl.get("version_code") or "").strip()
        if c:
            codes.add(c)
    for b in list_price_batches(conn, int(project_id)):
        if b:
            codes.add(b)
    return sorted(codes, key=lambda x: x.lower())
