"""Phạm vi phân lead AM theo ngành × dịch vụ (R4)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

WILDCARD = "*"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _norm_slug(raw: str) -> str:
    from crm_lead_catalog import normalize_catalog_slug

    return normalize_catalog_slug(raw) or WILDCARD


def ensure_staff_assign_scope_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff_assign_scope (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            industry_slug TEXT NOT NULL DEFAULT '*',
            service_slug TEXT NOT NULL DEFAULT '*',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_staff_assign_scope_staff "
        "ON crm_staff_assign_scope(staff_id, active)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_staff_assign_scope_dims "
        "ON crm_staff_assign_scope(industry_slug, service_slug, active)"
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def bootstrap_staff_assign_scopes_if_empty(conn: sqlite3.Connection) -> None:
    """Gán *:* cho mọi AM active — chỉ khi bảng phạm vi còn trống (gọi từ app init)."""
    row = conn.execute("SELECT COUNT(*) AS c FROM crm_staff_assign_scope").fetchone()
    if int(row["c"] if row else 0) > 0:
        return
    if not _table_exists(conn, "crm_staff"):
        return
    staff_rows = conn.execute(
        "SELECT id FROM crm_staff WHERE COALESCE(active, 1) = 1 ORDER BY id"
    ).fetchall()
    if not staff_rows:
        return
    ts = _ts()
    for sr in staff_rows:
        conn.execute(
            """
            INSERT INTO crm_staff_assign_scope
                (staff_id, industry_slug, service_slug, active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (int(sr["id"]), WILDCARD, WILDCARD, ts, ts),
        )


def lead_assignment_pool_key(
    *,
    re_project_id: int | None = None,
    industry_slug: str = "",
    service_slug: str = "",
) -> str:
    """Round-robin pool key — tách cursor theo ngành × dịch vụ (và dự án nếu có)."""
    ind = _norm_slug(industry_slug)
    svc = _norm_slug(service_slug)
    if re_project_id:
        return f"lead_rr:project:{int(re_project_id)}:ind:{ind}:svc:{svc}"
    return f"lead_rr:ind:{ind}:svc:{svc}"


def lead_assignment_pool_key_v1(
    *,
    industry_slug: str = "",
    service_slug: str = "",
) -> str:
    """Product Model v1 — chỉ pool ngành × dịch vụ (không re_project)."""
    return lead_assignment_pool_key(
        industry_slug=industry_slug,
        service_slug=service_slug,
        re_project_id=None,
    )


def _scope_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    return {
        "id": int(d["id"]),
        "staff_id": int(d["staff_id"]),
        "industry_slug": str(d.get("industry_slug") or WILDCARD),
        "service_slug": str(d.get("service_slug") or WILDCARD),
        "active": bool(int(d.get("active") or 0)),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
        "staff_name": str(d.get("staff_name") or ""),
    }


def list_staff_assign_scopes(
    conn: sqlite3.Connection, *, staff_id: int | None = None, active_only: bool = False
) -> list[dict[str, Any]]:
    ensure_staff_assign_scope_schema(conn)
    where = "1=1"
    params: list[Any] = []
    if staff_id is not None:
        where += " AND sc.staff_id = ?"
        params.append(int(staff_id))
    if active_only:
        where += " AND sc.active = 1"
    rows = conn.execute(
        f"""
        SELECT sc.*, s.name AS staff_name
        FROM crm_staff_assign_scope sc
        JOIN crm_staff s ON s.id = sc.staff_id
        WHERE {where}
        ORDER BY s.name ASC, sc.industry_slug ASC, sc.service_slug ASC, sc.id ASC
        """,
        params,
    ).fetchall()
    return [_scope_row_to_dict(r) for r in rows]


def _scope_matches(lead_ind: str, lead_svc: str, row_ind: str, row_svc: str) -> bool:
    ri = _norm_slug(row_ind) if row_ind and row_ind != WILDCARD else WILDCARD
    rs = _norm_slug(row_svc) if row_svc and row_svc != WILDCARD else WILDCARD
    li = _norm_slug(lead_ind) if lead_ind else WILDCARD
    ls = _norm_slug(lead_svc) if lead_svc else WILDCARD
    ind_ok = ri == WILDCARD or ri == li
    svc_ok = rs == WILDCARD or rs == ls
    return ind_ok and svc_ok


