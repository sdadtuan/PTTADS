"""Unit tests for B15 Meta Ads Ops helpers."""
from __future__ import annotations

import os
import unittest


class TestAdsOps(unittest.TestCase):
    def test_list_launch_templates(self) -> None:
        from ptt_meta.ads_ops import get_launch_template, list_launch_templates

        templates = list_launch_templates()
        self.assertGreaterEqual(len(templates), 2)
        tpl = get_launch_template("re_lead_default")
        self.assertIsNotNone(tpl)
        assert tpl is not None
        self.assertEqual(tpl["objective"], "OUTCOME_LEADS")

    def test_validate_launch_payload(self) -> None:
        from ptt_meta.ads_ops import build_create_campaign_payload, validate_launch_payload

        payload = build_create_campaign_payload(
            client_id="c1",
            external_account_id="act_1",
            template_id="re_lead_default",
            campaign_name="Camp",
            adset_name="Adset",
            ad_name="Ad",
            daily_budget_vnd=500_000,
            creative_submission_id="cr-1",
        )
        self.assertEqual(payload["action"], "create_campaign")
        self.assertEqual(validate_launch_payload(payload), [])

        bad = dict(payload)
        bad["daily_budget_vnd"] = 0
        self.assertIn("daily_budget_vnd_invalid", validate_launch_payload(bad))

    def test_pilot_allowlist(self) -> None:
        from ptt_meta.ads_ops import check_ads_ops_pilot

        old = os.environ.get("PTT_META_ADS_OPS_ENABLED")
        old_pilot = os.environ.get("PTT_META_ADS_OPS_PILOT_CLIENTS")
        os.environ["PTT_META_ADS_OPS_ENABLED"] = "1"
        os.environ["PTT_META_ADS_OPS_PILOT_CLIENTS"] = "client-a,client-b"
        try:
            self.assertTrue(check_ads_ops_pilot("client-a")["allowed"])
            self.assertFalse(check_ads_ops_pilot("other")["allowed"])
        finally:
            if old is None:
                os.environ.pop("PTT_META_ADS_OPS_ENABLED", None)
            else:
                os.environ["PTT_META_ADS_OPS_ENABLED"] = old
            if old_pilot is None:
                os.environ.pop("PTT_META_ADS_OPS_PILOT_CLIENTS", None)
            else:
                os.environ["PTT_META_ADS_OPS_PILOT_CLIENTS"] = old_pilot

    def test_edit_diff_and_validation(self) -> None:
        from ptt_meta.ads_edit import build_edit_diff, build_edit_snapshot, validate_edit_submit

        snap = build_edit_snapshot(client_id="c1", external_ad_id="ad_123")
        diff = build_edit_diff(
            old_value={"headline": snap["headline"]},
            new_value={"headline": "Updated"},
        )
        self.assertEqual(diff["change_count"], 1)

        errors = validate_edit_submit(
            action="update_ad_copy",
            client_id="c1",
            external_ad_id="ad_123",
            new_value={"headline": "H", "primary_text": "P"},
            effective_status="DISAPPROVED",
            disapproved_ack=False,
        )
        self.assertIn("disapproved_ack_required", errors)

    def test_creative_upload_stub(self) -> None:
        from ptt_meta.creative_upload import upload_creative_link, validate_upload_payload

        self.assertEqual(validate_upload_payload({}), ["client_id_required", "creative_submission_id_required"])
        out = upload_creative_link(
            client_id="c1",
            creative_submission_id="00000000-0000-0000-0000-000000000099",
            stub=True,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["stub"])
        self.assertIn("external_creative_id", out)


if __name__ == "__main__":
    unittest.main()
