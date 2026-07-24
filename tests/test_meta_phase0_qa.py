"""Wave Meta Phase 0 — hub refactor static QA checks."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestMetaPhase0Qa(unittest.TestCase):
    def test_lib_meta_foundation_files(self) -> None:
        for rel in (
            "services/ops-web/src/lib/meta/types.ts",
            "services/ops-web/src/lib/meta/format.ts",
            "services/ops-web/src/lib/meta/caps.ts",
            "services/ops-web/src/lib/meta/routes.ts",
        ):
            self.assertTrue((ROOT / rel).is_file(), msg=f"{rel} missing")
        caps = _read("services/ops-web/src/lib/meta/caps.ts")
        self.assertIn("canViewMetaHub", caps)
        self.assertIn("canConfigureMeta", caps)
        fmt = _read("services/ops-web/src/lib/meta/format.ts")
        self.assertIn("fmtVnd", fmt)
        self.assertIn("yesterdayIso", fmt)

    def test_core_meta_components_exist(self) -> None:
        for rel in (
            "services/ops-web/src/components/meta/MetaBadge.tsx",
            "services/ops-web/src/components/meta/MetaPageShell.tsx",
            "services/ops-web/src/components/meta/MetaHubFilters.tsx",
            "services/ops-web/src/components/meta/MetaHubKpiGrid.tsx",
            "services/ops-web/src/components/meta/MetaClientTable.tsx",
            "services/ops-web/src/components/meta/MetaHubAlertsList.tsx",
        ):
            self.assertTrue((ROOT / rel).is_file(), msg=f"{rel} missing")

    def test_meta_badge_uses_css_variants(self) -> None:
        badge = _read("services/ops-web/src/components/meta/MetaBadge.tsx")
        self.assertIn("meta-badge--ok", badge)
        css = _read("services/ops-web/src/app/globals.css")
        self.assertIn(".meta-badge--ok", css)
        self.assertIn(".summary-grid", css)

    def test_use_meta_hub_hook(self) -> None:
        hub = _read("services/ops-web/src/hooks/meta/useMetaHub.ts")
        auth = _read("services/ops-web/src/hooks/meta/useMetaHubAuth.ts")
        self.assertIn("fetchFacebookHub", hub)
        self.assertIn("downloadFacebookHubExport", hub)
        self.assertIn("syncUrl", hub)
        self.assertIn("useMetaHubAuth", hub)
        self.assertIn("canViewMetaHub", auth)
        self.assertIn("staffMe", auth)

    def test_hub_page_is_shell_composition(self) -> None:
        text = _read("services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx")
        self.assertIn("MetaPageShell", text)
        self.assertIn("MetaHubFilters", text)
        self.assertIn("MetaHubKpiGrid", text)
        self.assertIn("MetaHubAlertsList", text)
        self.assertIn("MetaHubTabPanels", text)
        self.assertIn("useMetaHub", text)
        self.assertNotIn("fetchFacebookHub", text)
        self.assertLessEqual(len(text.splitlines()), 150)

    def test_meta_hub_kpi_grid_structure(self) -> None:
        text = _read("services/ops-web/src/components/meta/MetaHubKpiGrid.tsx")
        self.assertIn('className="summary-grid"', text)
        self.assertIn("summary-card", text)

    def test_meta_hub_alerts_list_uses_ops_web_link(self) -> None:
        text = _read("services/ops-web/src/components/meta/MetaHubAlertsList.tsx")
        self.assertIn("opsWebLink", text)

    def test_portal_css_and_table_contract(self) -> None:
        css = _read("services/portal-web/src/app/globals.css")
        table = _read("services/portal-web/src/components/PerformanceTable.tsx")
        self.assertIn(".channel-badge", css)
        self.assertIn(".over-target", css)
        self.assertIn("channel-badge", table)
        self.assertRegex(table, r"over-target")

    def test_phase0_gate_scripts_exist(self) -> None:
        for rel in (
            "ptt_crm/wave_meta_phase0_gates.py",
            "scripts/wave_meta_phase0_gate.sh",
        ):
            self.assertTrue((ROOT / rel).is_file(), msg=f"{rel} missing")


if __name__ == "__main__":
    unittest.main()
