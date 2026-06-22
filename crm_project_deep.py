"""Quản lý KĐT hỗn hợp chuyên sâu — lead ↔ sản phẩm, phân khu, sub-team NV."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime
from typing import Any

from crm_re_projects import PRODUCT_LINES, PRODUCT_LINE_LABELS, save_product

_UNSET: object = object()


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_scope_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    s = str(raw or "").strip()
    if not s:
        return []
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return [p.strip() for p in s.split(",") if p.strip()]


def _scope_list_to_json(items: list[str] | None) -> str:
    if not items:
        return "[]"
    clean = [str(x).strip() for x in items if str(x).strip()]
    return json.dumps(clean, ensure_ascii=False)


def ensure_project_deep_schema(conn: sqlite3.Connection) -> None:
    """Migration: lead segment fields, staff scope, product hold + price batch."""
    lead_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_leads)").fetchall()}
    for col, ddl in (
        ("product_line", "ALTER TABLE crm_leads ADD COLUMN product_line TEXT NOT NULL DEFAULT ''"),
        ("zone", "ALTER TABLE crm_leads ADD COLUMN zone TEXT NOT NULL DEFAULT ''"),
        (
            "re_product_id",
            "ALTER TABLE crm_leads ADD COLUMN re_product_id INTEGER REFERENCES crm_re_project_products(id) ON DELETE SET NULL",
        ),
    ):
        if col not in lead_cols:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_segment "
        "ON crm_leads(re_project_id, product_line, zone)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_product "
        "ON crm_leads(re_product_id) WHERE re_product_id IS NOT NULL"
    )

    staff_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_staff)").fetchall()}
    for col, ddl in (
        (
            "scope_product_lines",
            "ALTER TABLE crm_re_project_staff ADD COLUMN scope_product_lines TEXT NOT NULL DEFAULT '[]'",
        ),
        ("scope_zones", "ALTER TABLE crm_re_project_staff ADD COLUMN scope_zones TEXT NOT NULL DEFAULT '[]'"),
    ):
        if col not in staff_cols:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass

    prod_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_products)").fetchall()}
    for col, ddl in (
        (
            "hold_lead_id",
            "ALTER TABLE crm_re_project_products ADD COLUMN hold_lead_id INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL",
        ),
        ("hold_at", "ALTER TABLE crm_re_project_products ADD COLUMN hold_at TEXT NOT NULL DEFAULT ''"),
        ("price_batch", "ALTER TABLE crm_re_project_products ADD COLUMN price_batch TEXT NOT NULL DEFAULT ''"),
    ):
        if col not in prod_cols:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass


def enrich_staff_scope_fields(d: dict[str, Any]) -> dict[str, Any]:
    d["scope_product_lines"] = _parse_scope_list(d.get("scope_product_lines"))
    d["scope_zones"] = _parse_scope_list(d.get("scope_zones"))
    lines = d["scope_product_lines"]
    zones = d["scope_zones"]
    if lines:
        d["scope_product_lines_label"] = ", ".join(
            PRODUCT_LINE_LABELS.get(x, x) for x in lines
        )
    else:
        d["scope_product_lines_label"] = "Tất cả dòng SP"
    d["scope_zones_label"] = ", ".join(zones) if zones else "Tất cả phân khu"
    return d


def staff_matches_lead_scope(
    staff_row: dict[str, Any],
    *,
    product_line: str = "",
    zone: str = "",
) -> bool:
    lines = staff_row.get("scope_product_lines") or _parse_scope_list(staff_row.get("scope_product_lines_json"))
    zones = staff_row.get("scope_zones") or _parse_scope_list(staff_row.get("scope_zones_json"))
    line = str(product_line or "").strip()
    zn = str(zone or "").strip()
    if lines and line and line not in lines:
        return False
    if zones and zn and zn not in zones:
        return False
    return True


def normalize_product_line(raw: str) -> str:
    line = str(raw or "").strip()
    if not line:
        return ""
    if line in PRODUCT_LINES:
        return line
    low = line.lower()
    for code in PRODUCT_LINES:
        if code == low:
            return code
    for code, label in PRODUCT_LINE_LABELS.items():
        if label.lower() == low:
            return code
    return "other"


def list_project_zones(conn: sqlite3.Connection, project_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trim(zone) AS z FROM crm_re_project_products
        WHERE project_id = ? AND trim(COALESCE(zone, '')) != ''
        ORDER BY z COLLATE NOCASE
        """,
        (int(project_id),),
    ).fetchall()
    return [str(r["z"]) for r in rows if r["z"]]


def fetch_product_by_id(
    conn: sqlite3.Connection,
    project_id: int,
    product_id: int,
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM crm_re_project_products WHERE id = ? AND project_id = ?",
        (int(product_id), int(project_id)),
    ).fetchone()


