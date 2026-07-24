"""QA helpers for Wave B14 warehouse BI."""
from __future__ import annotations

import json
import unittest


class TestB14WarehouseQa(unittest.TestCase):
    def test_clickhouse_ddl(self) -> None:
        ddl = open("deploy/clickhouse/init-meta-daily-facts.sql", encoding="utf-8").read()
        self.assertIn("ptt.meta_daily_facts", ddl)
        self.assertIn("INTERVAL 36 MONTH", ddl)

    def test_grafana_dashboard_spend_trend(self) -> None:
        dash = json.load(open("deploy/grafana/meta-ops-dashboard.json", encoding="utf-8"))
        titles = [p.get("title", "") for p in dash.get("panels", [])]
        self.assertTrue(any("spend trend" in t.lower() for t in titles))

    def test_nest_modules_registered(self) -> None:
        app = open("services/ptt-crm-api/src/app.module.ts", encoding="utf-8").read()
        self.assertIn("MetaComplianceModule", app)
        self.assertIn("MetricsModule", app)

    def test_compliance_route(self) -> None:
        ctrl = open(
            "services/ptt-crm-api/src/meta-compliance/meta-compliance.controller.ts",
            encoding="utf-8",
        ).read()
        self.assertIn("@Get('export')", ctrl)
        self.assertIn("meta/compliance", ctrl)

    def test_cross_channel_route(self) -> None:
        ctrl = open("services/ptt-crm-api/src/metrics/metrics.controller.ts", encoding="utf-8").read()
        self.assertIn("cross-channel/summary", ctrl)

    def test_worker_job_registered(self) -> None:
        worker = open("ptt_worker/__main__.py", encoding="utf-8").read()
        self.assertIn("meta_clickhouse_export", worker)


if __name__ == "__main__":
    unittest.main()
