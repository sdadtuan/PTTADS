"""Lead theo dự án BĐS — Phase 1–2: gắn dự án, nhân viên dự án, phân công scoped."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

_UNSET: object = object()

PROJECT_STAFF_ROLES: tuple[str, ...] = ("sales", "manager", "marketing", "viewer")
PROJECT_STAFF_ROLE_LABELS: dict[str, str] = {
    "sales": "Kinh doanh",
    "manager": "Quản lý dự án",
    "marketing": "Marketing",
    "viewer": "Xem only",
}
PORTAL_VIEW_ALL_LEAD_ROLES: tuple[str, ...] = ("manager", "viewer")


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def assignment_pool_key(project_id: int | None) -> str:
    if project_id:
        return f"lead_rr:project:{int(project_id)}"
    return "lead_round_robin"


def ensure_project_leads_schema(conn: sqlite3.Connection) -> None:
    """Migration: re_project_id + crm_re_project_staff."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_leads)").fetchall()}
    if "re_project_id" not in cols:
        conn.execute(
            """
            ALTER TABLE crm_leads
            ADD COLUMN re_project_id INTEGER REFERENCES crm_re_projects(id) ON DELETE SET NULL
            """
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_re_project "
        "ON crm_leads(re_project_id, id DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            staff_id INTEGER NOT NULL REFERENCES crm_staff(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'sales',
            assign_enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL DEFAULT '',
            left_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(project_id, staff_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_re_project_staff_active "
        "ON crm_re_project_staff(project_id, assign_enabled) WHERE left_at IS NULL"
    )
    from crm_project_webhooks import ensure_project_webhook_schema
    from crm_project_deep import ensure_project_deep_schema

    ensure_project_webhook_schema(conn)
    ensure_project_deep_schema(conn)


def parse_re_project_id(raw: Any) -> int | None:
    """Parse project id từ API/form; None nếu không chọn."""
    if raw is None or raw == "" or raw == 0 or raw == "0":
        return None
    try:
        pid = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("re_project_id không hợp lệ.") from exc
    if pid <= 0:
        return None
    return pid


def parse_re_project_filter(raw: Any) -> int | None | object:
    """Query filter: _UNSET = không lọc; None = lead chưa gán dự án; int = dự án cụ thể."""
    if raw is None:
        return _UNSET
    s = str(raw).strip().lower()
    if s in ("", "all", "*"):
        return _UNSET
    if s in ("none", "null", "0", "unassigned"):
        return None
    try:
        pid = int(s)
    except ValueError as exc:
        raise ValueError("re_project_id không hợp lệ.") from exc
    if pid <= 0:
        return None
    return pid


def validate_re_project_id(conn: sqlite3.Connection, project_id: int | None) -> None:
    """Raise nếu project_id không tồn tại."""
    if project_id is None:
        return
    row = conn.execute(
        "SELECT id FROM crm_re_projects WHERE id = ?",
        (int(project_id),),
    ).fetchone()
    if not row:
        raise ValueError(f"Dự án BĐS #{project_id} không tồn tại.")


def _normalize_role(role: str) -> str:
    r = str(role or "sales").strip().lower()
    return r if r in PROJECT_STAFF_ROLES else "sales"


def _project_staff_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    from crm_project_deep import enrich_staff_scope_fields

    d = dict(row)
    role = _normalize_role(str(d.get("role") or "sales"))
    out = {
        "id": int(d["id"]),
        "project_id": int(d["project_id"]),
        "staff_id": int(d["staff_id"]),
        "staff_name": str(d.get("staff_name") or ""),
        "staff_code": str(d.get("staff_code") or ""),
        "role": role,
        "role_label": PROJECT_STAFF_ROLE_LABELS.get(role, role),
        "assign_enabled": bool(d.get("assign_enabled")),
        "sort_order": int(d.get("sort_order") or 0),
        "joined_at": str(d.get("joined_at") or ""),
        "left_at": str(d.get("left_at") or "") or None,
        "active": not bool(d.get("left_at")),
        "scope_product_lines": d.get("scope_product_lines"),
        "scope_zones": d.get("scope_zones"),
    }
    return enrich_staff_scope_fields(out)


def list_project_staff(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    validate_re_project_id(conn, project_id)
    clauses = ["ps.project_id = ?"]
    params: list[Any] = [int(project_id)]
    if active_only:
        clauses.append("ps.left_at IS NULL")
    rows = conn.execute(
        f"""
        SELECT ps.*, s.name AS staff_name, s.internal_code AS staff_code
        FROM crm_re_project_staff ps
        JOIN crm_staff s ON s.id = ps.staff_id
        WHERE {' AND '.join(clauses)}
        ORDER BY ps.sort_order ASC, ps.id ASC
        """,
        params,
    ).fetchall()
    return [_project_staff_row_to_dict(r) for r in rows]


def fetch_project_assign_staff_ids(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    product_line: str = "",
    zone: str = "",
) -> list[int]:
    """NV đang tham gia dự án, bật nhận lead — lọc theo scope dòng SP / phân khu."""
    from crm_project_deep import staff_matches_lead_scope

    staff = list_project_staff(conn, int(project_id), active_only=True)
    out: list[int] = []
    for s in staff:
        if not s.get("assign_enabled"):
            continue
        if not staff_matches_lead_scope(s, product_line=product_line, zone=zone):
            continue
        out.append(int(s["staff_id"]))
    return out


def staff_may_receive_project_lead(
    conn: sqlite3.Connection,
    project_id: int,
    staff_id: int,
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM crm_re_project_staff
        WHERE project_id = ? AND staff_id = ? AND left_at IS NULL
        """,
        (int(project_id), int(staff_id)),
    ).fetchone()
    return row is not None


def fetch_staff_project_ids(conn: sqlite3.Connection, staff_id: int) -> list[int]:
    """Dự án BĐS NV đang tham gia (active)."""
    rows = conn.execute(
        """
        SELECT project_id FROM crm_re_project_staff
        WHERE staff_id = ? AND left_at IS NULL
        ORDER BY sort_order ASC, project_id ASC
        """,
        (int(staff_id),),
    ).fetchall()
    return [int(r["project_id"]) for r in rows]


def fetch_staff_project_role(
    conn: sqlite3.Connection,
    staff_id: int,
    project_id: int,
) -> str | None:
    row = conn.execute(
        """
        SELECT role FROM crm_re_project_staff
        WHERE project_id = ? AND staff_id = ? AND left_at IS NULL
        """,
        (int(project_id), int(staff_id)),
    ).fetchone()
    if not row:
        return None
    return _normalize_role(str(row["role"] or "sales"))


def lead_portal_scope_sql(staff_id: int, *, alias: str = "l") -> tuple[str, list[Any]]:
    """SQL scope portal NV: lead thuộc dự án tham gia; sales chỉ lead của mình."""
    sid = int(staff_id)
    roles = ", ".join(f"'{r}'" for r in PORTAL_VIEW_ALL_LEAD_ROLES)
    sql = f"""
        {alias}.re_project_id IN (
            SELECT project_id FROM crm_re_project_staff
            WHERE staff_id = ? AND left_at IS NULL
        )
        AND (
            {alias}.owner_id = ?
            OR {alias}.re_project_id IN (
                SELECT project_id FROM crm_re_project_staff
                WHERE staff_id = ? AND left_at IS NULL AND role IN ({roles})
            )
        )
    """
    return sql.strip(), [sid, sid, sid]


def staff_can_view_lead(
    conn: sqlite3.Connection,
    staff_id: int,
    row: sqlite3.Row | dict[str, Any],
) -> bool:
    """Portal NV — chỉ lead thuộc dự án tham gia (manager/viewer: mọi lead dự án)."""
    d = dict(row)
    pid = d.get("re_project_id")
    if not pid:
        return False
    project_id = int(pid)
    if not staff_may_receive_project_lead(conn, project_id, int(staff_id)):
        return False
    role = fetch_staff_project_role(conn, int(staff_id), project_id) or "sales"
    if role in PORTAL_VIEW_ALL_LEAD_ROLES:
        return True
    oid = d.get("owner_id")
    return oid is not None and int(oid) == int(staff_id)


def assert_staff_portal_project(
    conn: sqlite3.Connection,
    staff_id: int,
    project_id: int | None,
) -> None:
    """Portal NV tạo/sửa lead — bắt buộc chọn dự án đang tham gia."""
    if project_id is None:
        raise ValueError("Nhân viên phải chọn dự án BĐS khi tạo lead.")
    if not staff_may_receive_project_lead(conn, int(project_id), int(staff_id)):
        raise ValueError("Bạn không tham gia dự án BĐS này — không thể gán lead.")


def assert_staff_in_project(
    conn: sqlite3.Connection,
    project_id: int,
    staff_id: int,
) -> None:
    if not staff_may_receive_project_lead(conn, project_id, staff_id):
        raise ValueError(
            f"Nhân viên #{staff_id} không tham gia dự án BĐS #{project_id} — không được phân lead."
        )


def add_project_staff(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    staff_id: int,
    role: str = "sales",
    assign_enabled: bool = True,
    sort_order: int = 0,
    scope_product_lines: list[str] | None = None,
    scope_zones: list[str] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    from crm_project_deep import _scope_list_to_json
    validate_re_project_id(conn, project_id)
    sid = int(staff_id)
    staff = conn.execute(
        "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1",
        (sid,),
    ).fetchone()
    if not staff:
        raise ValueError("Nhân viên không hợp lệ hoặc đã ngưng.")
    ts_val = ts or _now_ts()
    existing = conn.execute(
        "SELECT id, left_at FROM crm_re_project_staff WHERE project_id = ? AND staff_id = ?",
        (int(project_id), sid),
    ).fetchone()
    role_norm = _normalize_role(role)
    scope_lines_json = _scope_list_to_json(scope_product_lines or [])
    scope_zones_json = _scope_list_to_json(scope_zones or [])
    if existing:
        conn.execute(
            """
            UPDATE crm_re_project_staff SET
                role = ?, assign_enabled = ?, sort_order = ?,
                scope_product_lines = ?, scope_zones = ?,
                left_at = NULL, joined_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                role_norm,
                1 if assign_enabled else 0,
                int(sort_order),
                scope_lines_json,
                scope_zones_json,
                ts_val,
                ts_val,
                int(existing["id"]),
            ),
        )
        row_id = int(existing["id"])
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_staff (
                project_id, staff_id, role, assign_enabled, sort_order,
                scope_product_lines, scope_zones,
                joined_at, left_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                int(project_id),
                sid,
                role_norm,
                1 if assign_enabled else 0,
                int(sort_order),
                scope_lines_json,
                scope_zones_json,
                ts_val,
                ts_val,
                ts_val,
            ),
        )
        row_id = int(cur.lastrowid)
    row = conn.execute(
        """
        SELECT ps.*, s.name AS staff_name, s.internal_code AS staff_code
        FROM crm_re_project_staff ps
        JOIN crm_staff s ON s.id = ps.staff_id
        WHERE ps.id = ?
        """,
        (row_id,),
    ).fetchone()
    assert row is not None
    return _project_staff_row_to_dict(row)


