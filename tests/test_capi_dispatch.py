"""Tests for Meta CAPI dispatch M5."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.capi_dispatch import (
    build_lead_event,
    capi_stats,
    client_allowed_for_capi,
    dispatch_lead_capi,
    hash_email,
    hash_phone,
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
    def test_build_lead_event_id(self) -> None:
        evt = build_lead_event(lead_id=99, client_id="c-uuid", email="a@b.com")
        self.assertEqual(evt["event_name"], "Lead")
        self.assertEqual(evt["event_id"], "ptt-lead-c-uuid-99")
        self.assertIn("em", evt["user_data"])


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


if __name__ == "__main__":
    unittest.main()
