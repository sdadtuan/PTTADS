"""Gate D — Grafana BI metrics, CWV, crawl reminders, Teams, AEO schedule."""
from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.aeo_store import add_aeo_question, insert_mention
from ptt_seo.aeo_schedule import create_drafts_from_gaps, run_aeo_schedule_for_customer
from ptt_seo.alert_notify import notify_seo_alert
from ptt_seo.bi_clickhouse import collect_daily_facts
from ptt_seo.content import create_content
from ptt_seo.crawl_reminder import last_crawl_import_at, record_crawl_import, run_crawl_reminders
from ptt_seo.cwv import capture_cwv_for_customer, effective_pagespeed, parse_pagespeed_response
from ptt_seo.enterprise_schema import ensure_enterprise_schema
from ptt_seo.gate_d_schema import ensure_gate_d_schema
from ptt_seo.research_schema import ensure_research_schema
from ptt_seo.teams_notify import notify_teams_for_alert, post_seo_teams


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '');")
    seo_schema.ensure_schema(conn)
    ensure_research_schema(conn)
    ensure_enterprise_schema(conn)
    ensure_gate_d_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
    conn.commit()
    return conn


class TestGateDBiFacts(unittest.TestCase):
    def test_aeo_coverage_fact(self) -> None:
        conn = _mem_conn()
        q1 = add_aeo_question(conn, 1, "what is seo", "Acme")
        q2 = add_aeo_question(conn, 1, "seo agency", "Acme")
        insert_mention(
            conn,
            customer_id=1,
            question_id=q1,
            query_text="what is seo",
            scan={"brand_visible": True, "gap_notes": "", "ai_response": "x"},
        )
        insert_mention(
            conn,
            customer_id=1,
            question_id=q2,
            query_text="seo agency",
            scan={"brand_visible": False, "gap_notes": "missing FAQ", "ai_response": "y"},
        )
        facts = collect_daily_facts(conn)
        cov = [f for f in facts if f["metric_name"] == "aeo_coverage_pct" and f["customer_id"] == 1]
        self.assertEqual(len(cov), 1)
        self.assertEqual(cov[0]["metric_value"], 50.0)


class TestGateDCwv(unittest.TestCase):
    def test_parse_pagespeed_response(self) -> None:
        data = {
            "lighthouseResult": {
                "categories": {"performance": {"score": 0.85}},
                "audits": {
                    "largest-contentful-paint": {"numericValue": 2200},
                    "cumulative-layout-shift": {"numericValue": 0.04},
                    "interaction-to-next-paint": {"numericValue": 150},
                },
            }
        }
        m = parse_pagespeed_response(data)
        self.assertEqual(m["cwv_rating"], "pass")
        self.assertEqual(m["performance_score"], 85.0)

    @patch.dict(os.environ, {"PTT_CWV_STUB": "1"}, clear=False)
    def test_capture_cwv_stub(self) -> None:
        conn = _mem_conn()
        conn.execute(
            "INSERT INTO seo_client_settings (customer_id, domains_json, updated_at) VALUES (1, '[\"example.com\"]', 'now')"
        )
        conn.commit()
        out = capture_cwv_for_customer(conn, 1, limit=1)
        self.assertEqual(out["captured"], 1)
        row = conn.execute("SELECT cwv_rating FROM seo_cwv_snapshots WHERE customer_id = 1").fetchone()
        self.assertEqual(row["cwv_rating"], "pass")

    @patch.dict(os.environ, {"PTT_CWV_STUB": "1"}, clear=False)
    def test_effective_pagespeed_stub(self) -> None:
        m = effective_pagespeed("https://example.com/")
        self.assertEqual(m["source"], "stub")


class TestGateDCrawlReminder(unittest.TestCase):
    def test_record_and_remind(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO seo_client_settings (customer_id, updated_at) VALUES (1, 'now')")
        conn.commit()
        record_crawl_import(conn, 1, 12)
        self.assertIsNotNone(last_crawl_import_at(conn, 1))
        out = run_crawl_reminders(conn, max_age_days=30)
        self.assertTrue(out["ok"])
        self.assertEqual(out["reminders"], 0)

    def test_stale_crawl_creates_alert(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO seo_client_settings (customer_id, updated_at) VALUES (1, 'now')")
        conn.commit()
        out = run_crawl_reminders(conn, max_age_days=30)
        self.assertEqual(out["reminders"], 1)
        alert = conn.execute("SELECT alert_type FROM seo_alerts WHERE customer_id = 1").fetchone()
        self.assertEqual(alert["alert_type"], "crawl_stale")


class TestGateDTeams(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_SEO_TEAMS_WEBHOOK": "https://teams.example/hook"}, clear=False)
    @patch("ptt_seo.teams_notify.urllib.request.urlopen")
    def test_post_teams(self, mock_urlopen) -> None:
        mock_urlopen.return_value.__enter__.return_value.status = 200
        out = post_seo_teams("hello")
        self.assertTrue(out["ok"])

    @patch("ptt_seo.slack_notify.notify_slack_for_alert", return_value={"ok": True})
    @patch("ptt_seo.teams_notify.notify_teams_for_alert", return_value={"ok": True})
    def test_unified_notify(self, _teams, _slack) -> None:
        out = notify_seo_alert(alert_type="critical_issues", message="test", link="/crm/seo")
        self.assertIn("slack", out)
        self.assertIn("teams", out)


class TestGateDAeoSchedule(unittest.TestCase):
    def test_auto_draft_from_gaps(self) -> None:
        conn = _mem_conn()
        qid = add_aeo_question(conn, 1, "best seo tool", "Acme")
        scan_results = [
            {"query_id": qid, "ok": True, "brand_visible": False, "gap_notes": "Need comparison table"},
        ]
        with patch.dict(os.environ, {"PTT_AEO_AUTO_DRAFT_ENABLED": "1"}, clear=False):
            drafts = create_drafts_from_gaps(conn, 1, scan_results)
        self.assertEqual(len(drafts), 1)
        row = conn.execute(
            "SELECT workflow_status, target_question_id FROM seo_content WHERE id = ?",
            (drafts[0]["content_id"],),
        ).fetchone()
        self.assertEqual(row["workflow_status"], "brief_ready")
        self.assertEqual(row["target_question_id"], qid)

    @patch("ptt_seo.aeo_schedule.scan_customer_batch")
    def test_run_schedule_for_customer(self, mock_batch) -> None:
        conn = _mem_conn()
        qid = add_aeo_question(conn, 1, "aeo query", "Acme")
        mock_batch.return_value = {
            "ok": True,
            "results": [{"query_id": qid, "ok": True, "brand_visible": False, "gap_notes": "gap"}],
        }
        with patch.dict(os.environ, {"PTT_AEO_AUTO_DRAFT_ENABLED": "1"}, clear=False):
            out = run_aeo_schedule_for_customer(conn, 1)
        self.assertEqual(out["drafts_created"], 1)


class TestGateDCron(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "PTT_CWV_ENABLED": "0",
            "PTT_AEO_SCHEDULE_ENABLED": "0",
            "PTT_CRAWL_REMINDER_ENABLED": "0",
        },
        clear=False,
    )
    def test_run_gate_d_cron_skips(self) -> None:
        from ptt_seo.cron import run_gate_d_cron

        out = run_gate_d_cron()
        self.assertTrue(out["ok"])
        self.assertTrue(out["jobs"]["cwv_capture"].get("skipped"))
        self.assertTrue(out["jobs"]["aeo_schedule"].get("skipped"))
        self.assertTrue(out["jobs"]["crawl_reminder"].get("skipped"))


if __name__ == "__main__":
    unittest.main()
