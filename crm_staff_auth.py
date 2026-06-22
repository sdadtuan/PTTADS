"""Đăng nhập nhân viên CRM — tài khoản riêng, chỉ truy cập Chăm sóc khách hàng."""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import sqlite3
from typing import Any

_LOGIN_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,64}$")
_PBKDF2_ITERATIONS = 260_000


def normalize_login_username(raw: str | None) -> str:
    return str(raw or "").strip().lower()


def validate_login_username(raw: str | None) -> str | None:
    u = normalize_login_username(raw)
    if not u:
        return None
    if not _LOGIN_USERNAME_RE.match(u):
        return None
    return u


def hash_password(password: str) -> str:
    pw = str(password or "")
    if len(pw) < 6:
        raise ValueError("Mật khẩu tối thiểu 6 ký tự.")
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        pw.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    b64 = base64.urlsafe_b64encode(dk).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${b64}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    sh = str(stored_hash or "").strip()
    if not sh or not password:
        return False
    try:
        algo, iter_s, salt, b64 = sh.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
        pad = "=" * (-len(b64) % 4)
        dk_expected = base64.urlsafe_b64decode(b64 + pad)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return secrets.compare_digest(dk, dk_expected)
    except (ValueError, TypeError):
        return False


def ensure_staff_login_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_staff)")}
    migrations = [
        (
            "login_username",
            "ALTER TABLE crm_staff ADD COLUMN login_username TEXT NOT NULL DEFAULT ''",
        ),
        (
            "password_hash",
            "ALTER TABLE crm_staff ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''",
        ),
        (
            "login_enabled",
            "ALTER TABLE crm_staff ADD COLUMN login_enabled INTEGER NOT NULL DEFAULT 0",
        ),
    ]
    for _name, sql in migrations:
        if _name not in cols:
            conn.execute(sql)
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_crm_staff_login_username
        ON crm_staff(lower(trim(login_username)))
        WHERE trim(login_username) != ''
        """
    )


def authenticate_staff(
    conn: sqlite3.Connection, username: str, password: str
) -> dict[str, Any] | None:
    uname = normalize_login_username(username)
    if not uname or not password:
        return None
    row = conn.execute(
        """
        SELECT id, name, login_username, password_hash, login_enabled, active
        FROM crm_staff
        WHERE lower(trim(login_username)) = ? AND trim(login_username) != ''
        LIMIT 1
        """,
        (uname,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if not int(d.get("active") or 0):
        return None
    if not int(d.get("login_enabled") or 0):
        return None
    if not verify_password(password, str(d.get("password_hash") or "")):
        return None
    return d


def staff_login_username_taken(
    conn: sqlite3.Connection, username: str, *, exclude_id: int | None = None
) -> bool:
    uname = validate_login_username(username)
    if not uname:
        return False
    q = """
        SELECT 1 FROM crm_staff
        WHERE lower(trim(login_username)) = ? AND trim(login_username) != ''
    """
    params: list[Any] = [uname]
    if exclude_id is not None:
        q += " AND id != ?"
        params.append(exclude_id)
    return conn.execute(q, params).fetchone() is not None


def apply_staff_login_from_payload(
    conn: sqlite3.Connection,
    merged: dict[str, Any],
    payload: dict[str, Any],
    *,
    staff_id: int | None = None,
) -> str | None:
    """Cập nhật login_username / password / login_enabled. Trả lỗi hoặc None."""
    if "login_username" in payload:
        raw_u = payload.get("login_username")
        if raw_u is None or str(raw_u).strip() == "":
            merged["login_username"] = ""
            merged["login_enabled"] = 0
            merged["password_hash"] = ""
        else:
            uname = validate_login_username(str(raw_u))
            if not uname:
                return "Tên đăng nhập: 3–64 ký tự, chỉ chữ, số, . _ -"
            if staff_login_username_taken(conn, uname, exclude_id=staff_id):
                return f"Tên đăng nhập «{uname}» đã được dùng."
            merged["login_username"] = uname

    if "login_enabled" in payload:
        merged["login_enabled"] = 1 if payload.get("login_enabled") else 0

    if "login_password" in payload:
        pw = str(payload.get("login_password") or "")
        if pw.strip():
            try:
                merged["password_hash"] = hash_password(pw.strip())
            except ValueError as exc:
                return str(exc)
            if not str(merged.get("login_username") or "").strip():
                return "Cần tên đăng nhập khi đặt mật khẩu."
            merged["login_enabled"] = 1

    if int(merged.get("login_enabled") or 0) and not str(
        merged.get("login_username") or ""
    ).strip():
        return "Bật đăng nhập cần có tên đăng nhập."
    if int(merged.get("login_enabled") or 0) and not str(
        merged.get("password_hash") or ""
    ).strip():
        return "Bật đăng nhập cần mật khẩu."

    return None


def staff_row_for_api(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    d.pop("password_hash", None)
    d["has_login"] = bool(
        int(d.get("login_enabled") or 0)
        and str(d.get("login_username") or "").strip()
    )
    return d


def staff_crm_api_allowed(method: str, path: str) -> bool:
    m = (method or "GET").upper()
    p = (path or "").split("?", 1)[0]
    if m == "GET" and p == "/api/crm/cases":
        return True
    if m == "GET" and p.startswith("/api/crm/channels"):
        return True
    if m == "GET" and p.startswith("/api/crm/campaigns"):
        return True
    if m == "GET" and re.match(r"^/api/crm/cases/\d+$", p):
        return True
    if m == "PATCH" and re.match(r"^/api/crm/cases/\d+$", p):
        return True
    if m == "POST" and re.match(r"^/api/crm/cases/\d+/events$", p):
        return True
    if m == "POST" and re.match(r"^/api/crm/cases/\d+/care-reports$", p):
        return True
    if m == "GET" and re.match(r"^/api/crm/staff/\d+/workspace$", p):
        return True
    if m == "GET" and p == "/api/crm/customers":
        return True
    if m == "GET" and re.match(r"^/api/crm/customers/\d+$", p):
        return True
    return False


def staff_portal_html_allowed(path: str) -> bool:
    p = (path or "").split("?", 1)[0].rstrip("/") or "/"
    return p in (
        "/crm",
        "/crm/home",
        "/crm/customers",
        "/crm/kpi",
        "/crm/payroll",
        "/crm/attendance",
        "/crm/daily-reports",
        "/crm/leads",
        "/account/password",
    )


def staff_crm_api_allowed_extended(method: str, path: str) -> bool:
    if staff_crm_api_allowed(method, path):
        return True
    m = (method or "GET").upper()
    p = (path or "").split("?", 1)[0]
    if m == "GET" and p == "/api/crm/staff/me":
        return True
    if m == "GET" and p == "/api/crm/staff/dashboard":
        return True
    if m == "GET" and p == "/api/crm/kpi/metrics":
        return True
    if m == "GET" and p == "/api/crm/staff/kpi":
        return True
    if m == "POST" and p == "/api/crm/staff/kpi":
        return True
    if m == "PATCH" and re.match(r"^/api/crm/staff/kpi/\d+$", p):
        return True
    if m == "GET" and p == "/api/crm/attendance":
        return True
    if m == "GET" and p == "/api/crm/kpi/alerts":
        return True
    if m == "GET" and p == "/api/crm/kpi/chart":
        return True
    if m == "POST" and p == "/api/account/change-password":
        return True
    if m == "POST" and re.match(r"^/api/crm/customers/\d+/issues$", p):
        return True
    if m == "PATCH" and re.match(r"^/api/crm/customers/\d+/issues/\d+$", p):
        return True
    if m == "GET" and p == "/api/crm/assistant/config":
        return True
    if m == "POST" and p.startswith("/api/crm/assistant/"):
        return True
    if m == "GET" and p == "/api/crm/payroll/export":
        return True
    if m == "GET" and p == "/api/crm/staff/daily-work-report-template":
        return True
    if m == "GET" and p.startswith("/api/crm/daily-work-reports"):
        return True
    if m == "POST" and p == "/api/crm/daily-work-reports":
        return True
    if m == "PATCH" and re.match(r"^/api/crm/daily-work-reports/\d+$", p):
        return True
    if m == "GET" and (p == "/api/crm/leads/stats" or p == "/api/crm/leads" or re.match(r"^/api/crm/leads/\d+$", p)):
        return True
    if m == "GET" and p == "/api/crm/leads/notifications":
        return True
    if m == "GET" and re.match(r"^/api/crm/leads/\d+/activities$", p):
        return True
    if m == "GET" and re.match(r"^/api/crm/leads/\d+/(status-logs|assignment-logs|audit)$", p):
        return True
    if m == "POST" and p == "/api/crm/leads":
        return True
    if m == "PUT" and re.match(r"^/api/crm/leads/\d+$", p):
        return True
    if m == "POST" and re.match(r"^/api/crm/leads/\d+/activities$", p):
        return True
    if m == "POST" and re.match(r"^/api/crm/leads/\d+/care-stages$", p):
        return True
    if m == "POST" and p.startswith("/api/crm/leads/ai/"):
        return True
    if m == "POST" and re.match(r"^/api/crm/leads/\d+/convert$", p):
        return True
    if m == "GET" and p == "/api/crm/leads/export":
        return True
    return False
