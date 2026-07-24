"""Wave B9 — Meta tracking UI + Launch QA static QA checks."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestB9TrackingQa(unittest.TestCase):
    def test_tracking_page_route_and_content(self) -> None:
        page = _read("services/ops-web/src/app/meta/tracking/page.tsx")
        content = _read("services/ops-web/src/app/meta/tracking/MetaTrackingContent.tsx")
        self.assertIn("MetaTrackingContent", page)
        self.assertIn("MetaTrackingKpiGrid", content)
        self.assertIn("MetaPreflightChecklist", content)
        self.assertIn("MetaCapiEventsTable", content)

    def test_meta_api_tracking_endpoints(self) -> None:
        text = _read("services/ops-web/src/lib/meta/api.ts")
        for path in (
            "/api/v1/meta/tracking/health",
            "/api/v1/meta/capi/events",
            "/api/v1/meta/conversion-rules",
            "test-pixel",
        ):
            self.assertIn(path, text, msg=f"missing {path}")
        self.assertIn("fetchMetaTrackingHealth", text)
        self.assertIn("postMetaTestPixel", text)
        self.assertIn("postMetaCapiRetry", text)

    def test_meta_flags_and_caps(self) -> None:
        flags = _read("services/ops-web/src/lib/meta/flags.ts")
        caps = _read("services/ops-web/src/lib/meta/caps.ts")
        self.assertIn("NEXT_PUBLIC_PTT_META_TRACKING_ENABLED", flags)
        self.assertIn("metaTrackingEnabled", flags)
        self.assertIn("canViewMetaTracking", caps)

    def test_ops_nav_tracking_link(self) -> None:
        text = _read("services/ops-web/src/components/OpsNav.tsx")
        self.assertIn("/meta/tracking", text)
        self.assertIn("Meta Tracking", text)
        self.assertIn("metaTrackingEnabled", text)

    def test_hub_capi_badge_on_facebook_ads(self) -> None:
        hub = _read("services/ops-web/src/hooks/meta/useMetaHub.ts")
        table = _read("services/ops-web/src/components/meta/MetaClientTable.tsx")
        self.assertIn("fetchMetaTrackingHealth", hub)
        self.assertIn("MetaBadge", table)
        self.assertIn("capiBadgeFromAccount", table)

    def test_launch_qa_meta_util_items(self) -> None:
        text = _read("services/ptt-crm-api/src/meta-tracking/launch-qa-meta.util.ts")
        for key in (
            "meta_pixel_configured",
            "meta_capi_test_ok",
            "meta_hub_map_coverage",
            "meta_capi_recent_sent",
        ):
            self.assertIn(key, text)

    def test_launch_qa_meta_bridge_wired(self) -> None:
        bridge = _read("services/ptt-crm-api/src/launch-qa/launch-qa-meta-bridge.service.ts")
        lifecycle = _read("services/ptt-crm-api/src/service-lifecycle/lifecycle-launch-qa.service.ts")
        self.assertIn("evaluateMetaLaunchQaItems", bridge)
        self.assertIn("LaunchQaMetaBridgeService", lifecycle)
        self.assertIn("meta_checklist_auto_only", lifecycle)

    def test_nest_meta_tracking_b9_e2e_exists(self) -> None:
        path = ROOT / "services/ptt-crm-api/test/meta-tracking-b9.e2e-spec.ts"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("/api/v1/meta/tracking/health", text)
        self.assertIn("test-pixel", text)
        self.assertIn("conversion-rules", text)

    def test_playwright_meta_tracking_spec(self) -> None:
        path = ROOT / "services/ops-web/e2e/meta-tracking.spec.ts"
        self.assertTrue(path.is_file(), msg="meta-tracking.spec.ts missing")
        text = path.read_text(encoding="utf-8")
        self.assertIn("/meta/tracking", text)
        self.assertTrue(re.search(r"test pixel", text, re.I), msg="missing Test pixel scenario")

    def test_wave_b9_gate_scripts_exist(self) -> None:
        for rel in (
            "ptt_crm/wave_b9_gates.py",
            "scripts/wave_b9_gate.sh",
            "scripts/wave_b9_smoke.sh",
            "scripts/playwright_ops_meta_tracking_e2e.sh",
            "docs/runbooks/b9-tracking-pilot-soak.md",
        ):
            self.assertTrue((ROOT / rel).is_file(), msg=f"{rel} missing")

    def test_b9_soak_module(self) -> None:
        text = _read("ptt_crm/b9_tracking_soak_evidence.py")
        self.assertIn("capi_fail_rate_pct", text)
        self.assertIn("evaluate_soak_gate", text)
        self.assertIn("DEFAULT_REQUIRED_DAYS = 30", text)


if __name__ == "__main__":
    unittest.main()
