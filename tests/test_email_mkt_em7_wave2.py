#!/usr/bin/env python3
"""Unit tests — EM-7 Wave 2 (ClickHouse, attribution, DNS, deliverability, reports)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_email.attribution import email_attribution_summary, rollup_daily_metrics
from ptt_email.dns_verify import verify_domain_dns
from ptt_email.deliverability import process_pending_suppressions, run_deliverability_scan
from ptt_email.bi_clickhouse import collect_daily_facts
from ptt_email.config import email_clickhouse_export_enabled, email_deliverability_alerts_enabled


class EmailWave2ConfigTests(unittest.TestCase):
    def test_clickhouse_export_default(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            self.assertTrue(email_clickhouse_export_enabled())

    def test_deliverability_alerts_default(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            self.assertTrue(email_deliverability_alerts_enabled())


class EmailDnsVerifyTests(unittest.TestCase):
    @patch("ptt_email.dns_verify._dig_txt")
    def test_verify_domain_dns_spf_pass(self, mock_dig) -> None:
        mock_dig.side_effect = lambda name: (
            ["v=spf1 include:sendgrid.net ~all"] if name == "mail.example.com" else ["v=DMARC1; p=none"]
            if name == "_dmarc.mail.example.com"
            else ["k=rsa; p=abc"] if "domainkey" in name else []
        )
        out = verify_domain_dns("mail.example.com")
        self.assertEqual(out["spf_status"], "pass")
        self.assertIn(out["dkim_status"], ("pass", "warn"))


class EmailAttributionTests(unittest.TestCase):
    @patch("ptt_jobs.db.pg_connection")
    def test_rollup_daily_metrics(self, mock_pg) -> None:
        conn = mock_pg.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.side_effect = [
            [("client-1",)],
            [("0",)],
            [("0",)],
            [("0",)],
            [("0",)],
        ]
        cur.fetchone.side_effect = [(0,), (0,), (0,), (0,), (0,)]
        with patch("ptt_email.attribution.email_attribution_summary", return_value={"revenue_attrib": 100, "leads_influenced": 1, "email_clicks": 2}):
            out = rollup_daily_metrics(client_id="client-1", metric_date="2026-07-19")
        self.assertTrue(out.get("ok"))
        self.assertGreaterEqual(out.get("updated", 0), 1)


class EmailDeliverabilityTests(unittest.TestCase):
    @patch("ptt_jobs.db.pg_connection")
    def test_process_pending_suppressions_empty(self, mock_pg) -> None:
        conn = mock_pg.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = []
        out = process_pending_suppressions(hours=24)
        self.assertTrue(out["ok"])
        self.assertEqual(out["suppressions_added"], 0)

    @patch("ptt_email.deliverability.scan_complaint_rates")
    @patch("ptt_email.deliverability.process_pending_suppressions")
    def test_run_deliverability_scan(self, mock_proc, mock_scan) -> None:
        mock_proc.return_value = {"ok": True, "suppressions_added": 0}
        mock_scan.return_value = {"ok": True, "paused": [], "alerts": []}
        out = run_deliverability_scan(hours=24)
        self.assertTrue(out["ok"])


class EmailBiClickhouseTests(unittest.TestCase):
    @patch("ptt_jobs.db.pg_connection")
    @patch("ptt_email.attribution.email_revenue_attributed")
    def test_collect_daily_facts(self, mock_rev, mock_pg) -> None:
        mock_rev.return_value = 50000.0
        conn = mock_pg.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = [("00000000-0000-0000-0000-000000000001",)]
        cur.fetchone.return_value = (10,)
        facts = collect_daily_facts(fact_date="2026-07-19")
        self.assertTrue(any(f.get("metric_name") == "emails_sent" for f in facts))


if __name__ == "__main__":
    unittest.main()