def search_available_products(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    q: str = "",
    product_line: str = "",
    zone: str = "",
    price_batch: str = "",
    status: str = "available",
    limit: int = 50,
) -> list[dict[str, Any]]:
    from crm_re_projects import _enrich_product_row, _staff_lookup

    clauses = ["project_id = ?"]
    params: list[Any] = [int(project_id)]
    st = str(status or "").strip()
    if st:
        clauses.append("status = ?")
        params.append(st)
    line = normalize_product_line(product_line)
    if line:
        clauses.append("product_line = ?")
        params.append(line)
    zn = str(zone or "").strip()
    if zn:
        clauses.append("trim(zone) = ?")
        params.append(zn)
    batch = str(price_batch or "").strip()
    if batch:
        clauses.append("trim(price_batch) = ?")
        params.append(batch)
    if str(q or "").strip():
        like = f"%{str(q).strip()}%"
        clauses.append(
            "(unit_code LIKE ? OR tower LIKE ? OR floor LIKE ? OR zone LIKE ? OR product_type LIKE ?)"
        )
        params.extend([like] * 5)
    lim = max(1, min(int(limit), 200))
    rows = conn.execute(
        f"""
        SELECT * FROM crm_re_project_products
        WHERE {' AND '.join(clauses)}
        ORDER BY zone, product_line, tower, unit_code
        LIMIT ?
        """,
        [*params, lim],
    ).fetchall()
    staff_ids = {int(r["sales_staff_id"]) for r in rows if r["sales_staff_id"]}
    staff_map = _staff_lookup(conn, staff_ids)
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        _enrich_product_row(d, staff_map)
        out.append(d)
    return out


def _release_product_hold_by_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    ts: str,
    except_product_id: int | None = None,
) -> None:
    rows = conn.execute(
        """
        SELECT id FROM crm_re_project_products
        WHERE hold_lead_id = ? AND status = 'hold'
        """,
        (int(lead_id),),
    ).fetchall()
    for r in rows:
        pid = int(r["id"])
        if except_product_id is not None and pid == int(except_product_id):
            continue
        conn.execute(
            """
            UPDATE crm_re_project_products SET
                status = 'available', hold_lead_id = NULL, hold_at = '', updated_at = ?
            WHERE id = ?
            """,
            (ts, pid),
        )


def hold_product_for_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    product_id: int,
    *,
    updated_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    from crm_lead_store import fetch_lead_by_id, log_lead_activity

    ts_val = ts or _now_ts()
    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    ld = dict(lead)
    project_id = ld.get("re_project_id")
    if not project_id:
        raise ValueError("Lead chưa gán dự án BĐS — không thể giữ chỗ sản phẩm.")
    prod = fetch_product_by_id(conn, int(project_id), int(product_id))
    if prod is None:
        raise ValueError("Sản phẩm không thuộc dự án của lead.")
    pd = dict(prod)
    st = str(pd.get("status") or "available")
    hold_lead = pd.get("hold_lead_id")
    if st not in ("available", "hold"):
        raise ValueError(f"Sản phẩm đang ở trạng thái «{st}» — không thể giữ chỗ.")
    if st == "hold" and hold_lead and int(hold_lead) != int(lead_id):
        raise ValueError("Sản phẩm đang được giữ chỗ bởi lead khác.")
    _release_product_hold_by_lead(conn, int(lead_id), ts=ts_val, except_product_id=int(product_id))
    cur = conn.execute(
        """
        UPDATE crm_re_project_products SET
            status = 'hold', hold_lead_id = ?, hold_at = ?, updated_at = ?
        WHERE id = ? AND project_id = ?
          AND (
            status = 'available'
            OR (status = 'hold' AND COALESCE(hold_lead_id, 0) = ?)
          )
        """,
        (int(lead_id), ts_val, ts_val, int(product_id), int(project_id), int(lead_id)),
    )
    if cur.rowcount != 1:
        raise ValueError("Sản phẩm không còn trống hoặc vừa được giữ chỗ bởi lead khác.")
    conn.execute(
        """
        UPDATE crm_leads SET
            re_product_id = ?, product_line = ?, zone = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            int(product_id),
            str(pd.get("product_line") or ""),
            str(pd.get("zone") or ""),
            ts_val,
            str(updated_by or "")[:120],
            int(lead_id),
        ),
    )
    unit = str(pd.get("unit_code") or product_id)
    zone = str(pd.get("zone") or "")
    log_lead_activity(
        conn,
        lead_id=int(lead_id),
        activity_type="system",
        content=f"Giữ chỗ sản phẩm {unit}" + (f" ({zone})" if zone else ""),
        created_by=updated_by,
        ts=ts_val,
    )
    refreshed = fetch_lead_by_id(conn, lead_id)
    assert refreshed is not None
    return {"lead_id": int(lead_id), "product_id": int(product_id), "unit_code": unit}


def release_product_hold(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    updated_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    from crm_lead_store import fetch_lead_by_id, log_lead_activity

    ts_val = ts or _now_ts()
    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    ld = dict(lead)
    pid = ld.get("re_product_id")
    _release_product_hold_by_lead(conn, int(lead_id), ts=ts_val)
    conn.execute(
        """
        UPDATE crm_leads SET re_product_id = NULL, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (ts_val, str(updated_by or "")[:120], int(lead_id)),
    )
    if pid:
        log_lead_activity(
            conn,
            lead_id=int(lead_id),
            activity_type="system",
            content=f"Hủy giữ chỗ sản phẩm #{pid}",
            created_by=updated_by,
            ts=ts_val,
        )
    return {"lead_id": int(lead_id), "released": True}


