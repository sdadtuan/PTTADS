"""Tests for Meta CAPI dispatch M5."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.capi_dispatch import (
    build_lead_event,
    capi_stats,
    client_allowed_for_capi,
    dispatch_conversion_capi,
    dispatch_conversion_intent,
    dispatch_lead_capi,
    find_capi_log_dedup,
    flush_pending_capi,
    hash_email,
    hash_phone,
    lead_event_id,
    legacy_lead_event_ids,
    process_capi_dispatch_payload,
)


class TestCapiHashing(unittest.TestCase):
    def test_hash_email_normalized(self) -> None:
        h1 = hash_email("  Test@Example.COM ")
        h2 = hash_email("test@example.com")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1 or ""), 64)

    def test_hash_phone_vn(self) -> None:
        h = hash_phone("0901234567")
        self.assertIsNotNone(h)
        self.assertEqual(len(h or ""), 64)


class TestCapiEvent(unittest.TestCase):
    def test_build_lead_event_id_legacy(self) -> None:
        evt = build_lead_event(lead_id=99, client_id="c-uuid", email="a@b.com")
        self.assertEqual(evt["event_name"], "Lead")
        self.assertEqual(evt["event_id"], "ptt-lead-c-uuid-99")
        self.assertIn("em", evt["user_data"])

    def test_build_lead_event_id_leadgen(self) -> None:
        evt = build_lead_event(
            lead_id=99,
            client_id="c-uuid",
            external_id="fb-lead-123",
            email="a@b.com",
        )
        self.assertEqual(evt["event_id"], "leadgen_fb-lead-123")

    def test_lead_event_id_helpers(self) -> None:
        self.assertEqual(
            lead_event_id(lead_id=1, client_id="c1", external_id="fb-9"),
            "leadgen_fb-9",
        )
        self.assertEqual(legacy_lead_event_ids(lead_id=1, client_id="c1", external_id="fb-9"), ["ptt-lead-c1-1"])


class TestCapiDedupe(unittest.TestCase):
    @patch("ptt_meta.capi_dispatch.find_capi_log")
    def test_find_dedup_checks_legacy(self, mock_find: MagicMock) -> None:
        mock_find.side_effect = [None, {"id": "log-old", "status": "sent"}]
        out = find_capi_log_dedup(
            "c1",
            "Lead",
            "leadgen_fb-1",
            legacy_event_ids=["ptt-lead-c1-1"],
        )
        self.assertEqual(out["id"], "log-old")
        self.assertEqual(mock_find.call_count, 2)


class TestCapiPilot(unittest.TestCase):
    def test_pilot_allowlist(self) -> None:
        with patch.dict(os.environ, {"PTT_CAPI_PILOT_CLIENTS": "abc-123"}, clear=False):
            self.assertTrue(client_allowed_for_capi("abc-123"))
            self.assertFalse(client_allowed_for_capi("other"))


class TestCapiDispatch(unittest.TestCase):
    @patch("ptt_meta.capi_dispatch.update_capi_log")
    @patch("ptt_meta.capi_dispatch.insert_capi_log", return_value="log-1")
    @patch("ptt_meta.capi_dispatch.find_capi_log", return_value=None)
    @patch("ptt_meta.capi_dispatch.load_sqlite_lead")
    @patch("ptt_meta.capi_dispatch.resolve_capi_config")
    @patch("ptt_meta.capi_dispatch.pg_capi_ready", return_value=True)
    def test_stub_dispatch(
        self,
        _ready: MagicMock,
        mock_cfg: MagicMock,
        mock_lead: MagicMock,
        _find: MagicMock,
        _insert: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        mock_cfg.return_value = {"pixel_id": "123", "access_token": "tok"}
        mock_lead.return_value = {"email": "lead@test.com", "phone": "0901111222"}

        with patch.dict(os.environ, {"PTT_CAPI_ENABLED": "1", "PTT_CAPI_STUB": "1"}, clear=False):
            out = dispatch_lead_capi(lead_id=1, client_id="550e8400-e29b-41d4-a716-446655440000")

        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("stub"))
        mock_update.assert_called_once()

    @patch("ptt_meta.capi_dispatch.dispatch_lead_capi")
    def test_process_payload(self, mock_dispatch: MagicMock) -> None:
        mock_dispatch.return_value = {"ok": True}
        out = process_capi_dispatch_payload({"lead_id": 5, "client_id": "c1"})
        self.assertTrue(out.get("ok"))
        mock_dispatch.assert_called_once()

    @patch("ptt_meta.capi_dispatch.dispatch_conversion_capi")
    def test_process_payload_conversion_event(self, mock_conv: MagicMock) -> None:
        mock_conv.return_value = {"ok": True}
        out = process_capi_dispatch_payload(
            {
                "client_id": "c1",
                "lead_id": 9,
                "event": {"event_name": "CompleteRegistration", "event_id": "crm_qualify_9_1"},
            }
        )
        self.assertTrue(out.get("ok"))
        mock_conv.assert_called_once()

    @patch("ptt_meta.capi_dispatch._dispatch_capi_event")
    @patch("ptt_meta.capi_dispatch.replay_capi_event_from_log")
    @patch("ptt_meta.capi_dispatch.get_capi_log_row")
    def test_process_payload_capi_log_replay(
        self,
        mock_get: MagicMock,
        mock_replay: MagicMock,
        mock_send: MagicMock,
    ) -> None:
        mock_get.return_value = {
            "id": "log-1",
            "client_id": "c1",
            "event_name": "Lead",
            "event_id": "lead-1",
            "lead_id": 5,
            "status": "failed",
        }
        mock_replay.return_value = {"event_name": "Lead", "event_id": "lead-1"}
        mock_send.return_value = {"ok": True}
        out = process_capi_dispatch_payload({"capi_log_id": "log-1", "client_id": "c1"})
        self.assertTrue(out.get("ok"))
        mock_get.assert_called_once_with("log-1")
        mock_replay.assert_called_once()
        mock_send.assert_called_once()


class TestConversionDispatch(unittest.TestCase):
    @patch("ptt_meta.capi_dispatch._dispatch_capi_event")
    def test_dispatch_conversion_capi(self, mock_send: MagicMock) -> None:
        mock_send.return_value = {"ok": True}
        event = {"event_name": "CompleteRegistration", "event_id": "crm_qualify_1_ts"}
        out = dispatch_conversion_capi(client_id="c1", event=event, lead_id=1)
        self.assertTrue(out.get("ok"))
        mock_send.assert_called_once()

    @patch("ptt_meta.capi_dispatch.dispatch_conversion_capi")
    def test_dispatch_conversion_intent_skipped(self, mock_conv: MagicMock) -> None:
        out = dispatch_conversion_intent({"skipped": True, "reason": "rule_disabled"})
        self.assertTrue(out.get("skipped"))
        mock_conv.assert_not_called()

    @patch("ptt_meta.capi_dispatch.dispatch_conversion_capi")
    def test_dispatch_conversion_intent_sends(self, mock_conv: MagicMock) -> None:
        mock_conv.return_value = {"ok": True}
        out = dispatch_conversion_intent(
            {
                "client_id": "c1",
                "lead_id": 2,
                "event": {"event_name": "Purchase", "event_id": "crm_purchase_2_x"},
            }
        )
        self.assertTrue(out.get("ok"))
        mock_conv.assert_called_once()


class TestCapiFlush(unittest.TestCase):
    @patch("ptt_meta.capi_dispatch._dispatch_capi_event")
    @patch("ptt_meta.capi_dispatch.replay_capi_event_from_log")
    @patch("ptt_meta.capi_dispatch.list_flushable_capi_logs")
    @patch("ptt_meta.capi_dispatch.capi_dispatch_enabled", return_value=True)
    @patch("ptt_meta.capi_dispatch.capi_stub_mode", return_value=True)
    def test_flush_pending_replays_rows(
        self,
        _stub: MagicMock,
        _enabled: MagicMock,
        mock_list: MagicMock,
        mock_replay: MagicMock,
        mock_send: MagicMock,
    ) -> None:
        mock_list.return_value = [
            {
                "id": "log-1",
                "client_id": "c1",
                "event_name": "Lead",
                "event_id": "leadgen_x",
                "lead_id": 1,
                "status": "failed",
            }
        ]
        mock_replay.return_value = {"event_name": "Lead", "event_id": "leadgen_x"}
        mock_send.return_value = {"ok": True, "stub": True}
        out = flush_pending_capi(client_id="c1", limit=10)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("processed"), 1)
        mock_send.assert_called_once()


class TestCapiHandler(unittest.TestCase):
    @patch("ptt_jobs.handlers.capi_dispatch.process_capi_dispatch_payload")
    @patch("ptt_jobs.handlers.capi_dispatch.mark_job_done")
    def test_handler_done(self, mock_done: MagicMock, mock_proc: MagicMock) -> None:
        from ptt_jobs.handlers.capi_dispatch import run_capi_dispatch_job

        mock_proc.return_value = {"ok": True, "skipped": True}
        run_capi_dispatch_job({"id": "j1", "payload": {"lead_id": 1, "client_id": "c1"}, "attempts": 1, "max_attempts": 3})
        mock_done.assert_called_once_with("j1")


class TestCapiStats(unittest.TestCase):
    @patch("ptt_meta.capi_dispatch.pg_capi_ready", return_value=False)
    def test_stats_not_ready(self, _mock: MagicMock) -> None:
        self.assertFalse(capi_stats().get("ok"))

    @patch("ptt_meta.capi_dispatch.pg_connection")
    @patch("ptt_meta.capi_dispatch.pg_capi_ready", return_value=True)
    def test_stats_7d_window_fields(self, _ready: MagicMock, mock_pg: MagicMock) -> None:
        cur = MagicMock()
        cur.fetchall.return_value = [("sent", 8), ("failed", 2), ("pending", 1)]
        cur.fetchone.return_value = (150.5,)
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        out = capi_stats(hours=168)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("hours"), 168)
        self.assertEqual(out.get("window_days"), 7.0)
        self.assertEqual(out.get("sent"), 8)
        self.assertEqual(out.get("pending"), 1)
        self.assertEqual(out.get("fail_rate_pct"), 20.0)
        self.assertEqual(out.get("avg_latency_ms"), 150.5)


if __name__ == "__main__":
    unittest.main()
