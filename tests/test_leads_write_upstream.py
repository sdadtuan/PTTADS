"""Tests for leads write upstream / assign proxy (Phase 2 W6)."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch


class TestLeadsWriteUpstreamConfig(unittest.TestCase):
    def test_default_flask(self) -> None:
        from ptt_crm.config import leads_write_upstream

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_LEADS_WRITE_UPSTREAM", None)
            self.assertEqual(leads_write_upstream(), "flask")

    def test_nest_mode(self) -> None:
        from ptt_crm.config import leads_write_upstream

        with patch.dict(os.environ, {"PTT_LEADS_WRITE_UPSTREAM": "nest"}):
            self.assertEqual(leads_write_upstream(), "nest")


class TestProxyAssignLead(unittest.TestCase):
    @patch("ptt_crm.leads_write_upstream._mirror_sqlite_assign_audit")
    @patch("ptt_crm.leads_write_upstream._sync_sqlite_after_nest_assign")
    @patch("ptt_crm.leads_write_upstream._validate_assign")
    @patch("ptt_crm.leads_write_upstream.request_nest_json")
    def test_proxy_assign_success(
        self,
        mock_patch: MagicMock,
        mock_validate: MagicMock,
        mock_sync: MagicMock,
        mock_mirror: MagicMock,
    ) -> None:
        from ptt_crm.leads_write_upstream import proxy_assign_lead

        mock_validate.return_value = (MagicMock(), None)
        mock_patch.return_value = (200, {"id": 1, "owner_id": 2}, None)
        mock_mirror.return_value = {"id": 1, "owner_id": 2, "full_name": "Lead A"}

        body, status = proxy_assign_lead(
            1,
            to_user_id=2,
            reason="Chuyển CSKH",
            assigned_by="admin",
            ts="2026-07-17 10:00:00",
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["lead"]["owner_id"], 2)
        self.assertEqual(body["upstream"], "nest")
        mock_patch.assert_called_once()
        mock_sync.assert_called_once()
        mock_mirror.assert_called_once()

    @patch("ptt_crm.leads_write_upstream._validate_assign")
    @patch("ptt_crm.leads_write_upstream.request_nest_json")
    def test_proxy_assign_nest_error(self, mock_patch: MagicMock, mock_validate: MagicMock) -> None:
        from ptt_crm.leads_write_upstream import proxy_assign_lead

        mock_validate.return_value = (MagicMock(), None)
        mock_patch.return_value = (404, {"error": "Not found"}, None)

        body, status = proxy_assign_lead(
            1,
            to_user_id=2,
            reason="test",
            assigned_by="admin",
            ts="2026-07-17",
        )
        self.assertEqual(status, 404)

    @patch("ptt_crm.leads_write_upstream._validate_assign")
    def test_proxy_assign_validation_error(self, mock_validate: MagicMock) -> None:
        from ptt_crm.leads_write_upstream import proxy_assign_lead

        mock_validate.side_effect = ValueError("Nhân viên không hợp lệ hoặc đã ngưng.")
        body, status = proxy_assign_lead(
            1,
            to_user_id=99,
            reason="test",
            assigned_by="admin",
            ts="2026-07-17",
        )
        self.assertEqual(status, 400)
        self.assertIn("error", body)


class TestAssignEndpointRouting(unittest.TestCase):
    @patch("app._admin_logged_in", return_value=True)
    @patch("app._admin_section_can", return_value=True)
    @patch("app._crm_effective_staff_id", return_value=None)
    @patch("ptt_crm.leads_write_upstream.proxy_assign_lead")
    @patch("ptt_crm.leads_write_upstream.nest_write_upstream_enabled", return_value=True)
    def test_assign_proxies_when_nest(
        self,
        _enabled: MagicMock,
        mock_proxy: MagicMock,
        _staff: MagicMock,
        _can: MagicMock,
        _auth: MagicMock,
    ) -> None:
        from app import app

        mock_proxy.return_value = ({"lead": {"id": 1, "owner_id": 2}, "upstream": "nest"}, 200)
        client = app.test_client()
        resp = client.post(
            "/api/crm/leads/1/assign",
            data=json.dumps({"to_user_id": 2, "reason": "test reason here"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        mock_proxy.assert_called_once()
        self.assertEqual(resp.get_json()["upstream"], "nest")

    @patch("app._admin_logged_in", return_value=True)
    @patch("app._admin_section_can", return_value=True)
    @patch("app._crm_effective_staff_id", return_value=None)
    @patch("crm_lead_store.assign_lead")
    @patch("crm_lead_store.lead_row_to_dict", return_value={"id": 1, "owner_id": 2})
    @patch("ptt_crm.leads_write_upstream.nest_write_upstream_enabled", return_value=False)
    def test_assign_local_when_flask(
        self,
        _enabled: MagicMock,
        _dict: MagicMock,
        mock_assign: MagicMock,
        _staff: MagicMock,
        _can: MagicMock,
        _auth: MagicMock,
    ) -> None:
        from app import app

        mock_assign.return_value = {"id": 1}
        client = app.test_client()
        resp = client.post(
            "/api/crm/leads/1/assign",
            data=json.dumps({"to_user_id": 2, "reason": "local assign reason"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        mock_assign.assert_called_once()


if __name__ == "__main__":
    unittest.main()