def import_products_csv(
    conn: sqlite3.Connection,
    project_id: int,
    csv_text: str,
    *,
    updated_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    ts_val = ts or _now_ts()
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
        payload: dict[str, Any] = {
            "unit_code": unit,
            "zone": str(row.get("zone") or row.get("phan_khu") or "").strip(),
            "tower": str(row.get("tower") or row.get("block") or "").strip(),
            "floor": str(row.get("floor") or row.get("tang") or "").strip(),
            "product_line": normalize_product_line(str(row.get("product_line") or row.get("dong_sp") or "")),
            "typology": str(row.get("typology") or "").strip(),
            "product_type": str(row.get("product_type") or "").strip(),
            "direction": str(row.get("direction") or row.get("huong") or "").strip(),
            "view_type": str(row.get("view_type") or row.get("view") or "").strip(),
            "status": str(row.get("status") or "available").strip() or "available",
            "price_batch": str(row.get("price_batch") or row.get("dot_gia") or "").strip(),
            "notes": str(row.get("notes") or "").strip(),
        }
        for num_key, field in (
            ("area_m2", "area_m2"),
            ("bedrooms", "bedrooms"),
            ("list_price_vnd", "list_price_vnd"),
            ("net_price_vnd", "net_price_vnd"),
        ):
            raw = row.get(num_key) or row.get({"area_m2": "dien_tich", "list_price_vnd": "gia"}.get(num_key, ""))
            if raw not in (None, ""):
                try:
                    payload[field] = float(raw) if num_key == "area_m2" else int(float(raw))
                except (TypeError, ValueError):
                    pass
        existing = conn.execute(
            "SELECT id FROM crm_re_project_products WHERE project_id = ? AND lower(trim(unit_code)) = lower(?)",
            (int(project_id), unit),
        ).fetchone()
        try:
            save_product(
                conn,
                int(project_id),
                payload,
                product_id=int(existing["id"]) if existing else None,
                ts=ts_val,
            )
            if existing:
                updated += 1
            else:
                created += 1
        except Exception as exc:
            errors.append(f"Dòng {i} ({unit}): {exc}")
    return {"created": created, "updated": updated, "errors": errors[:20]}


def inventory_by_zone_summary(
    conn: sqlite3.Connection,
    project_id: int,
) -> list[dict[str, Any]]:
    from crm_re_projects import compute_product_inventory_stats, list_products

    products = list_products(conn, int(project_id))
    inv = compute_product_inventory_stats(products)
    by_zone = inv.get("by_zone") or []
    by_line = {r["key"]: r for r in (inv.get("by_product_line") or [])}
    out: list[dict[str, Any]] = []
    for z in by_zone:
        zone_key = str(z.get("key") or "")
        zone_products = [p for p in products if (str(p.get("zone") or "").strip() or "Chưa phân khu") == zone_key]
        line_counts: dict[str, int] = {}
        for p in zone_products:
            lk = str(p.get("product_line") or "other")
            line_counts[lk] = line_counts.get(lk, 0) + 1
        lines_detail = [
            {
                "product_line": lk,
                "label": PRODUCT_LINE_LABELS.get(lk, lk),
                "count": cnt,
                "stats": by_line.get(lk),
            }
            for lk, cnt in sorted(line_counts.items(), key=lambda x: (-x[1], x[0]))
        ]
        out.append({**z, "product_lines": lines_detail})
    return out


def list_price_batches(conn: sqlite3.Connection, project_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT trim(price_batch) AS b FROM crm_re_project_products
        WHERE project_id = ? AND trim(COALESCE(price_batch, '')) != ''
        ORDER BY b COLLATE NOCASE DESC
        """,
        (int(project_id),),
    ).fetchall()
    return [str(r["b"]) for r in rows if r["b"]]


def inventory_by_price_batch_summary(
    conn: sqlite3.Connection,
    project_id: int,
) -> list[dict[str, Any]]:
    from crm_re_projects import list_products

    products = list_products(conn, int(project_id))
    batches: dict[str, dict[str, Any]] = {}
    for p in products:
        key = str(p.get("price_batch") or "").strip() or "Chưa gán đợt"
        bucket = batches.setdefault(
            key,
            {
                "key": key,
                "label": key,
                "total": 0,
                "available": 0,
                "sold": 0,
                "hold": 0,
                "booked": 0,
            },
        )
        bucket["total"] += 1
        st = str(p.get("status") or "available")
        if st == "available":
            bucket["available"] += 1
        elif st == "sold":
            bucket["sold"] += 1
        elif st == "hold":
            bucket["hold"] += 1
        elif st == "booked":
            bucket["booked"] += 1
    return sorted(batches.values(), key=lambda x: (-x["total"], x["label"]))
