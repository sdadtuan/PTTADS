"""Đổi mật khẩu — hash DB phải thay thế mật khẩu .env."""
from __future__ import annotations

import sqlite3
import unittest

from unified_auth import set_unified_password, unified_login, verify_unified_password


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE cms_admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, role_code TEXT, position_id INTEGER,
            password_hash TEXT, active INTEGER, created_at TEXT, updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, login_username TEXT, password_hash TEXT,
            login_enabled INTEGER, active INTEGER, created_at TEXT, updated_at TEXT
        )
        """
    )
    return conn


def _const_eq(a: str, b: str) -> bool:
    return a == b


class TestUnifiedAuthPassword(unittest.TestCase):
    def test_env_password_works_before_hash_stored(self) -> None:
        conn = _conn()
        self.assertTrue(
            verify_unified_password(
                conn,
                "admin",
                "env-secret",
                env_username="admin",
                env_password="env-secret",
                const_eq=_const_eq,
            )
        )

    def test_old_env_password_rejected_after_password_change(self) -> None:
        conn = _conn()
        ts = "2026-05-25 12:00:00"
        conn.execute(
            """
            INSERT INTO cms_admin_users (username, role_code, password_hash, active, created_at, updated_at)
            VALUES ('admin', 'super_admin', '', 1, '2026-05-25', ?)
            """,
            (ts,),
        )
        set_unified_password(conn, "admin", "new-password-123", updated_at=ts)
        conn.commit()
        self.assertFalse(
            verify_unified_password(
                conn,
                "admin",
                "env-secret",
                env_username="admin",
                env_password="env-secret",
                const_eq=_const_eq,
            )
        )
        self.assertTrue(
            verify_unified_password(
                conn,
                "admin",
                "new-password-123",
                env_username="admin",
                env_password="env-secret",
                const_eq=_const_eq,
            )
        )

    def test_unified_login_uses_new_password_not_env(self) -> None:
        conn = _conn()
        ts = "2026-05-25 12:00:00"
        ph = set_unified_password(conn, "admin", "only-new-pw-99", updated_at=ts)
        conn.execute(
            """
            INSERT INTO cms_admin_users (username, role_code, password_hash, active, created_at, updated_at)
            VALUES ('admin', 'cms_admin', ?, 1, '2026-05-25', ?)
            """,
            (ph, ts),
        )
        self.assertIsNone(
            unified_login(
                conn,
                "admin",
                "env-secret",
                env_username="admin",
                env_password="env-secret",
                const_eq=_const_eq,
            )
        )
        hit = unified_login(
            conn,
            "admin",
            "only-new-pw-99",
            env_username="admin",
            env_password="env-secret",
            const_eq=_const_eq,
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.kind, "admin")


if __name__ == "__main__":
    unittest.main()
