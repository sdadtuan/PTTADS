"""Unit tests for B12 creative registry."""
from __future__ import annotations

import os
import unittest


class TestCreativeRegistry(unittest.TestCase):
    def test_validate_requires_fields(self) -> None:
        from ptt_meta.creative_registry import validate_link_payload

        _, errors = validate_link_payload({})
        self.assertIn("client_id_required", errors)
        self.assertIn("creative_submission_id_required", errors)
        self.assertIn("external_ad_id_required", errors)

    def test_validate_rejects_unapproved_creative(self) -> None:
        from ptt_meta.creative_registry import validate_link_payload

        _, errors = validate_link_payload(
            {
                "client_id": "c1",
                "creative_submission_id": "cr1",
                "external_ad_id": "ad1",
                "creative_status": "pending_client",
            }
        )
        self.assertIn("creative_not_approved", errors)

    def test_validate_client_mismatch(self) -> None:
        from ptt_meta.creative_registry import validate_link_payload

        _, errors = validate_link_payload(
            {
                "client_id": "c1",
                "creative_submission_id": "cr1",
                "external_ad_id": "ad1",
                "creative_client_id": "c2",
                "creative_status": "approved",
            }
        )
        self.assertIn("creative_client_mismatch", errors)

    def test_stub_upsert_when_disabled(self) -> None:
        from ptt_meta.creative_registry import upsert_ad_creative_link

        old = os.environ.get("PTT_META_CREATIVE_REGISTRY_ENABLED")
        os.environ["PTT_META_CREATIVE_REGISTRY_ENABLED"] = "0"
        try:
            out = upsert_ad_creative_link(
                payload={
                    "client_id": "c1",
                    "creative_submission_id": "cr1",
                    "external_ad_id": "ad1",
                    "creative_status": "approved",
                },
                stub=True,
            )
        finally:
            if old is None:
                os.environ.pop("PTT_META_CREATIVE_REGISTRY_ENABLED", None)
            else:
                os.environ["PTT_META_CREATIVE_REGISTRY_ENABLED"] = old
        self.assertTrue(out["ok"])
        self.assertTrue(out["stub"])
        self.assertEqual(out["link"]["external_ad_id"], "ad1")

    def test_list_filters_default_active(self) -> None:
        from ptt_meta.creative_registry import list_links_filters

        out = list_links_filters({"client_id": "abc", "limit": "9999"})
        self.assertEqual(out["client_id"], "abc")
        self.assertTrue(out["active_only"])
        self.assertEqual(out["limit"], 1000)


if __name__ == "__main__":
    unittest.main()
