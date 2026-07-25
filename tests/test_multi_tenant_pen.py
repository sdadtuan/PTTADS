"""PROD-H-PEN — multi-tenant isolation checks (Prod-S4)."""
from __future__ import annotations

import unittest


class TestMultiTenantPenMatrix(unittest.TestCase):
    """Static pen-test matrix — complements Nest e2e client-offboard + portal JWT scope."""

    MATRIX = (
        ("portal_notification_list", "JWT client_id only", "repo.listForUser(clientId)"),
        ("portal_creative_approve", "approver client scope", "creative.client_id match"),
        ("client_offboard", "archived tenant locked", "403 tenant_archived"),
        ("agency_jobs", "client_id on job_queue", "cancel pending on offboard"),
        ("staff_cskh_board", "staff JWT caps", "StaffLeadsViewGuard"),
    )

    def test_pen_matrix_documented(self) -> None:
        self.assertGreaterEqual(len(self.MATRIX), 5)
        for case_id, control, mechanism in self.MATRIX:
            self.assertTrue(case_id)
            self.assertTrue(control)
            self.assertTrue(mechanism)

    def test_portal_notification_scopes_client_id(self) -> None:
        from ptt_crm.portal_notification_pen import assert_client_scoped

        out = assert_client_scoped(
            user_client_id="550e8400-e29b-41d4-a716-446655440000",
            requested_client_id="660e8400-e29b-41d4-a716-446655440001",
        )
        self.assertFalse(out["allowed"])
        self.assertEqual(out["reason"], "client_mismatch")

    def test_portal_notification_allows_same_client(self) -> None:
        from ptt_crm.portal_notification_pen import assert_client_scoped

        cid = "550e8400-e29b-41d4-a716-446655440000"
        out = assert_client_scoped(user_client_id=cid, requested_client_id=cid)
        self.assertTrue(out["allowed"])


if __name__ == "__main__":
    unittest.main()
