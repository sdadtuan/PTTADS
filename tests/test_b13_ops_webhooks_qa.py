"""QA helpers for Wave B13 Meta ops webhooks."""
from __future__ import annotations

import unittest


class TestB13OpsWebhooksQa(unittest.TestCase):
    def test_nest_ops_webhook_service_wired(self) -> None:
        webhooks = open("services/ptt-crm-api/src/webhooks/webhooks.service.ts", encoding="utf-8").read()
        module = open("services/ptt-crm-api/src/webhooks/webhooks.module.ts", encoding="utf-8").read()
        self.assertIn("MetaOpsWebhookService", webhooks)
        self.assertIn("ops_webhook", webhooks)
        self.assertIn("MetaOpsWebhookService", module)

    def test_worker_job_type_registered(self) -> None:
        worker = open("ptt_worker/__main__.py", encoding="utf-8").read()
        self.assertIn('job_type == "meta_ops_webhook"', worker)
        self.assertIn("run_meta_ops_webhook_job", worker)

    def test_ops_web_alert_labels(self) -> None:
        table = open("services/ops-web/src/components/meta/MetaAlertsTable.tsx", encoding="utf-8").read()
        self.assertIn("meta_account_disabled", table)
        self.assertIn("ad_disapproved", table)

    def test_hub_inline_disabled_alert(self) -> None:
        agency = open("services/ptt-crm-api/src/agency/agency.service.ts", encoding="utf-8").read()
        self.assertIn("ops_account_disabled_count", agency)
        self.assertIn("bị vô hiệu hóa", agency)


if __name__ == "__main__":
    unittest.main()
