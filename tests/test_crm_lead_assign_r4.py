"""Tests — phân lead round-robin × ngành × dịch vụ (R4)."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_assign_scope import (
    create_staff_assign_scope,
    delete_staff_assign_scope,
    eligible_staff_ids_for_lead,
    ensure_staff_assign_scope_schema,
    lead_assignment_pool_key,
    list_staff_assign_scopes,
)
from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner, config_with_only
from crm_lead_store import assign_lead_owner, create_lead, ensure_lead_schema, lead_row_to_dict
from crm_re_projects import ensure_re_projects_schema


TS = "2026-06-05 10:00:00"


class LeadAssignR4Test(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crm_assignment_state (
                pool_key TEXT PRIMARY KEY,
                last_staff_id INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                sales_level TEXT NOT NULL DEFAULT 'b',
                internal_code TEXT NOT NULL DEFAULT '',
                department_id INTEGER
            );
            """
        )
        self.staff: dict[str, int] = {}
        for name in ("AM Spa FB", "AM Spa FB 2", "AM FnB Google"):
            cur = self.conn.execute(
                "INSERT INTO crm_staff (name, active, sales_level) VALUES (?, 1, 'b')",
                (name,),
            )
            self.staff[name] = int(cur.lastrowid)
        self.conn.execute("DELETE FROM crm_staff_assign_scope")
        create_staff_assign_scope(
            self.conn,
            staff_id=self.staff["AM Spa FB"],
            industry_slug="spa",
            service_slug="quang-cao-facebook",
        )
        create_staff_assign_scope(
            self.conn,
            staff_id=self.staff["AM Spa FB 2"],
            industry_slug="spa",
            service_slug="quang-cao-facebook",
        )
        create_staff_assign_scope(
            self.conn,
            staff_id=self.staff["AM FnB Google"],
            industry_slug="fnb",
            service_slug="quang-cao-google",
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_pool_key_separates_industry_service(self) -> None:
        k1 = lead_assignment_pool_key(industry_slug="spa", service_slug="quang-cao-facebook")
        k2 = lead_assignment_pool_key(industry_slug="fnb", service_slug="quang-cao-google")
        self.assertNotEqual(k1, k2)
        self.assertEqual(k1, "lead_rr:ind:spa:svc:quang-cao-facebook")

    def test_eligible_staff_filters_by_scope(self) -> None:
        spa_fb = eligible_staff_ids_for_lead(
            self.conn, industry_slug="spa", service_slug="quang-cao-facebook"
        )
        self.assertEqual(
            spa_fb,
            frozenset({self.staff["AM Spa FB"], self.staff["AM Spa FB 2"]}),
        )
        fnb_g = eligible_staff_ids_for_lead(
            self.conn, industry_slug="fnb", service_slug="quang-cao-google"
        )
        self.assertEqual(fnb_g, frozenset({self.staff["AM FnB Google"]}))
        none = eligible_staff_ids_for_lead(
            self.conn, industry_slug="bds", service_slug="dich-vu-seo-local"
        )
        self.assertEqual(none, frozenset())

    def test_round_robin_rotates_within_same_industry_service_pool(self) -> None:
        cfg = config_with_only("round_robin")
        ctx = LeadAssignContext(
            lead_level="warm",
            industry_slug="spa",
            product_interest="quang-cao-facebook",
        )
        ids = []
        for _ in range(4):
            sid, _, strategy = auto_assign_lead_owner(self.conn, ctx, config=cfg)
            self.assertEqual(strategy, "round_robin")
            self.assertIn(sid, (self.staff["AM Spa FB"], self.staff["AM Spa FB 2"]))
            ids.append(sid)
        self.assertEqual(len(set(ids)), 2)

    def test_different_pools_do_not_share_rotation(self) -> None:
        cfg = config_with_only("round_robin")
        sid_spa, _, _ = auto_assign_lead_owner(
            self.conn,
            LeadAssignContext(
                industry_slug="spa",
                product_interest="quang-cao-facebook",
            ),
            config=cfg,
        )
        sid_fnb, _, _ = auto_assign_lead_owner(
            self.conn,
            LeadAssignContext(
                industry_slug="fnb",
                product_interest="quang-cao-google",
            ),
            config=cfg,
        )
        self.assertIn(sid_spa, (self.staff["AM Spa FB"], self.staff["AM Spa FB 2"]))
        self.assertEqual(sid_fnb, self.staff["AM FnB Google"])
        pk_spa = lead_assignment_pool_key(
            industry_slug="spa", service_slug="quang-cao-facebook"
        )
        pk_fnb = lead_assignment_pool_key(
            industry_slug="fnb", service_slug="quang-cao-google"
        )
        row_spa = self.conn.execute(
            "SELECT last_staff_id FROM crm_assignment_state WHERE pool_key = ?",
            (pk_spa,),
        ).fetchone()
        row_fnb = self.conn.execute(
            "SELECT last_staff_id FROM crm_assignment_state WHERE pool_key = ?",
            (pk_fnb,),
        ).fetchone()
        self.assertIsNotNone(row_spa)
        self.assertIsNotNone(row_fnb)

    def test_create_lead_auto_assign_respects_scope(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Lead R4",
            phone="0904000001",
            source="manual",
            product_interest="quang-cao-google",
            industry_slug="fnb",
            auto_assign=True,
            ts=TS,
        )
        out = lead_row_to_dict(row, self.conn)
        self.assertEqual(out["owner_id"], self.staff["AM FnB Google"])
        self.assertEqual(out["industry_slug"], "fnb")

    def test_no_scope_staff_returns_strategy(self) -> None:
        sid, _, strategy = assign_lead_owner(
            self.conn,
            industry_slug="bds",
            product_interest="dich-vu-seo-local",
            lead_level="warm",
        )
        self.assertIsNone(sid)
        self.assertEqual(strategy, "no_scope_staff")

    def test_list_and_delete_scope(self) -> None:
        scopes = list_staff_assign_scopes(self.conn)
        self.assertGreaterEqual(len(scopes), 3)
        scope_id = scopes[0]["id"]
        delete_staff_assign_scope(self.conn, scope_id)
        remaining = list_staff_assign_scopes(self.conn)
        self.assertEqual(len(remaining), len(scopes) - 1)


if __name__ == "__main__":
    unittest.main()