def update_project_staff(
    conn: sqlite3.Connection,
    project_id: int,
    staff_id: int,
    *,
    role: str | None = None,
    assign_enabled: bool | None = None,
    sort_order: int | None = None,
    scope_product_lines: list[str] | None = None,
    scope_zones: list[str] | None = None,
    ts: str | None = None,
) -> dict[str, Any]:
    from crm_project_deep import _scope_list_to_json
    row = conn.execute(
        """
        SELECT id FROM crm_re_project_staff
        WHERE project_id = ? AND staff_id = ? AND left_at IS NULL
        """,
        (int(project_id), int(staff_id)),
    ).fetchone()
    if not row:
        raise ValueError("Nhân viên không còn trong dự án.")
    ts_val = ts or _now_ts()
    sets: list[str] = ["updated_at = ?"]
    params: list[Any] = [ts_val]
    if role is not None:
        sets.append("role = ?")
        params.append(_normalize_role(role))
    if assign_enabled is not None:
        sets.append("assign_enabled = ?")
        params.append(1 if assign_enabled else 0)
    if sort_order is not None:
        sets.append("sort_order = ?")
        params.append(int(sort_order))
    if scope_product_lines is not None:
        sets.append("scope_product_lines = ?")
        params.append(_scope_list_to_json(scope_product_lines))
    if scope_zones is not None:
        sets.append("scope_zones = ?")
        params.append(_scope_list_to_json(scope_zones))
    params.append(int(row["id"]))
    conn.execute(
        f"UPDATE crm_re_project_staff SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    out = conn.execute(
        """
        SELECT ps.*, s.name AS staff_name, s.internal_code AS staff_code
        FROM crm_re_project_staff ps
        JOIN crm_staff s ON s.id = ps.staff_id
        WHERE ps.id = ?
        """,
        (int(row["id"]),),
    ).fetchone()
    assert out is not None
    return _project_staff_row_to_dict(out)


