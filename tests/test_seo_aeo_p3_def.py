"""Tests for P3d–f — RBAC approve, Slack alerts, report schedule polish."""
from __future__ import annotations

import os
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from admin_page_permissions import position_can
from cms_permissions import CMS_ACTIONS
from ptt_seo import schema as seo_schema
from ptt_seo.automation import create_alert
from ptt_seo.p2_schema import ensure_p2_schema
from ptt_seo.report_schedule import (
    build_report_email_html,
    compute_next_run,
    create_schedule,
    get_schedule,
)
from ptt_seo.slack_notify import notify_slack_for_alert, post_seo_slack, seo_slack_enabled


class TestP3dRbac(unittest.TestCase):
    def test_approve_action_registered(self) -> None:
        self.assertIn("approve", CMS_ACTIONS)

    def test_writer_role_no_approve(self) -> None:
        grants = {"crm_seo_aeo": ["view", "edit", "create", "export"]}
        self.assertTrue(position_can(grants, "crm_seo_aeo", "edit"))
        self.assertFalse(position_can(grants, "crm_seo_aeo", "approve"))

    def test_head_role_has_approve(self) -> None:
        grants = {"crm_seo_aeo": ["view", "edit", "create", "approve", "configure", "export"]}
        self.assertTrue(position_can(grants, "crm_seo_aeo", "approve"))


class TestP3eSlack(unittest.TestCase):
    def test_slack_disabled_without_env(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_SEO_SLACK_WEBHOOK", None)
            self.assertFalse(seo_slack_enabled())

    @patch.dict(os.environ, {"PTT_SEO_SLACK_WEBHOOK": "https://hooks.example.com/x"}, clear=False)
    @patch("ptt_seo.slack_notify.urllib.request.urlopen")
    def test_post_seo_slack_ok(self, mock_urlopen) -> None:
        mock_urlopen.return_value.__enter__.return_value.status = 200
        out = post_seo_slack("hello")
        self.assertTrue(out["ok"])

    @patch.dict(os.environ, {"PTT_SEO_SLACK_WEBHOOK": "https://hooks.example.com/x"}, clear=False)
    @patch("ptt_seo.slack_notify.post_seo_slack")
    def test_critical_alert_triggers_slack(self, mock_post) -> None:
        mock_post.return_value = {"ok": True}
        out = notify_slack_for_alert(
            alert_type="critical_issues",
            message="3 critical issues",
            link="/crm/seo/technical",
        )
        self.assertIsNotNone(out)
        mock_post.assert_called_once()

    @patch.dict(os.environ, {"PTT_SEO_SLACK_WEBHOOK": "https://hooks.example.com/x"}, clear=False)
    @patch("ptt_seo.slack_notify.post_seo_slack")
    def test_create_alert_hooks_slack(self, mock_post) -> None:
        mock_post.return_value = {"ok": True}
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        seo_schema.ensure_schema(conn)
        aid = create_alert(
            conn,
            customer_id=1,
            alert_type="critical_issues",
            severity="danger",
            message="2 critical",
            link="/crm/seo/technical",
        )
        self.assertIsNotNone(aid)
        mock_post.assert_called()


class TestP3fReportSchedule(unittest.TestCase):
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        seo_schema.ensure_schema(conn)
        ensure_p2_schema(conn)
        return conn

    def test_create_schedule_with_cc_bcc(self) -> None:
        conn = self._conn()
        sid = create_schedule(
            conn,
            1,
            {
                "recipient_emails": ["am@test.com"],
                "cc_emails": ["boss@test.com"],
                "bcc_emails": ["archive@test.com"],
                "dashboard_type": "executive",
                "cadence": "weekly",
            },
        )
        row = get_schedule(conn, sid)
        assert row is not None
        self.assertEqual(row["cc_emails"], ["boss@test.com"])
        self.assertEqual(row["bcc_emails"], ["archive@test.com"])

    def test_html_email_template(self) -> None:
        html = build_report_email_html(
            customer_label="Acme",
            dashboard_type="executive",
            report_date="2026-07-19",
            summary={"critical_issues": 2, "gsc": {"clicks": 10, "impressions": 100}},
        )
        self.assertIn("Acme", html)
        self.assertIn("Asia/Ho_Chi_Minh", html)
        self.assertIn("<html>", html)

    def test_compute_next_run_weekly_vn(self) -> None:
        monday = date(2026, 7, 20)
        nxt = compute_next_run(cadence="weekly", day_of_week=0, from_date=monday)
        self.assertEqual(nxt, "2026-07-27")


if __name__ == "__main__":
    unittest.main()
