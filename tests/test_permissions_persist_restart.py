"""Ma trận phân quyền không bị seed lại sau restart (migrate)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest

from admin_page_permissions import (
    backfill_position_grants_customized,
    ensure_position_grants_customized_column,
)
from cms_permissions import (
    CMS_MODULE_IDS,
    backfill_role_grants_customized,
    default_grants_for_role,
    ensure_role_grants_customized_column,
    migrate_cms_role_sidebar_modules,
)


class PermissionsPersistRestartTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE cms_roles (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                is_system INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT '',
                grants_customized INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE cms_role_permissions (
                role_code TEXT NOT NULL,
                module_id TEXT NOT NULL,
                action TEXT NOT NULL,
                PRIMARY KEY (role_code, module_id, action)
            );
            INSERT INTO cms_roles (code, name, description, is_system, updated_at, grants_customized)
            VALUES ('marketing_staff', 'NV Marketing', '', 1, '', 0);
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_migrate_skips_customized_role(self) -> None:
        """Vai trò đã lưu ma trận — restart không thêm lại module mặc định."""
        code = "marketing_staff"
        self.conn.execute(
            "UPDATE cms_roles SET grants_customized = 1 WHERE code = ?",
            (code,),
        )
        self.conn.execute(
            """
            INSERT INTO cms_role_permissions (role_code, module_id, action)
            VALUES (?, 'crm_leads', 'view')
            """,
            (code,),
        )
        self.conn.commit()
        migrate_cms_role_sidebar_modules(self.conn)
        self.conn.commit()
        rows = self.conn.execute(
            "SELECT module_id, action FROM cms_role_permissions WHERE role_code = ? ORDER BY module_id, action",
            (code,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0]["module_id"]), "crm_leads")
        self.assertEqual(str(rows[0]["action"]), "view")

    def test_backfill_marks_existing_roles_customized(self) -> None:
        """DB cũ đã có quyền — backfill một lần, migrate sau đó không ghi đè."""
        code = "marketing_staff"
        self.conn.execute(
            """
            INSERT INTO cms_role_permissions (role_code, module_id, action)
            VALUES (?, 'admin_dashboard', 'view')
            """,
            (code,),
        )
        self.conn.commit()
        ensure_role_grants_customized_column(self.conn)
        backfill_role_grants_customized(self.conn)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT grants_customized FROM cms_roles WHERE code = ?",
            (code,),
        ).fetchone()
        self.assertEqual(int(row["grants_customized"]), 1)
        migrate_cms_role_sidebar_modules(self.conn)
        self.conn.commit()
        cnt = self.conn.execute(
            "SELECT COUNT(*) AS n FROM cms_role_permissions WHERE role_code = ?",
            (code,),
        ).fetchone()
        self.assertEqual(int(cnt["n"]), 1)

    def test_non_customized_role_still_gets_new_modules(self) -> None:
        """Vai trò chưa tùy chỉnh vẫn được bổ sung module mới (seed migrate)."""
        code = "marketing_staff"
        defaults = default_grants_for_role(code)
        first_mid = next(iter(CMS_MODULE_IDS))
        first_acts = defaults.get(first_mid) or ["view"]
        for act in first_acts:
            self.conn.execute(
                """
                INSERT INTO cms_role_permissions (role_code, module_id, action)
                VALUES (?, ?, ?)
                """,
                (code, first_mid, act),
            )
        self.conn.commit()
        migrate_cms_role_sidebar_modules(self.conn)
        self.conn.commit()
        cnt = self.conn.execute(
            "SELECT COUNT(*) AS n FROM cms_role_permissions WHERE role_code = ?",
            (code,),
        ).fetchone()
        self.assertGreater(int(cnt["n"]), len(first_acts))

    def test_position_backfill_marks_customized(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE crm_positions (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                grants_customized INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE crm_position_section_permissions (
                position_id INTEGER NOT NULL,
                section_id TEXT NOT NULL,
                action TEXT NOT NULL,
                PRIMARY KEY (position_id, section_id, action)
            );
            INSERT INTO crm_positions (id, code, name, active) VALUES (1, 'MKT-02', 'NV MKT', 1);
            INSERT INTO crm_position_section_permissions (position_id, section_id, action)
            VALUES (1, 'crm_leads', 'view');
            """
        )
        self.conn.commit()
        ensure_position_grants_customized_column(self.conn)
        backfill_position_grants_customized(self.conn)
        self.conn.commit()
        row = self.conn.execute(
            "SELECT grants_customized FROM crm_positions WHERE id = 1"
        ).fetchone()
        self.assertEqual(int(row["grants_customized"]), 1)


if __name__ == "__main__":
    unittest.main()