def remove_project_staff(
    conn: sqlite3.Connection,
    project_id: int,
    staff_id: int,
    *,
    ts: str | None = None,
) -> None:
    ts_val = ts or _now_ts()
    cur = conn.execute(
        """
        UPDATE crm_re_project_staff SET left_at = ?, updated_at = ?
        WHERE project_id = ? AND staff_id = ? AND left_at IS NULL
        """,
        (ts_val, ts_val, int(project_id), int(staff_id)),
    )
    if cur.rowcount == 0:
        raise ValueError("Nhân viên không còn trong dự án.")


def list_assignable_staff_for_project(
    conn: sqlite3.Connection,
    project_id: int,
) -> list[dict[str, Any]]:
    """Danh sách NV có thể phân lead thủ công (mọi thành viên active, kể cả viewer)."""
    return list_project_staff(conn, project_id, active_only=True)


def suggest_project_assignee(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    lead_level: str = "warm",
    product_line: str = "",
    zone: str = "",
) -> dict[str, Any] | None:
    """Gợi ý NV tiếp theo trong pool dự án (round-robin) — dùng cho AI."""
    from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner
    from crm_lead_rules import fetch_lead_config

    line = str(product_line or "").strip()
    zn = str(zone or "").strip()
    ids = fetch_project_assign_staff_ids(conn, project_id, product_line=line, zone=zn)
    if not ids:
        return None
    cfg = fetch_lead_config(conn)
    assign_cfg = cfg.get("assign_config") or {}
    ctx = LeadAssignContext(
        lead_level=str(lead_level or "warm"),
        re_project_id=int(project_id),
        product_line=line,
        zone=zn,
    )
    sid, name, strategy = auto_assign_lead_owner(conn, ctx, config=assign_cfg)
    if not sid:
        return None
    row = conn.execute(
        """
        SELECT ps.role, s.name, s.internal_code
        FROM crm_re_project_staff ps
        JOIN crm_staff s ON s.id = ps.staff_id
        WHERE ps.project_id = ? AND ps.staff_id = ? AND ps.left_at IS NULL
        """,
        (int(project_id), int(sid)),
    ).fetchone()
    role = _normalize_role(str(row["role"]) if row else "sales")
    return {
        "staff_id": int(sid),
        "name": str(row["name"] if row else name),
        "staff_code": str(row["internal_code"] if row else ""),
        "role": role,
        "role_label": PROJECT_STAFF_ROLE_LABELS.get(role, role),
        "strategy": strategy,
    }


