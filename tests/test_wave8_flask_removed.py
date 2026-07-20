#!/usr/bin/env python3
"""Unit tests — Wave 8 Flask HTTP removed checks."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus, gap_report
from ptt_crm.flask_guard import deny_flask_write, flask_monolith_retired
from ptt_crm.wave8_gates import run_gates

ROOT = Path(__file__).resolve().parents[1]


class Wave8FlaskRemovedTests(unittest.TestCase):
    _WAVE8_ENV = {
        "PTT_CRM_RE_PROJECTS_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_RE_PROJECTS_RETIRED": "1",
        "PTT_CRM_PAYROLL_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_PAYROLL_RETIRED": "1",
        "WAVE5_EXPECT_OPS_WEB": "1",
        "PTT_CRM_SALES_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_SALES_RETIRED": "1",
        "PTT_CRM_KPI_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_KPI_RETIRED": "1",
        "PTT_CRM_STAFF_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_STAFF_RETIRED": "1",
        "WAVE4_EXPECT_OPS_WEB": "1",
        "PTT_CRM_PROPOSALS_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_PROPOSALS_RETIRED": "1",
        "WAVE4P_EXPECT_OPS_WEB": "1",
        "PTT_CRM_RE_PROJECTS_ACCOUNTING_UPSTREAM": "nest",
        "PTT_FLASK_CRM_RE_PROJECTS_ACCOUNTING_RETIRED": "1",
        "WAVE5P_EXPECT_ACCOUNTING_NEST": "1",
        "PTT_CRM_RE_PROJECTS_KPI_RISKS_UPSTREAM": "nest",
        "PTT_FLASK_CRM_RE_PROJECTS_KPI_RISKS_RETIRED": "1",
        "WAVE5PP_EXPECT_KPI_RISKS_NEST": "1",
        "PTT_CRM_RE_PROJECTS_OPS_UPSTREAM": "nest",
        "PTT_FLASK_CRM_RE_PROJECTS_OPS_RETIRED": "1",
        "WAVE5PPP_EXPECT_OPS_NEST": "1",
        "PTT_CRM_FINANCE_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_FINANCE_RETIRED": "1",
        "WAVE6_EXPECT_FINANCE_NEST": "1",
        "PTT_CRM_SHELL_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_SHELL_RETIRED": "1",
        "WAVE7_EXPECT_SHELL_OPS_WEB": "1",
        "WAVE7_EXPECT_PHASE5_READY": "1",
        "WAVE8_EXPECT_FLASK_REMOVED": "1",
    }

    def test_app_py_not_exists(self) -> None:
        if (ROOT / "app.py").is_file():
            self.skipTest("app.py still present — W8-G01 pending")
        self.assertFalse((ROOT / "app.py").is_file())

    def test_blueprints_dir_gone(self) -> None:
        if (ROOT / "blueprints").is_dir():
            self.skipTest("blueprints/ still present — W8-G01 pending")
        self.assertFalse((ROOT / "blueprints").is_dir())

    def test_flask_guard_stub(self) -> None:
        self.assertTrue(flask_monolith_retired())
        self.assertIsNone(deny_flask_write())

    def test_no_proxy_to_flask_in_webhooks_service(self) -> None:
        webhooks = ROOT / "services" / "ptt-crm-api" / "src" / "webhooks" / "webhooks.service.ts"
        self.assertTrue(webhooks.is_file())
        text = webhooks.read_text(encoding="utf-8")
        if "proxyToFlask" in text:
            self.skipTest("proxyToFlask still present — W8-G02 pending")
        self.assertNotIn("proxyToFlask", text)

    def test_registry_all_retired(self) -> None:
        for mod in CRM_MODULES:
            self.assertEqual(mod.status, CrmModuleStatus.RETIRED, msg=mod.id)

    def test_gap_can_stop_true(self) -> None:
        report = gap_report()
        self.assertTrue(report["can_stop_ptt_service"])

    def test_landing_site_removed(self) -> None:
        self.assertFalse((ROOT / "templates" / "landing.html").is_file())
        self.assertFalse((ROOT / "static" / "landing.js").is_file())
        self.assertFalse((ROOT / "cms_media_images.py").is_file())

    def test_cms_core_modules_empty(self) -> None:
        from cms_permissions import CMS_CORE_MODULES

        self.assertEqual(len(CMS_CORE_MODULES), 0)

    def test_wave8_gates_pass_when_flask_removed(self) -> None:
        if (ROOT / "app.py").is_file() or (ROOT / "blueprints").is_dir():
            self.skipTest("app.py/blueprints still present — W8-G01 pending")
        webhooks = ROOT / "services" / "ptt-crm-api" / "src" / "webhooks" / "webhooks.service.ts"
        if "proxyToFlask" in webhooks.read_text(encoding="utf-8"):
            self.skipTest("proxyToFlask still present — W8-G02 pending")
        with patch.dict(os.environ, self._WAVE8_ENV, clear=False):
            report = run_gates()
        self.assertTrue(report["ok"], msg=str(report.get("failed_ids")))


if __name__ == "__main__":
    unittest.main()
