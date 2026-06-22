"""Một username / một mật khẩu cho toàn bộ PTT (CMS admin + nhân viên CRM)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable

from crm_staff_auth import hash_password, normalize_login_username, verify_password


@dataclass(frozen=True)
class UnifiedLoginResult:
    kind: str  # "admin" | "staff"
    username: str
    role_code: str | None = None
    position_id: int | None = None
    staff_id: int | None = None
    staff_name: str | None = None


def lookup_cms_admin(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    key = normalize_login_username(username)
    if not key:
        return None
    row = conn.execute(
        """
        SELECT id, username, role_code, position_id, password_hash, active
        FROM cms_admin_users
        WHERE lower(trim(username)) = ? AND active = 1
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    return dict(row) if row else None


def lookup_staff_login(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    key = normalize_login_username(username)
    if not key:
        return None
    row = conn.execute(
        """
        SELECT id, name, login_username, password_hash, login_enabled, active
        FROM crm_staff
        WHERE lower(trim(login_username)) = ? AND trim(login_username) != ''
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    return dict(row) if row else None


def get_stored_password_hashes(conn: sqlite3.Connection, username: str) -> tuple[str, str]:
    key = normalize_login_username(username)
    if not key:
        return "", ""
    cms_row = conn.execute(
        """
        SELECT password_hash FROM cms_admin_users
        WHERE lower(trim(username)) = ? AND active = 1
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    staff_row = conn.execute(
        """
        SELECT password_hash FROM crm_staff
        WHERE lower(trim(login_username)) = ? AND trim(login_username) != ''
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    cms_h = str(cms_row["password_hash"] or "").strip() if cms_row else ""
    staff_h = str(staff_row["password_hash"] or "").strip() if staff_row else ""
    return cms_h, staff_h


def resolve_canonical_password_hash(conn: sqlite3.Connection, username: str) -> str:
    cms_h, staff_h = get_stored_password_hashes(conn, username)
    if cms_h and staff_h and cms_h != staff_h:
        return cms_h
    return cms_h or staff_h


def sync_password_hash(
    conn: sqlite3.Connection, username: str, password_hash: str, *, updated_at: str
) -> None:
    key = normalize_login_username(username)
    ph = str(password_hash or "").strip()
    if not key or not ph:
        return
    conn.execute(
        """
        UPDATE cms_admin_users
        SET password_hash = ?, updated_at = ?
        WHERE lower(trim(username)) = ? AND active = 1
        """,
        (ph, updated_at, key),
    )
    conn.execute(
        """
        UPDATE crm_staff
        SET password_hash = ?, updated_at = ?
        WHERE lower(trim(login_username)) = ? AND trim(login_username) != ''
        """,
        (ph, updated_at, key),
    )


def set_unified_password(
    conn: sqlite3.Connection, username: str, plain_password: str, *, updated_at: str
) -> str:
    ph = hash_password(str(plain_password or "").strip())
    sync_password_hash(conn, username, ph, updated_at=updated_at)
    return ph


def verify_unified_password(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    *,
    env_username: str,
    env_password: str,
    const_eq: Callable[[str, str], bool],
) -> bool:
    uname = str(username or "").strip()
    if not uname or not password:
        return False
    canonical = resolve_canonical_password_hash(conn, uname)
    if canonical:
        return verify_password(password, canonical)
    eu = str(env_username or "").strip()
    if eu and const_eq(uname, eu) and const_eq(password, env_password):
        return True
    return False


def migrate_unified_passwords(conn: sqlite3.Connection, *, updated_at: str) -> None:
    """Đồng bộ mật khẩu giữa cms_admin_users và crm_staff cùng username."""
    keys: set[str] = set()
    for row in conn.execute(
        """
        SELECT lower(trim(username)) AS u FROM cms_admin_users
        WHERE active = 1 AND trim(username) != ''
        """
    ).fetchall():
        u = str(row["u"] or "").strip()
        if u:
            keys.add(u)
    for row in conn.execute(
        """
        SELECT lower(trim(login_username)) AS u FROM crm_staff
        WHERE trim(login_username) != '' AND active = 1
        """
    ).fetchall():
        u = str(row["u"] or "").strip()
        if u:
            keys.add(u)
    for key in keys:
        canonical = resolve_canonical_password_hash(conn, key)
        if canonical:
            sync_password_hash(conn, key, canonical, updated_at=updated_at)


def ensure_unified_password_stored(
    conn: sqlite3.Connection,
    username: str,
    plain_password: str,
    *,
    updated_at: str,
) -> None:
    """Lưu hash mật khẩu vào DB nếu user chưa có hash (vd. đăng nhập bằng .env)."""
    if resolve_canonical_password_hash(conn, username):
        return
    set_unified_password(conn, username, plain_password, updated_at=updated_at)


def unified_login(
    conn: sqlite3.Connection,
    username: str,
    password: str,
    *,
    env_username: str,
    env_password: str,
    const_eq: Callable[[str, str], bool],
) -> UnifiedLoginResult | None:
    uname = str(username or "").strip()
    if not verify_unified_password(
        conn,
        uname,
        password,
        env_username=env_username,
        env_password=env_password,
        const_eq=const_eq,
    ):
        return None

    cms = lookup_cms_admin(conn, uname)
    if cms:
        role_code = str(cms.get("role_code") or "viewer")
        position_id: int | None = None
        if role_code not in ("super_admin", "cms_admin"):
            try:
                pid = int(cms.get("position_id") or 0)
                if pid > 0:
                    position_id = pid
            except (TypeError, ValueError):
                position_id = None
        return UnifiedLoginResult(
            kind="admin",
            username=str(cms.get("username") or uname),
            role_code=role_code,
            position_id=position_id,
        )

    eu = str(env_username or "").strip()
    canonical = resolve_canonical_password_hash(conn, uname)
    if not canonical and eu and const_eq(uname, eu) and const_eq(password, env_password):
        return UnifiedLoginResult(
            kind="admin",
            username=uname,
            role_code="super_admin",
            position_id=None,
        )

    staff = lookup_staff_login(conn, uname)
    if (
        staff
        and int(staff.get("active") or 0)
        and int(staff.get("login_enabled") or 0)
    ):
        return UnifiedLoginResult(
            kind="staff",
            username=str(staff.get("login_username") or uname),
            staff_id=int(staff["id"]),
            staff_name=str(staff.get("name") or ""),
        )
    return None