def eligible_staff_ids_for_lead(
    conn: sqlite3.Connection,
    *,
    industry_slug: str = "",
    service_slug: str = "",
) -> frozenset[int] | None:
    """
    Trả frozenset staff_id đủ điều kiện nhận lead.
    None = chưa cấu hình phạm vi (giữ hành vi cũ: mọi NV active).
    """
    ensure_staff_assign_scope_schema(conn)
    rows = conn.execute(
        """
        SELECT sc.staff_id, sc.industry_slug, sc.service_slug
        FROM crm_staff_assign_scope sc
        JOIN crm_staff s ON s.id = sc.staff_id
        WHERE sc.active = 1 AND COALESCE(s.active, 1) = 1
        """
    ).fetchall()
    if not rows:
        return None
    matched: set[int] = set()
    for r in rows:
        if _scope_matches(
            industry_slug,
            service_slug,
            str(r["industry_slug"] or WILDCARD),
            str(r["service_slug"] or WILDCARD),
        ):
            matched.add(int(r["staff_id"]))
    return frozenset(matched)


def create_staff_assign_scope(
    conn: sqlite3.Connection,
    *,
    staff_id: int,
    industry_slug: str = WILDCARD,
    service_slug: str = WILDCARD,
    active: bool = True,
) -> dict[str, Any]:
    ensure_staff_assign_scope_schema(conn)
    staff = conn.execute(
        "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
        (int(staff_id),),
    ).fetchone()
    if staff is None:
        raise ValueError("Nhân viên không hợp lệ.")
    ind = WILDCARD if not str(industry_slug or "").strip() or industry_slug == WILDCARD else _norm_slug(industry_slug)
    svc = WILDCARD if not str(service_slug or "").strip() or service_slug == WILDCARD else _norm_slug(service_slug)
    if ind != WILDCARD:
        from crm_lead_catalog import validate_industry_slug

        validate_industry_slug(conn, ind)
    if svc != WILDCARD:
        from crm_lead_catalog import validate_service_slug

        validate_service_slug(conn, svc)
    dup = conn.execute(
        """
        SELECT id FROM crm_staff_assign_scope
        WHERE staff_id = ? AND industry_slug = ? AND service_slug = ?
        """,
        (int(staff_id), ind, svc),
    ).fetchone()
    if dup is not None:
        raise ValueError("Phạm vi phân lead đã tồn tại cho AM này.")
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_staff_assign_scope
            (staff_id, industry_slug, service_slug, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (int(staff_id), ind, svc, 1 if active else 0, ts, ts),
    )
    row = conn.execute(
        """
        SELECT sc.*, s.name AS staff_name
        FROM crm_staff_assign_scope sc
        JOIN crm_staff s ON s.id = sc.staff_id
        WHERE sc.id = ?
        """,
        (int(cur.lastrowid),),
    ).fetchone()
    assert row is not None
    return _scope_row_to_dict(row)


def update_staff_assign_scope(
    conn: sqlite3.Connection,
    scope_id: int,
    *,
    active: bool | None = None,
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM crm_staff_assign_scope WHERE id = ?", (int(scope_id),)
    ).fetchone()
    if row is None:
        raise ValueError("Không tìm thấy phạm vi phân lead.")
    act = int(row["active"]) if active is None else (1 if active else 0)
    ts = _ts()
    conn.execute(
        "UPDATE crm_staff_assign_scope SET active = ?, updated_at = ? WHERE id = ?",
        (act, ts, int(scope_id)),
    )
    out = conn.execute(
        """
        SELECT sc.*, s.name AS staff_name
        FROM crm_staff_assign_scope sc
        JOIN crm_staff s ON s.id = sc.staff_id
        WHERE sc.id = ?
        """,
        (int(scope_id),),
    ).fetchone()
    assert out is not None
    return _scope_row_to_dict(out)


def delete_staff_assign_scope(conn: sqlite3.Connection, scope_id: int) -> None:
    cur = conn.execute(
        "DELETE FROM crm_staff_assign_scope WHERE id = ?", (int(scope_id),)
    )
    if int(cur.rowcount or 0) == 0:
        raise ValueError("Không tìm thấy phạm vi phân lead.")