def list_lead_project_options_for_staff(
    conn: sqlite3.Connection,
    staff_id: int,
    *,
    q: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Dropdown dự án — chỉ dự án NV tham gia (portal)."""
    pids = fetch_staff_project_ids(conn, int(staff_id))
    if not pids:
        return []
    lim = max(1, min(int(limit), 1000))
    params: list[Any] = []
    where = f" WHERE id IN ({','.join('?' * len(pids))})"
    params.extend(pids)
    if str(q or "").strip():
        like = f"%{str(q).strip()}%"
        where += " AND (name LIKE ? OR code LIKE ? OR city LIKE ?)"
        params.extend([like, like, like])
    rows = conn.execute(
        f"""
        SELECT id, code, name, status, city
        FROM crm_re_projects{where}
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        [*params, lim],
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "code": str(r["code"] or ""),
            "name": str(r["name"] or ""),
            "status": str(r["status"] or ""),
            "city": str(r["city"] or ""),
            "label": _project_option_label(r),
        }
        for r in rows
    ]


def list_lead_project_options(conn: sqlite3.Connection, *, q: str = "", limit: int = 500) -> list[dict[str, Any]]:
    """Danh sách rút gọn dự án cho dropdown Lead CRM."""
    try:
        conn.execute("SELECT 1 FROM crm_re_projects LIMIT 1")
    except sqlite3.OperationalError:
        return []
    lim = max(1, min(int(limit), 1000))
    params: list[Any] = []
    where = ""
    if str(q or "").strip():
        like = f"%{str(q).strip()}%"
        where = " WHERE name LIKE ? OR code LIKE ? OR city LIKE ?"
        params = [like, like, like]
    rows = conn.execute(
        f"""
        SELECT id, code, name, status, city
        FROM crm_re_projects{where}
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        [*params, lim],
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "code": str(r["code"] or ""),
            "name": str(r["name"] or ""),
            "status": str(r["status"] or ""),
            "city": str(r["city"] or ""),
            "label": _project_option_label(r),
        }
        for r in rows
    ]


def format_project_display_label(
    *,
    code: str = "",
    name: str = "",
    project_id: int | None = None,
) -> str:
    """Nhãn ngắn — chỉ mã dự án (dễ quét trên bảng / dropdown)."""
    c = str(code or "").strip()
    if c:
        return c
    n = str(name or "").strip()
    if n:
        return n
    if project_id:
        return f"#{int(project_id)}"
    return ""


def format_project_full_label(
    *,
    code: str = "",
    name: str = "",
    project_id: int | None = None,
) -> str:
    """Nhãn đầy đủ — tooltip / chi tiết lead."""
    c = str(code or "").strip()
    n = str(name or "").strip()
    if c and n:
        return f"{c} — {n}"
    return format_project_display_label(code=c, name=n, project_id=project_id)


def _project_option_label(row: sqlite3.Row | dict[str, Any]) -> str:
    return format_project_display_label(
        code=str(row["code"] or ""),
        name=str(row["name"] or ""),
        project_id=int(row["id"]) if row.get("id") is not None else None,
    )
