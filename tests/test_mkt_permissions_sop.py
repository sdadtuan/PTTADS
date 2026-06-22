"""MKT-01/MKT-02 permissions seed + SOP launch template."""
from __future__ import annotations

import sqlite3
import unittest

from admin_page_permissions import default_grants_for_position, position_can, seed_marketing_positions
from cms_permissions import CMS_ACTIONS
from crm_sop_seed import LAUNCH_CAMPAIGN_STEPS, LAUNCH_CAMPAIGN_TEMPLATE_CODE, seed_launch_campaign_sop_template


def _perm_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE crm_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, name TEXT, description TEXT, sort_order INTEGER,
            active INTEGER, created_at TEXT, updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE crm_position_section_permissions (
            position_id INTEGER, section_id TEXT, action TEXT,
            PRIMARY KEY (position_id, section_id, action)
        )
        """
    )
    return conn


def _sop_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE crm_sop_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT, name TEXT, channel TEXT, description TEXT, notes TEXT,
            active INTEGER, created_at TEXT, updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE crm_sop_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER, position INTEGER, title TEXT, description TEXT,
            offset_days INTEGER, duration_days INTEGER, role TEXT, required INTEGER,
            checklist_json TEXT, created_at TEXT, updated_at TEXT
        )
        """
    )
    return conn


class TestMktPermissions(unittest.TestCase):
    def test_mkt01_default_grants(self) -> None:
        grants = default_grants_for_position("MKT-01")
        self.assertIn("configure", grants.get("crm_leads", []))
        self.assertIn("export", grants.get("crm_re_projects_budget", []))
        self.assertTrue(position_can(grants, "crm_re_projects_marketing", "edit"))
        self.assertFalse(position_can(grants, "crm_payroll_salary", "view"))

    def test_mkt02_limited_vs_mkt01(self) -> None:
        g1 = default_grants_for_position("MKT-01")
        g2 = default_grants_for_position("MKT-02")
        self.assertNotIn("configure", g2.get("crm_leads", []))
        self.assertNotIn("delete", g2.get("crm_hub_campaigns", []))
        self.assertIn("create", g2.get("crm_re_projects_budget", []))

    def test_seed_marketing_positions(self) -> None:
        conn = _perm_conn()
        out = seed_marketing_positions(conn)
        self.assertIsNone(out)
        rows = conn.execute(
            "SELECT code FROM crm_positions WHERE code IN ('MKT-01', 'MKT-02') ORDER BY code"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        mkt1 = conn.execute("SELECT id FROM crm_positions WHERE code = 'MKT-01'").fetchone()
        assert mkt1 is not None
        perms = conn.execute(
            "SELECT section_id, action FROM crm_position_section_permissions WHERE position_id = ?",
            (int(mkt1["id"]),),
        ).fetchall()
        self.assertGreater(len(perms), 10)
        self.assertTrue(any(r["section_id"] == "crm_hub_campaigns" for r in perms))
        seed_marketing_positions(conn)
        cnt = conn.execute("SELECT COUNT(*) AS n FROM crm_positions").fetchone()
        self.assertEqual(int(cnt["n"]), 2)


class TestSopLaunchSeed(unittest.TestCase):
    def test_seed_launch_template(self) -> None:
        conn = _sop_conn()
        r1 = seed_launch_campaign_sop_template(conn)
        self.assertTrue(r1["created"])
        self.assertEqual(r1["steps"], len(LAUNCH_CAMPAIGN_STEPS))
        tpl = conn.execute(
            "SELECT code, channel FROM crm_sop_templates WHERE id = ?",
            (int(r1["template_id"]),),
        ).fetchone()
        assert tpl is not None
        self.assertEqual(tpl["code"], LAUNCH_CAMPAIGN_TEMPLATE_CODE)
        self.assertEqual(tpl["channel"], "ads")
        steps = conn.execute(
            "SELECT COUNT(*) AS n FROM crm_sop_steps WHERE template_id = ?",
            (int(r1["template_id"]),),
        ).fetchone()
        self.assertEqual(int(steps["n"]), len(LAUNCH_CAMPAIGN_STEPS))
        r2 = seed_launch_campaign_sop_template(conn)
        self.assertFalse(r2["created"])
        self.assertEqual(r2["template_id"], r1["template_id"])


if __name__ == "__main__":
    unittest.main()
