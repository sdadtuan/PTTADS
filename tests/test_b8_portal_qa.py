"""Wave B8 — Portal CPL delta + attribution static QA checks."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestB8PortalQa(unittest.TestCase):
    def test_performance_table_has_map_and_cpl_delta_columns(self) -> None:
        text = _read("services/portal-web/src/components/PerformanceTable.tsx")
        self.assertIn("CPL Δ", text)
        self.assertIn("Map", text)
        self.assertIn("map-badge", text)
        self.assertIn("fmtDeltaVnd", text)
        self.assertIn("fmtDeltaPct", text)
        self.assertIn("hub_mapped", text)

    def test_portal_attribution_footer_contract(self) -> None:
        text = _read("services/portal-web/src/components/PortalAttributionFooter.tsx")
        self.assertIn("attribution_model", text)
        self.assertIn("unmapped_spend_pct", text)
        self.assertIn("spend_source", text)
        self.assertIn("data_freshness", text)
        self.assertIn("portal-attribution-footer", text)

    def test_performance_panel_exposes_unmapped_kpi_and_footer(self) -> None:
        text = _read("services/portal-web/src/components/PerformancePanel.tsx")
        self.assertIn("PortalAttributionFooter", text)
        self.assertIn("unmapped_spend_pct", text)

    def test_portal_api_types_include_attribution_fields(self) -> None:
        text = _read("services/portal-web/src/lib/api.ts")
        for field in (
            "attribution_model",
            "unmapped_spend_pct",
            "spend_source",
            "data_freshness",
            "hub_mapped",
            "cpl_delta_vnd",
            "cpl_delta_pct",
            "target_cpl_vnd",
        ):
            self.assertIn(field, text, msg=f"missing {field}")

    def test_nest_performance_e2e_asserts_cpl_delta(self) -> None:
        text = _read("services/ptt-crm-api/test/performance.e2e-spec.ts")
        self.assertIn("cpl_delta_vnd", text)
        self.assertIn("cpl_delta_pct", text)
        self.assertIn("attribution_model", text)

    def test_nest_facebook_hub_b8_e2e_exists(self) -> None:
        path = ROOT / "services/ptt-crm-api/test/facebook-hub-b8.e2e-spec.ts"
        self.assertTrue(path.is_file(), msg="facebook-hub-b8.e2e-spec.ts missing")
        text = path.read_text(encoding="utf-8")
        self.assertIn("attribution_model", text)
        self.assertIn("cpl_delta_vnd", text)

    def test_portal_b8_playwright_spec_exists(self) -> None:
        path = ROOT / "services/portal-web/e2e/portal-b8.spec.ts"
        self.assertTrue(path.is_file(), msg="portal-b8.spec.ts missing")
        text = path.read_text(encoding="utf-8")
        self.assertRegex(text, r"CPL\s*Δ|CPL Δ")
        self.assertIn("last_touch_crm", text)

    def test_pg_seed_includes_hub_map_for_cpl_delta(self) -> None:
        text = _read("services/ptt-crm-api/test/pg-contract-seed.ts")
        self.assertIn("hub_campaign_map", text)
        self.assertIn("target_cpl_vnd", text)
        self.assertIn("hub_campaign_map_id", text)

    def test_meta_attribution_util_spec_exists(self) -> None:
        path = ROOT / "services/ptt-crm-api/src/meta-attribution.util.spec.ts"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("last_touch_crm", text)


if __name__ == "__main__":
    unittest.main()
