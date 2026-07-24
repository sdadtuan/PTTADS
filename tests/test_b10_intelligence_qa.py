"""Wave B10 — Meta Intelligence UI + API static QA checks."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestB10IntelligenceQa(unittest.TestCase):
    def test_intelligence_page_route_and_content(self) -> None:
        page = _read("services/ops-web/src/app/meta/intelligence/page.tsx")
        content = _read("services/ops-web/src/app/meta/intelligence/MetaIntelligenceContent.tsx")
        self.assertIn("MetaIntelligenceContent", page)
        self.assertIn("MetaIntelligenceRoasKpi", content)
        self.assertIn("MetaAnomaliesTable", content)
        self.assertIn("MetaBudgetRecommendTable", content)
        self.assertIn("Tạo write request", _read("services/ops-web/src/components/meta/MetaBudgetRecommendTable.tsx"))

    def test_meta_api_intelligence_endpoints(self) -> None:
        text = _read("services/ops-web/src/lib/meta/api.ts")
        for path in (
            "/api/v1/meta/anomalies",
            "/api/v1/meta/roas",
            "/api/v1/meta/budget-recommendations",
        ):
            self.assertIn(path, text, msg=f"missing {path}")
        self.assertIn("fetchMetaAnomalies", text)
        self.assertIn("fetchMetaRoas", text)
        self.assertIn("fetchMetaBudgetRecommendations", text)

    def test_meta_flags_and_caps(self) -> None:
        flags = _read("services/ops-web/src/lib/meta/flags.ts")
        caps = _read("services/ops-web/src/lib/meta/caps.ts")
        self.assertIn("NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED", flags)
        self.assertIn("NEXT_PUBLIC_PTT_META_ROAS_ENABLED", flags)
        self.assertIn("metaIntelligenceEnabled", flags)
        self.assertIn("canViewMetaIntelligence", caps)

    def test_ops_nav_intelligence_link(self) -> None:
        text = _read("services/ops-web/src/components/OpsNav.tsx")
        self.assertIn("/meta/intelligence", text)
        self.assertIn("Meta Intelligence", text)
        self.assertIn("metaIntelligenceEnabled", text)

    def test_nest_meta_intelligence_controller_routes(self) -> None:
        text = _read("services/ptt-crm-api/src/meta-intelligence/meta-intelligence.controller.ts")
        self.assertIn("@Get('anomalies')", text)
        self.assertIn("@Get('roas')", text)
        self.assertIn("@Get('budget-recommendations')", text)

    def test_python_b10_modules_exist(self) -> None:
        for rel in ("ptt_meta/anomaly.py", "ptt_meta/roas.py", "ptt_meta/budget_recommend.py"):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_alerts_eval_calls_anomaly(self) -> None:
        text = _read("ptt_meta/alerts.py")
        self.assertIn("evaluate_anomaly_alerts", text)
