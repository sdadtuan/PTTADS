"""Phân quyền menu sidebar admin theo vai trò CMS + chức vụ CRM."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import json
import unittest

from cms_permissions import CMS_CRM_NAV_MODULE_IDS, CMS_MODULE_IDS
from admin_page_permissions import SIDEBAR_CRM_NAV_SECTIONS


class AdminMenuPermissionsTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl chưa cài — bỏ qua test route Flask")
        from app import (
            ADMIN_SESSION_KEY,
            CMS_ROLE_SESSION_KEY,
            _admin_full_access,
            _admin_grants_bootstrap_json,
            app,
        )

        self.app = app
        self._admin_full_access = _admin_full_access
        self._admin_grants_bootstrap_json = _admin_grants_bootstrap_json
        self._admin_session_key = ADMIN_SESSION_KEY
        self._cms_role_session_key = CMS_ROLE_SESSION_KEY
        self.client = app.test_client()

    def _with_admin_role(self, role_code: str):
        ctx = self.app.test_request_context("/admin")
        ctx.push()
        from flask import session

        session[self._admin_session_key] = True
        session[self._cms_role_session_key] = role_code
        return ctx

    def test_full_access_only_super_and_cms_admin(self) -> None:
        for role in ("super_admin", "cms_admin"):
            ctx = self._with_admin_role(role)
            try:
                self.assertTrue(self._admin_full_access())
            finally:
                ctx.pop()
        for role in ("marketing_lead", "content_editor", "viewer"):
            ctx = self._with_admin_role(role)
            try:
                self.assertFalse(self._admin_full_access())
            finally:
                ctx.pop()

    def test_bootstrap_restricts_content_editor_cms_modules(self) -> None:
        ctx = self._with_admin_role("content_editor")
        try:
            raw = self._admin_grants_bootstrap_json()
            data = json.loads(raw)
            self.assertFalse(data["is_full_access"])
            self.assertTrue(data["is_admin_session"])
            grants = data["cms_grants"]
            self.assertIn("view", grants.get("projects", []))
            self.assertNotIn("view", grants.get("mk_chat_campaign_kit", []))
        finally:
            ctx.pop()

    def test_bootstrap_super_admin_full_grants(self) -> None:
        ctx = self._with_admin_role("super_admin")
        try:
            raw = self._admin_grants_bootstrap_json()
            data = json.loads(raw)
            self.assertTrue(data["is_full_access"])
            for mid in CMS_MODULE_IDS:
                self.assertIn("view", data["cms_grants"].get(mid, []))
        finally:
            ctx.pop()

    def test_role_matrix_includes_all_sidebar_nav_modules(self) -> None:
        """Ma trận vai trò CMS phải có đủ mục menu trái (CRM nav + dashboard)."""

        self.assertIn("admin_dashboard", CMS_MODULE_IDS)
        for sid in SIDEBAR_CRM_NAV_SECTIONS:
            self.assertIn(sid, CMS_MODULE_IDS, msg=f"Thiếu menu CRM: {sid}")
            self.assertIn(sid, CMS_CRM_NAV_MODULE_IDS)
        from cms_permissions import build_permission_matrix

        matrix = build_permission_matrix({})
        module_ids = {row["module_id"] for role in matrix["roles"] for row in role["grants"]}
        for sid in SIDEBAR_CRM_NAV_SECTIONS:
            self.assertIn(sid, module_ids)
        self.assertIn("admin_dashboard", module_ids)


if __name__ == "__main__":
    unittest.main()
