"""Phase 1 — Lead theo dự án BĐS: schema, filter, dedup scoped, AI."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_ai import ai_recommend_lead, ai_search_leads
from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner, config_with_only
from crm_lead_store import (
    assign_lead,
    count_leads,
    create_lead,
    ensure_lead_schema,
    fetch_leads,
    find_duplicate_matches,
    lead_row_to_dict,
)
from crm_project_leads import (
    _UNSET,
    add_project_staff,
    assert_staff_in_project,
    assert_staff_portal_project,
    assignment_pool_key,
    ensure_project_leads_schema,
    fetch_project_assign_staff_ids,
    fetch_staff_project_ids,
    list_lead_project_options,
    list_lead_project_options_for_staff,
    list_project_staff,
    parse_re_project_filter,
    remove_project_staff,
    staff_can_view_lead,
    suggest_project_assignee,
    validate_re_project_id,
)
from crm_re_projects import create_project, ensure_re_projects_schema, refresh_project_re_leads_new_kpi

TS = "2026-06-15 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    ensure_lead_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            internal_code TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (1, 'Sales', 1)")
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (2, 'Sales B', 1)")
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (3, 'Outsider', 1)")
    conn.commit()
    return conn


def _seed_project(conn: sqlite3.Connection, *, name: str, code: str) -> int:
    proj = create_project(conn, {"name": name, "code": code}, ts=TS)
    return int(proj["id"])


class TestProjectLeadsPhase1(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="Dự án Alpha", code="DA-A")
        self.p2 = _seed_project(self.conn, name="Dự án Beta", code="DA-B")
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_schema_adds_re_project_id(self) -> None:
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(crm_leads)").fetchall()}
        self.assertIn("re_project_id", cols)

    def test_create_lead_with_project(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Khách A",
            phone="0901000001",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        out = lead_row_to_dict(row, self.conn)
        self.assertEqual(out["re_project_id"], self.p1)
        self.assertIn("Alpha", out["re_project_label"])

    def test_create_lead_invalid_project_raises(self) -> None:
        with self.assertRaises(ValueError):
            create_lead(
                self.conn,
                full_name="Bad",
                phone="0901000002",
                email="",
                re_project_id=9999,
                auto_assign=False,
                created_by="test",
                ts=TS,
            )

    def test_fetch_leads_filter_by_project(self) -> None:
        create_lead(
            self.conn,
            full_name="P1",
            phone="0901000011",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="P2",
            phone="0901000012",
            email="",
            re_project_id=self.p2,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="NoProj",
            phone="0901000013",
            email="",
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        p1_rows = fetch_leads(self.conn, re_project_id=self.p1, limit=50)
        names = {str(r["full_name"]) for r in p1_rows}
        self.assertEqual(names, {"P1"})
        self.assertEqual(count_leads(self.conn, re_project_id=self.p2), 1)
        unassigned = fetch_leads(self.conn, re_project_id=None, limit=50)
        self.assertEqual(len(unassigned), 1)
        self.assertEqual(str(unassigned[0]["full_name"]), "NoProj")

    def test_duplicate_scoped_per_project(self) -> None:
        create_lead(
            self.conn,
            full_name="Dup P1",
            phone="0902000001",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="Dup P2",
            phone="0902000001",
            email="",
            re_project_id=self.p2,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        d1 = find_duplicate_matches(
            self.conn, phone="0902000001", email="", re_project_id=self.p1
        )
        d2 = find_duplicate_matches(
            self.conn, phone="0902000001", email="", re_project_id=self.p2
        )
        self.assertEqual(len(d1), 1)
        self.assertEqual(len(d2), 1)
        self.assertNotEqual(d1[0]["lead_id"], d2[0]["lead_id"])

    def test_list_lead_project_options(self) -> None:
        opts = list_lead_project_options(self.conn)
        self.assertGreaterEqual(len(opts), 2)
        self.assertTrue(any(o["id"] == self.p1 for o in opts))

    def test_parse_re_project_filter(self) -> None:
        self.assertIs(parse_re_project_filter(None), _UNSET)
        self.assertIs(parse_re_project_filter(""), _UNSET)
        self.assertIs(parse_re_project_filter("none"), None)
        self.assertEqual(parse_re_project_filter("3"), 3)

    def test_ai_search_respects_project_filter(self) -> None:
        create_lead(
            self.conn,
            full_name="Hot Alpha",
            phone="0903000001",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.execute(
            "UPDATE crm_leads SET lead_level = 'hot' WHERE full_name = 'Hot Alpha'"
        )
        create_lead(
            self.conn,
            full_name="Hot Beta",
            phone="0903000002",
            email="",
            re_project_id=self.p2,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.execute(
            "UPDATE crm_leads SET lead_level = 'hot' WHERE full_name = 'Hot Beta'"
        )
        self.conn.commit()
        out = ai_search_leads(self.conn, "lead hot uu tien", re_project_id=self.p1, ts=TS)
        names = {l["full_name"] for l in out.get("leads") or []}
        self.assertIn("Hot Alpha", names)
        self.assertNotIn("Hot Beta", names)
        self.assertIn("Alpha", out.get("answer") or "")

    def test_validate_re_project_id(self) -> None:
        validate_re_project_id(self.conn, None)
        with self.assertRaises(ValueError):
            validate_re_project_id(self.conn, 404)


class TestProjectLeadsPhase2(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="Dự án Alpha", code="DA-A")
        add_project_staff(self.conn, self.p1, staff_id=1, assign_enabled=True, ts=TS)
        add_project_staff(self.conn, self.p1, staff_id=2, assign_enabled=True, ts=TS)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_project_staff_schema_and_list(self) -> None:
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(crm_re_project_staff)").fetchall()}
        self.assertIn("assign_enabled", cols)
        staff = list_project_staff(self.conn, self.p1)
        self.assertEqual(len(staff), 2)
        self.assertEqual(fetch_project_assign_staff_ids(self.conn, self.p1), [1, 2])

    def test_auto_assign_scoped_to_project_pool(self) -> None:
        cfg = config_with_only("round_robin")
        ctx = LeadAssignContext(re_project_id=self.p1)
        sid1, _, _ = auto_assign_lead_owner(self.conn, ctx, config=cfg)
        sid2, _, _ = auto_assign_lead_owner(self.conn, ctx, config=cfg)
        self.assertIn(sid1, (1, 2))
        self.assertIn(sid2, (1, 2))
        self.assertNotEqual(sid1, sid2)
        self.assertEqual(assignment_pool_key(self.p1), f"lead_rr:project:{self.p1}")

    def test_auto_assign_no_project_staff_fails_closed(self) -> None:
        remove_project_staff(self.conn, self.p1, 1, ts=TS)
        remove_project_staff(self.conn, self.p1, 2, ts=TS)
        self.conn.commit()
        cfg = config_with_only("round_robin")
        sid, _, strategy = auto_assign_lead_owner(
            self.conn,
            LeadAssignContext(re_project_id=self.p1),
            config=cfg,
        )
        self.assertIsNone(sid)
        self.assertEqual(strategy, "no_project_staff")

    def test_create_lead_auto_assigns_project_staff_only(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Lead scoped",
            phone="0904000001",
            email="",
            re_project_id=self.p1,
            auto_assign=True,
            created_by="test",
            ts=TS,
        )
        out = lead_row_to_dict(row, self.conn)
        self.assertIn(out["owner_id"], (1, 2))

    def test_manual_assign_rejects_outside_project(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Need assign",
            phone="0904000002",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        p2 = _seed_project(self.conn, name="Other", code="OT")
        self.conn.commit()
        with self.assertRaises(ValueError):
            assign_lead(
                self.conn,
                int(row["id"]),
                to_user_id=3,
                reason="test",
                assigned_by="admin",
                ts=TS,
            )
        assert_staff_in_project(self.conn, self.p1, 1)
        updated = assign_lead(
            self.conn,
            int(row["id"]),
            to_user_id=1,
            reason="ok",
            assigned_by="admin",
            ts=TS,
        )
        self.assertEqual(int(updated["owner_id"]), 1)

    def test_ai_recommend_suggests_project_assignee(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Unassigned",
            phone="0904000003",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        out = ai_recommend_lead(self.conn, int(row["id"]), ts=TS)
        recs = out.get("recommendations") or []
        assign_recs = [r for r in recs if r.get("type") == "assign"]
        self.assertTrue(assign_recs)
        self.assertIn(assign_recs[0]["staff_id"], (1, 2))

    def test_ai_search_unassigned_project_leads(self) -> None:
        create_lead(
            self.conn,
            full_name="No owner",
            phone="0904000004",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        out = ai_search_leads(self.conn, "lead chua gan owner", re_project_id=self.p1, ts=TS)
        names = {l["full_name"] for l in out.get("leads") or []}
        self.assertIn("No owner", names)

    def test_suggest_project_assignee(self) -> None:
        sug = suggest_project_assignee(self.conn, self.p1, lead_level="hot")
        self.assertIsNotNone(sug)
        self.assertIn(sug["staff_id"], (1, 2))


class TestProjectLeadsPhase3(unittest.TestCase):
    def setUp(self) -> None:
        from crm_lead_rules import save_lead_config
        from crm_project_webhooks import save_project_lead_config

        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="Dự án Alpha", code="DA-A")
        add_project_staff(self.conn, self.p1, staff_id=1, assign_enabled=True, ts=TS)
        save_project_lead_config(
            self.conn,
            self.p1,
            {
                "enabled": True,
                "webhook_slug": "slug-alpha",
                "facebook_page_id": "page_alpha",
                "forms": [{"form_id": "form_alpha_1", "form_name": "Form Alpha", "active": True}],
            },
            updated_by="test",
            ts=TS,
        )
        save_lead_config(
            self.conn,
            config={
                "assign_config": config_with_only("round_robin"),
                "facebook_config": {
                    "enabled": True,
                    "page_id": "page_global",
                    "form_ids": [],
                    "auto_assign": True,
                    "webhook_enabled": True,
                },
            },
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_webhook_schema_tables(self) -> None:
        tables = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("crm_re_project_lead_config", tables)
        self.assertIn("crm_re_project_facebook_forms", tables)

    def test_resolve_project_from_form_id(self) -> None:
        from crm_project_webhooks import resolve_project_from_webhook

        pid = resolve_project_from_webhook(self.conn, form_id="form_alpha_1")
        self.assertEqual(pid, self.p1)

    def test_resolve_project_from_webhook_slug(self) -> None:
        from crm_project_webhooks import resolve_project_from_webhook

        pid = resolve_project_from_webhook(self.conn, webhook_slug="slug-alpha")
        self.assertEqual(pid, self.p1)

    def test_facebook_lead_item_assigns_project(self) -> None:
        import unittest.mock

        from crm_facebook_leads import process_facebook_lead_item

        item = {
            "full_name": "Lead FB dự án",
            "phone": "0905000001",
            "email": "",
            "meta": {
                "facebook_form_id": "form_alpha_1",
                "facebook_page_id": "page_alpha",
                "facebook_leadgen_id": "lg_proj_1",
            },
        }
        result = process_facebook_lead_item(
            self.conn, item, created_by="test", ts=TS, skip_source_filter=True
        )
        self.assertIn(result.get("status"), ("created_assigned", "created_unassigned"))
        self.assertEqual(result.get("re_project_id"), self.p1)
        row = self.conn.execute(
            "SELECT re_project_id, owner_id FROM crm_leads WHERE phone LIKE '%0905000001%'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["re_project_id"]), self.p1)
        self.assertEqual(int(row["owner_id"]), 1)

    def test_webhook_payload_maps_form_to_project(self) -> None:
        import unittest.mock

        from crm_facebook_leads import (
            find_lead_by_facebook_leadgen_id,
            process_facebook_webhook_payload,
        )

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_alpha",
                    "time": 1,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lg_webhook_proj",
                                "form_id": "form_alpha_1",
                                "page_id": "page_alpha",
                            },
                        }
                    ],
                }
            ],
        }
        with unittest.mock.patch(
            "crm_facebook_leads.fetch_facebook_lead_from_graph_with_retry",
            return_value={
                "full_name": "Webhook Project",
                "phone": "0905000002",
                "email": "",
                "meta": {},
            },
        ):
            result = process_facebook_webhook_payload(
                self.conn, payload, created_by="webhook:test", ts=TS
            )
        self.assertEqual(int(result.get("created_count") or 0), 1)
        lid = find_lead_by_facebook_leadgen_id(self.conn, "lg_webhook_proj")
        self.assertIsNotNone(lid)
        row = self.conn.execute("SELECT re_project_id FROM crm_leads WHERE id = ?", (lid,)).fetchone()
        self.assertEqual(int(row["re_project_id"]), self.p1)

    def test_slug_webhook_forces_project(self) -> None:
        import unittest.mock

        from crm_facebook_leads import process_facebook_webhook_payload

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_other",
                    "time": 1,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lg_slug_force",
                                "form_id": "form_UNKNOWN",
                                "page_id": "page_other",
                            },
                        }
                    ],
                }
            ],
        }
        with unittest.mock.patch(
            "crm_facebook_leads.fetch_facebook_lead_from_graph_with_retry",
            return_value={
                "full_name": "Slug Force",
                "phone": "0905000003",
                "email": "",
                "meta": {},
            },
        ):
            result = process_facebook_webhook_payload(
                self.conn,
                payload,
                created_by="webhook:test",
                ts=TS,
                webhook_slug="slug-alpha",
                forced_project_id=self.p1,
            )
        self.assertEqual(int(result.get("created_count") or 0), 1)
        row = self.conn.execute(
            "SELECT re_project_id FROM crm_leads WHERE phone LIKE '%0905000003%'"
        ).fetchone()
        self.assertEqual(int(row["re_project_id"]), self.p1)

    def test_ai_search_unmapped_facebook_forms(self) -> None:
        from crm_facebook_pending import enqueue_facebook_leadgen

        enqueue_facebook_leadgen(
            self.conn,
            leadgen_id="lg_unmapped",
            form_id="form_UNMAPPED_X",
            page_id="page_alpha",
            ts=TS,
            error="pending",
        )
        self.conn.commit()
        out = ai_search_leads(self.conn, "form facebook chua map", ts=TS)
        form_ids = {r.get("form_id") for r in out.get("leads") or []}
        self.assertIn("form_UNMAPPED_X", form_ids)
        self.assertIn("map", out.get("answer", "").lower())

    def test_ai_recommend_suggests_form_mapping(self) -> None:
        from crm_facebook_pending import enqueue_facebook_leadgen

        enqueue_facebook_leadgen(
            self.conn,
            leadgen_id="lg_map_sug",
            form_id="form_SUGGEST",
            page_id="page_alpha",
            ts=TS,
            error="pending",
        )
        row, _, _ = create_lead(
            self.conn,
            full_name="FB no project",
            phone="0905000004",
            email="",
            source="facebook",
            meta={"facebook_form_id": "form_SUGGEST"},
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        out = ai_recommend_lead(self.conn, int(row["id"]), ts=TS)
        recs = [r for r in (out.get("recommendations") or []) if r.get("type") == "webhook_map"]
        self.assertTrue(recs)
        self.assertEqual(recs[0].get("project_id"), self.p1)


class TestProjectLeadsPhase4(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="Alpha", code="DA-A")
        self.p2 = _seed_project(self.conn, name="Beta", code="DA-B")
        add_project_staff(self.conn, self.p1, staff_id=1, role="sales", assign_enabled=True, ts=TS)
        add_project_staff(self.conn, self.p1, staff_id=2, role="manager", assign_enabled=True, ts=TS)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_fetch_staff_project_ids(self) -> None:
        self.assertEqual(fetch_staff_project_ids(self.conn, 1), [self.p1])
        self.assertEqual(fetch_staff_project_ids(self.conn, 3), [])

    def test_list_lead_project_options_for_staff(self) -> None:
        opts = list_lead_project_options_for_staff(self.conn, 1)
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0]["id"], self.p1)
        all_opts = list_lead_project_options(self.conn)
        self.assertGreaterEqual(len(all_opts), 2)

    def test_staff_can_view_own_lead_in_project(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Mine",
            phone="0906000001",
            email="",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.assertTrue(staff_can_view_lead(self.conn, 1, row))

    def test_staff_cannot_view_other_project_lead(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Other",
            phone="0906000002",
            email="",
            re_project_id=self.p2,
            owner_id=None,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.assertFalse(staff_can_view_lead(self.conn, 1, row))

    def test_manager_sees_all_project_leads(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Team",
            phone="0906000003",
            email="",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.assertTrue(staff_can_view_lead(self.conn, 2, row))

    def test_fetch_leads_staff_portal_scope(self) -> None:
        create_lead(
            self.conn,
            full_name="P1 mine",
            phone="0906000011",
            email="",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="P2 other",
            phone="0906000012",
            email="",
            re_project_id=self.p2,
            owner_id=None,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        rows = fetch_leads(self.conn, staff_portal_id=1, limit=50)
        names = {lead_row_to_dict(r, self.conn)["full_name"] for r in rows}
        self.assertIn("P1 mine", names)
        self.assertNotIn("P2 other", names)

    def test_owner_stats_staff_portal_only_own_assigned(self) -> None:
        from crm_lead_sla import fetch_lead_owner_stats

        add_project_staff(self.conn, self.p1, staff_id=1, assign_enabled=True, ts=TS)
        add_project_staff(self.conn, self.p1, staff_id=2, assign_enabled=True, role="manager", ts=TS)
        create_lead(
            self.conn,
            full_name="Lead NV1",
            phone="0906000101",
            email="",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="Lead NV2",
            phone="0906000102",
            email="",
            re_project_id=self.p1,
            owner_id=2,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        all_stats = fetch_lead_owner_stats(self.conn)
        self.assertEqual(len(all_stats), 2)
        staff_stats = fetch_lead_owner_stats(self.conn, staff_portal_id=1)
        self.assertEqual(len(staff_stats), 1)
        self.assertEqual(staff_stats[0]["owner_id"], 1)
        self.assertEqual(staff_stats[0]["total"], 1)

    def test_owner_stats_by_care_stage(self) -> None:
        from crm_lead_care_pipeline import complete_lead_care_stage
        from crm_lead_sla import fetch_lead_owner_stats

        row1, _, _ = create_lead(
            self.conn,
            full_name="Stage A",
            phone="0906000201",
            email="",
            need="Tu van",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="Stage B",
            phone="0906000202",
            email="",
            need="Tu van",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        complete_lead_care_stage(
            self.conn,
            lead_id=int(row2["id"]),
            stage_key="intake",
            created_by="test",
            ts="2026-05-25 11:00:00",
        )
        self.conn.commit()
        stats = fetch_lead_owner_stats(self.conn, owner_id=1)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["total"], 2)
        by_stage = stats[0]["by_care_stage"]
        self.assertEqual(by_stage.get("intake"), 1)
        self.assertEqual(by_stage.get("first_contact"), 1)
        self.assertEqual(stats[0]["open"], 2)
        self.assertEqual(stats[0]["won"], 0)

    def test_owner_stats_excludes_leads_without_project(self) -> None:
        from crm_lead_sla import fetch_lead_owner_stats

        create_lead(
            self.conn,
            full_name="With Project",
            phone="0906000501",
            email="",
            need="Tu van",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="No Project",
            phone="0906000502",
            email="",
            need="Tu van",
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        stats = fetch_lead_owner_stats(self.conn, owner_id=1)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["total"], 1)
        self.assertEqual(len(stats[0]["projects"]), 1)

    def test_owner_stats_portal_matches_project_scope(self) -> None:
        """Portal NV: chỉ đếm lead thuộc dự án tham gia — không đếm lead chưa gán dự án."""
        from crm_lead_sla import fetch_lead_owner_stats

        add_project_staff(self.conn, self.p1, staff_id=1, assign_enabled=True, ts=TS)
        create_lead(
            self.conn,
            full_name="In Project",
            phone="0906000301",
            email="",
            need="Tu van",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="No Project",
            phone="0906000302",
            email="",
            need="Tu van",
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        stats = fetch_lead_owner_stats(self.conn, staff_portal_id=1)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["total"], 1)
        self.assertEqual(stats[0]["owner_id"], 1)

    def test_staff_multi_project_leads_and_stats(self) -> None:
        """NV tham gia nhiều dự án — thấy lead & hiệu suất gộp cả hai dự án."""
        from crm_lead_sla import fetch_lead_owner_stats
        from crm_lead_store import fetch_leads, lead_row_to_dict

        p2 = _seed_project(self.conn, name="Multi P2", code="MP2")
        add_project_staff(self.conn, self.p1, staff_id=1, assign_enabled=True, ts=TS)
        add_project_staff(self.conn, p2, staff_id=1, assign_enabled=True, ts=TS)
        create_lead(
            self.conn,
            full_name="Lead P1",
            phone="0906000401",
            email="",
            need="Tu van",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="Lead P2",
            phone="0906000402",
            email="",
            need="Tu van",
            re_project_id=p2,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        rows = fetch_leads(self.conn, staff_portal_id=1, limit=50)
        names = {lead_row_to_dict(r, self.conn)["full_name"] for r in rows}
        self.assertIn("Lead P1", names)
        self.assertIn("Lead P2", names)
        stats = fetch_lead_owner_stats(self.conn, staff_portal_id=1)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["total"], 2)
        self.assertEqual(stats[0]["project_count"], 2)
        self.assertEqual(len(stats[0]["projects"]), 2)

    def test_assert_staff_portal_project(self) -> None:
        with self.assertRaises(ValueError):
            assert_staff_portal_project(self.conn, 1, None)
        with self.assertRaises(ValueError):
            assert_staff_portal_project(self.conn, 1, self.p2)

    def test_re_leads_new_kpi_auto_count(self) -> None:
        create_lead(
            self.conn,
            full_name="KPI A",
            phone="0906000021",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="KPI B",
            phone="0906000022",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        period = TS[:7]
        out = refresh_project_re_leads_new_kpi(self.conn, self.p1, period_month=period, ts=TS)
        self.assertTrue(out.get("updated"))
        self.assertEqual(int(out.get("actual") or 0), 2)
        row = self.conn.execute(
            "SELECT actual_value FROM crm_re_project_kpis WHERE project_id = ? AND metric_code = ?",
            (self.p1, "RE_LEADS_NEW"),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["actual_value"]), 2)


class TestProjectLeadsE2EFlow(unittest.TestCase):
    """Luồng tổng thể Phase 1→5: webhook → dự án → assign → portal → KPI."""

    def setUp(self) -> None:
        import unittest.mock

        from crm_lead_rules import save_lead_config
        from crm_lead_auto_assign import config_with_only
        from crm_project_webhooks import save_project_lead_config

        self.mock = unittest.mock
        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="E2E Tower", code="E2E-T")
        add_project_staff(self.conn, self.p1, staff_id=1, role="sales", assign_enabled=True, ts=TS)
        add_project_staff(self.conn, self.p1, staff_id=2, role="manager", assign_enabled=True, ts=TS)
        save_project_lead_config(
            self.conn,
            self.p1,
            {
                "enabled": True,
                "webhook_slug": "e2e-slug",
                "facebook_page_id": "page_e2e",
                "forms": [{"form_id": "2814926042203269", "form_name": "Form E2E", "active": True}],
            },
            updated_by="test",
            ts=TS,
        )
        save_lead_config(
            self.conn,
            config={
                "assign_config": config_with_only("round_robin"),
                "facebook_config": {
                    "enabled": True,
                    "page_id": "page_e2e",
                    "form_ids": [],
                    "auto_assign": True,
                    "webhook_enabled": True,
                },
            },
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_full_webhook_to_portal_and_kpi(self) -> None:
        from crm_facebook_leads import process_facebook_webhook_payload
        from crm_lead_store import fetch_new_assigned_leads

        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_e2e",
                    "time": 1,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lg_e2e_flow",
                                "form_id": "2814926042203269",
                                "page_id": "page_e2e",
                            },
                        }
                    ],
                }
            ],
        }
        with self.mock.patch(
            "crm_facebook_leads.fetch_facebook_lead_from_graph_with_retry",
            return_value={
                "full_name": "Khách E2E",
                "phone": "0907000001",
                "email": "",
                "meta": {},
            },
        ):
            result = process_facebook_webhook_payload(
                self.conn,
                payload,
                created_by="webhook:test",
                ts=TS,
                webhook_slug="e2e-slug",
                forced_project_id=self.p1,
            )
        self.conn.commit()
        self.assertEqual(int(result.get("created_count") or 0), 1)
        row = self.conn.execute(
            "SELECT id, re_project_id, owner_id FROM crm_leads WHERE phone LIKE '%0907000001%'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["re_project_id"]), self.p1)
        self.assertEqual(int(row["owner_id"]), 1)

        lead_row = self.conn.execute("SELECT * FROM crm_leads WHERE id = ?", (int(row["id"]),)).fetchone()
        self.assertTrue(staff_can_view_lead(self.conn, 1, lead_row))
        self.assertTrue(staff_can_view_lead(self.conn, 2, lead_row))

        sales_rows = fetch_leads(self.conn, staff_portal_id=1, limit=50)
        sales_phones = {lead_row_to_dict(r, self.conn)["phone"] for r in sales_rows}
        self.assertTrue(any("0907000001" in p for p in sales_phones))

        mgr_rows = fetch_leads(self.conn, staff_portal_id=2, limit=50)
        mgr_phones = {lead_row_to_dict(r, self.conn)["phone"] for r in mgr_rows}
        self.assertTrue(any("0907000001" in p for p in mgr_phones))

        notifs = fetch_new_assigned_leads(self.conn, after_id=0, staff_portal_id=1, limit=10)
        self.assertTrue(any(int(r["id"]) == int(row["id"]) for r in notifs))

        kpi = refresh_project_re_leads_new_kpi(self.conn, self.p1, period_month=TS[:7], ts=TS)
        self.assertGreaterEqual(int(kpi.get("actual") or 0), 1)

    def test_dedup_scoped_while_webhook_adds_second_project(self) -> None:
        from crm_facebook_leads import process_facebook_lead_item
        from crm_project_webhooks import save_project_lead_config

        p2 = _seed_project(self.conn, name="E2E Other", code="E2E-O")
        add_project_staff(self.conn, p2, staff_id=1, assign_enabled=True, ts=TS)
        save_project_lead_config(
            self.conn,
            p2,
            {
                "forms": [{"form_id": "form_other_e2e", "active": True}],
            },
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

        create_lead(
            self.conn,
            full_name="Dup A",
            phone="0907000100",
            email="",
            re_project_id=self.p1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        item = {
            "full_name": "Dup B",
            "phone": "0907000100",
            "email": "",
            "meta": {"facebook_form_id": "form_other_e2e", "facebook_page_id": "page_e2e"},
        }
        result = process_facebook_lead_item(
            self.conn, item, created_by="test", ts=TS, skip_source_filter=True, re_project_id=p2
        )
        self.assertIn(result.get("status"), ("created_assigned", "created_unassigned", "duplicate_linked"))
        total = count_leads(self.conn, re_project_id=p2)
        self.assertGreaterEqual(total, 1)

    def test_staff_without_project_sees_nothing(self) -> None:
        create_lead(
            self.conn,
            full_name="Hidden",
            phone="0907000200",
            email="",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        rows = fetch_leads(self.conn, staff_portal_id=3, limit=50)
        self.assertEqual(len(rows), 0)

    def test_notifications_scoped_to_project(self) -> None:
        from crm_lead_store import fetch_new_assigned_leads

        p2 = _seed_project(self.conn, name="Other", code="OTH")
        row1, _, _ = create_lead(
            self.conn,
            full_name="Mine",
            phone="0907000301",
            email="",
            re_project_id=self.p1,
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        create_lead(
            self.conn,
            full_name="Other proj",
            phone="0907000302",
            email="",
            re_project_id=p2,
            owner_id=None,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        notifs = fetch_new_assigned_leads(self.conn, after_id=0, staff_portal_id=1, limit=20)
        ids = {int(r["id"]) for r in notifs}
        self.assertIn(int(row1["id"]), ids)
        self.assertEqual(len(ids), 1)


class TestProjectLeadsZaloWebhook(unittest.TestCase):
    def setUp(self) -> None:
        from crm_lead_rules import save_lead_config
        from crm_project_webhooks import save_project_lead_config

        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="Dự án Zalo", code="DA-Z")
        add_project_staff(self.conn, self.p1, staff_id=1, assign_enabled=True, ts=TS)
        save_project_lead_config(
            self.conn,
            self.p1,
            {
                "enabled": True,
                "webhook_slug": "slug-zalo",
                "zalo_oa_id": "oa_zalo_alpha",
                "zalo_campaigns": [
                    {
                        "campaign_id": "zalo_camp_001",
                        "campaign_name": "Zalo Ads Alpha",
                        "active": True,
                    }
                ],
            },
            updated_by="test",
            ts=TS,
        )
        save_lead_config(
            self.conn,
            config={"assign_config": config_with_only("round_robin")},
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_zalo_webhook_schema_tables(self) -> None:
        tables = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("crm_re_project_zalo_campaigns", tables)

    def test_resolve_project_from_zalo_campaign_id(self) -> None:
        from crm_project_webhooks import resolve_project_from_zalo_webhook

        pid = resolve_project_from_zalo_webhook(self.conn, campaign_id="zalo_camp_001")
        self.assertEqual(pid, self.p1)

    def test_resolve_project_from_zalo_slug(self) -> None:
        from crm_project_webhooks import resolve_project_from_zalo_webhook

        pid = resolve_project_from_zalo_webhook(self.conn, webhook_slug="slug-zalo")
        self.assertEqual(pid, self.p1)

    def test_zalo_lead_item_assigns_project(self) -> None:
        from crm_lead_webhooks import process_zalo_lead_item

        item = {
            "full_name": "Lead Zalo dự án",
            "phone": "0906000001",
            "email": "",
            "campaign_id": "zalo_camp_001",
            "meta": {"oa_id": "oa_zalo_alpha", "campaign_id": "zalo_camp_001"},
        }
        result = process_zalo_lead_item(self.conn, item, created_by="test", ts=TS)
        self.assertIn(result.get("status"), ("created_assigned", "created_unassigned"))
        self.assertEqual(result.get("re_project_id"), self.p1)
        row = self.conn.execute(
            "SELECT re_project_id, owner_id FROM crm_leads WHERE phone LIKE '%0906000001%'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["re_project_id"]), self.p1)
        self.assertEqual(int(row["owner_id"]), 1)

    def test_zalo_ingest_via_webhook_slug(self) -> None:
        from crm_lead_webhooks import ingest_webhook_leads

        items = [
            {
                "full_name": "Lead Zalo slug",
                "phone": "0906000002",
                "email": "",
                "source": "zalo",
                "meta": {"webhook": "zalo"},
            }
        ]
        result = ingest_webhook_leads(
            self.conn,
            items,
            default_source="zalo",
            created_by="webhook:zalo",
            ts=TS,
            webhook_slug="slug-zalo",
        )
        self.assertEqual(result.get("created_count"), 1)
        row = self.conn.execute(
            "SELECT re_project_id FROM crm_leads WHERE phone LIKE '%0906000002%'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["re_project_id"]), self.p1)


class TestProjectWebsiteRoutes(unittest.TestCase):
    def setUp(self) -> None:
        from crm_project_webhooks import save_project_lead_config

        self.conn = _setup_conn()
        self.p1 = _seed_project(self.conn, name="Vinhomes Saigon Park", code="VSP")
        save_project_lead_config(
            self.conn,
            self.p1,
            {
                "enabled": True,
                "webhook_enabled": True,
                "webhook_slug": "vsp-seo",
                "website_routes": [
                    {
                        "route_key": "seo-vinhomes-saigon-park",
                        "route_name": "UTM SEO VSP",
                        "route_type": "utm",
                        "active": True,
                    },
                    {
                        "route_key": "vinhomesssaigonpark.vn",
                        "route_name": "Landing VSP",
                        "route_type": "site",
                        "active": True,
                    },
                ],
            },
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_resolve_by_utm_campaign(self) -> None:
        from crm_project_webhooks import resolve_project_for_lead_ingest

        pid = resolve_project_for_lead_ingest(
            self.conn,
            utm_campaign="seo-vinhomes-saigon-park",
        )
        self.assertEqual(pid, self.p1)

    def test_resolve_by_ingest_site(self) -> None:
        from crm_project_webhooks import resolve_project_for_lead_ingest

        pid = resolve_project_for_lead_ingest(
            self.conn,
            ingest_site="vinhomesssaigonpark.vn",
        )
        self.assertEqual(pid, self.p1)

    def test_resolve_by_project_code(self) -> None:
        from crm_project_webhooks import resolve_project_for_lead_ingest

        pid = resolve_project_for_lead_ingest(self.conn, re_project_code="VSP")
        self.assertEqual(pid, self.p1)

    def test_ingest_lead_assigns_project(self) -> None:
        from crm_project_webhooks import resolve_project_for_lead_ingest

        pid = resolve_project_for_lead_ingest(
            self.conn,
            utm_campaign="seo-vinhomes-saigon-park",
        )
        self.assertEqual(pid, self.p1)
        row, _, _ = create_lead(
            self.conn,
            full_name="Lead SEO VSP",
            phone="0908000001",
            email="",
            source="website",
            utm_campaign="seo-vinhomes-saigon-park",
            re_project_id=pid,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.assertEqual(int(row["re_project_id"]), self.p1)


if __name__ == "__main__":
    unittest.main()
