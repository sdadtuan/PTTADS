"""Tests for Meta conversion rules engine (B9-PY-1)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.conversion_rules import (
    build_conversion_event,
    build_event_id,
    evaluate_conversion_rules,
    load_rules,
    normalize_lead,
    require_meta_attribution_ok,
    summarize_intents,
)


class TestRequireMetaAttribution(unittest.TestCase):
    def test_external_lead_id_passes(self) -> None:
        self.assertTrue(
            require_meta_attribution_ok(
                {"id": 1, "external_lead_id": "fb-123", "agency_client_id": "c1"},
            )
        )

    def test_utm_campaign_passes(self) -> None:
        self.assertTrue(
            require_meta_attribution_ok(
                {
                    "id": 2,
                    "agency_client_id": "c1",
                    "meta_json": {"utm_campaign": "summer_meta"},
                }
            )
        )

    def test_missing_attribution_fails(self) -> None:
        self.assertFalse(
            require_meta_attribution_ok(
                {"id": 3, "agency_client_id": "c1", "meta_json": {}, "source": "walk-in"},
            )
        )


class TestBuildEventId(unittest.TestCase):
    def test_qualified_event_id(self) -> None:
        eid = build_event_id(
            event_name="CompleteRegistration",
            lead={
                "id": 42,
                "status": "qualified",
                "agency_client_id": "c1",
                "status_entered_at": "2026-07-24T05:00:00+00:00",
            },
        )
        self.assertTrue(eid.startswith("crm_qualify_42_"))

    def test_purchase_event_id_with_deal(self) -> None:
        eid = build_event_id(
            event_name="Purchase",
            lead={
                "id": 7,
                "status": "post_sale",
                "agency_client_id": "c1",
                "meta_json": {"deal_id": "deal-99"},
            },
        )
        self.assertEqual(eid, "crm_purchase_7_deal-99")

    def test_leadgen_for_webhook_lead(self) -> None:
        eid = build_event_id(
            event_name="Lead",
            lead={"id": 1, "external_lead_id": "1234567890", "agency_client_id": "c1"},
        )
        self.assertEqual(eid, "leadgen_1234567890")

    def test_manual_retry(self) -> None:
        eid = build_event_id(
            event_name="CompleteRegistration",
            lead={"id": 5, "agency_client_id": "c1"},
            manual_uuid="abc-uuid",
        )
        self.assertEqual(eid, "manual_5_abc-uuid")


class TestBuildConversionEvent(unittest.TestCase):
    def test_complete_registration_payload(self) -> None:
        rule = {
            "id": "rule-1",
            "client_id": None,
            "lead_status": "qualified",
            "event_name": "CompleteRegistration",
            "enabled": True,
            "require_meta_attribution": True,
            "value_vnd": 0,
            "notes": "",
        }
        event = build_conversion_event(
            {
                "id": 10,
                "email": "lead@test.com",
                "phone": "0901234567",
                "status": "qualified",
                "agency_client_id": "550e8400-e29b-41d4-a716-446655440000",
                "external_lead_id": "fb-1",
                "status_entered_at": 1720000000,
            },
            rule,
        )
        self.assertEqual(event["event_name"], "CompleteRegistration")
        self.assertIn("em", event["user_data"])
        self.assertIn("ph", event["user_data"])
        self.assertTrue(str(event["event_id"]).startswith("crm_qualify_10_"))

    def test_purchase_includes_value(self) -> None:
        rule = {
            "id": "rule-2",
            "client_id": None,
            "lead_status": "post_sale",
            "event_name": "Purchase",
            "enabled": True,
            "require_meta_attribution": False,
            "value_vnd": 5000000,
            "notes": "",
        }
        event = build_conversion_event(
            {"id": 3, "status": "post_sale", "agency_client_id": "c1", "meta_json": {}},
            rule,
        )
        self.assertEqual(event["event_name"], "Purchase")
        self.assertEqual(event["custom_data"]["value"], 5000000.0)
        self.assertEqual(event["custom_data"]["currency"], "VND")


class TestLoadRulesMerge(unittest.TestCase):
    @patch("ptt_meta.conversion_rules.pg_meta_conversion_rules_ready", return_value=True)
    @patch("ptt_meta.conversion_rules.pg_connection")
    def test_client_rule_overrides_global(self, mock_pg: MagicMock, _ready: MagicMock) -> None:
        cur = MagicMock()
        cur.description = [
            ("id",),
            ("client_id",),
            ("lead_status",),
            ("event_name",),
            ("enabled",),
            ("require_meta_attribution",),
            ("value_vnd",),
            ("notes",),
        ]
        cur.fetchall.return_value = [
            ("g1", None, "qualified", "CompleteRegistration", True, True, 0, "global"),
            (
                "c1",
                "550e8400-e29b-41d4-a716-446655440000",
                "qualified",
                "CompleteRegistration",
                False,
                True,
                0,
                "client override",
            ),
        ]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        rules = load_rules("550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "c1")
        self.assertFalse(rules[0]["enabled"])


class TestEvaluateConversionRules(unittest.TestCase):
    def _qualified_rule(self, *, enabled: bool = True, require_attr: bool = True) -> dict:
        return {
            "id": "rule-q",
            "client_id": None,
            "lead_status": "qualified",
            "event_name": "CompleteRegistration",
            "enabled": enabled,
            "require_meta_attribution": require_attr,
            "value_vnd": 0,
            "notes": "",
        }

    def test_no_op_when_status_unchanged(self) -> None:
        intents = evaluate_conversion_rules(
            {"id": 1, "agency_client_id": "c1", "status": "qualified"},
            "qualified",
            "qualified",
            rules=[self._qualified_rule()],
        )
        self.assertEqual(intents, [])

    def test_dispatch_on_status_transition(self) -> None:
        intents = evaluate_conversion_rules(
            {
                "id": 1,
                "agency_client_id": "c1",
                "status": "qualified",
                "external_lead_id": "fb-99",
                "email": "a@b.com",
            },
            "new",
            "qualified",
            rules=[self._qualified_rule()],
        )
        self.assertEqual(len(intents), 1)
        self.assertFalse(intents[0].get("skipped"))
        self.assertEqual(intents[0]["event_name"], "CompleteRegistration")
        self.assertIn("event", intents[0])

    def test_skip_when_attribution_required(self) -> None:
        intents = evaluate_conversion_rules(
            {"id": 2, "agency_client_id": "c1", "status": "qualified", "meta_json": {}},
            "new",
            "qualified",
            rules=[self._qualified_rule(require_attr=True)],
        )
        self.assertEqual(len(intents), 1)
        self.assertTrue(intents[0].get("skipped"))
        self.assertEqual(intents[0].get("reason"), "attribution_required")

    def test_skip_disabled_rule(self) -> None:
        intents = evaluate_conversion_rules(
            {"id": 3, "agency_client_id": "c1", "status": "qualified", "external_lead_id": "x"},
            "new",
            "qualified",
            rules=[self._qualified_rule(enabled=False)],
        )
        self.assertTrue(intents[0].get("skipped"))
        self.assertEqual(intents[0].get("reason"), "rule_disabled")

    def test_summarize_intents(self) -> None:
        summary = summarize_intents(
            [
                {"ok": True, "skipped": False, "event_name": "CompleteRegistration"},
                {"ok": True, "skipped": True, "reason": "rule_disabled", "event_name": "Lead"},
            ]
        )
        self.assertEqual(summary["dispatch_count"], 1)
        self.assertEqual(summary["skipped_count"], 1)


class TestNormalizeLead(unittest.TestCase):
    def test_pg_shape(self) -> None:
        norm = normalize_lead(
            {
                "sqlite_lead_id": 99,
                "agency_client_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "New",
                "meta_json": {"facebook_leadgen_id": "lg-1", "utm_source": "facebook"},
            }
        )
        self.assertEqual(norm["id"], 99)
        self.assertEqual(norm["status"], "new")
        self.assertEqual(norm["external_lead_id"], "lg-1")


if __name__ == "__main__":
    unittest.main()
